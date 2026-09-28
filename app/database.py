"""PostgreSQL jobs with atomic claims, fencing tokens and durable budgets."""

from datetime import datetime, timezone
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.contracts import ARGUMENTS, RESTART_TOOL, Policy, Rejected, request, uuid_text
from app.runtime import MODE


class Database:
    def __init__(self, dsn, policy=None):
        self.dsn = dsn
        self.policy = policy or Policy()

    def connect(self):
        return psycopg.connect(self.dsn, row_factory=dict_row, connect_timeout=3,
                               options='-c statement_timeout=2000 -c lock_timeout=1000')

    @staticmethod
    def view(row):
        return {**row['data'], 'status': row['status'], 'attempts': row['attempts'],
                'step_count': row['step_count']}

    def get(self, run_id):
        run_id = uuid_text(run_id)
        with self.connect() as conn:
            row = conn.execute('SELECT * FROM jobs WHERE run_id = %s', (run_id,)).fetchone()
            if not row:
                return None
            run = self.view(row)
            run['events'] = [dict(e, at=e['at'].isoformat()) for e in conn.execute(
                'SELECT at, kind, detail FROM events WHERE run_id = %s ORDER BY event_id',
                (run_id,))]
            return run

    def create(self, payload, revision):
        question, scenario = request(payload)
        run_id = str(uuid4())
        data = dict(run_id=run_id, mode=MODE, revision=revision, question=question,
                    scenario=scenario, started_at=datetime.now(timezone.utc).isoformat(),
                    steps=[], outcome=None, error=None, summary='Waiting for a worker.',
                    duration_ms=0)
        with self.connect() as conn:
            conn.execute('''INSERT INTO jobs
                (run_id, data, status, deadline, max_steps, max_attempts)
                VALUES (%s, %s, 'queued', clock_timestamp() + %s * interval '1 second', %s, %s)''',
                (run_id, Jsonb(data), self.policy.deadline_seconds,
                 self.policy.max_steps, self.policy.max_attempts))
        return self.get(run_id)

    @staticmethod
    def event(conn, run_id, kind, detail):
        conn.execute('INSERT INTO events (run_id, kind, detail) VALUES (%s, %s, %s)',
                     (run_id, kind, Jsonb(detail)))

    def claim(self):
        token = str(uuid4())
        with self.connect() as conn:
            # A crashed worker cannot leave a job running forever, even on its last attempt.
            expired = conn.execute('''UPDATE jobs SET status = 'failed', lease_token = NULL,
                data = data || jsonb_build_object('error', CASE
                    WHEN status = 'awaiting_approval' THEN 'APPROVAL_EXPIRED'
                    WHEN deadline <= clock_timestamp() THEN 'DEADLINE_EXCEEDED'
                    ELSE 'ATTEMPTS_EXHAUSTED' END,
                    'summary', 'Execution stopped at a durable limit.',
                    'duration_ms', EXTRACT(EPOCH FROM (clock_timestamp() - created_at)) * 1000,
                    'finished_at', clock_timestamp())
                WHERE status IN ('queued', 'running', 'awaiting_approval')
                AND (deadline <= clock_timestamp() OR
                    (status = 'running' AND lease_until <= clock_timestamp()
                     AND attempts >= max_attempts)) RETURNING run_id, data''').fetchall()
            for row in expired:
                self.event(conn, row['run_id'], 'failed', {'error': row['data']['error']})
            row = conn.execute('''WITH candidate AS (
                SELECT run_id FROM jobs WHERE deadline > clock_timestamp()
                AND attempts < max_attempts AND
                (status = 'queued' OR (status = 'running' AND lease_until <= clock_timestamp()))
                ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1)
                UPDATE jobs j SET status = 'running', lease_token = %s,
                    lease_until = LEAST(deadline, clock_timestamp() + %s * interval '1 second'),
                    attempts = attempts + 1
                FROM candidate c WHERE j.run_id = c.run_id RETURNING j.*''',
                (token, self.policy.lease_seconds)).fetchone()
            if row:
                self.event(conn, row['run_id'], 'claimed', {'attempt': row['attempts']})
                return row
        return None

    def locked(self, conn, job):
        row = conn.execute('''SELECT *, deadline > clock_timestamp() AS within_deadline,
            lease_until > clock_timestamp() AS within_lease FROM jobs
            WHERE run_id = %s FOR UPDATE''', (job['run_id'],)).fetchone()
        if (not row or row['status'] != 'running' or row['lease_token'] != job['lease_token']
                or not row['within_lease'] or not row['within_deadline']):
            raise Rejected('LEASE_LOST', 409)
        return row

    def reserve_step(self, job, tool, arguments):
        with self.connect() as conn:
            row = self.locked(conn, job)
            if row['step_count'] >= row['max_steps']:
                raise Rejected('STEP_LIMIT', 409)
            step = row['step_count'] + 1
            conn.execute('''UPDATE jobs SET step_count = %s,
                lease_until = LEAST(deadline, clock_timestamp() + %s * interval '1 second')
                WHERE run_id = %s''', (step, self.policy.lease_seconds, job['run_id']))
            self.event(conn, job['run_id'], 'tool_started',
                       {'step': step, 'tool': tool, 'arguments': arguments})
            return step

    def record_step(self, job, step):
        with self.connect() as conn:
            row = self.locked(conn, job)
            data = row['data']
            data['steps'].append(step)
            conn.execute('UPDATE jobs SET data = %s WHERE run_id = %s',
                         (Jsonb(data), job['run_id']))
            self.event(conn, job['run_id'], 'tool_' + step['status'], step)

    def finish(self, job, status, **values):
        with self.connect() as conn:
            row = self.locked(conn, job)
            data = row['data']
            data.update(values)
            data['duration_ms'] = round((datetime.now(timezone.utc) - row['created_at']).total_seconds() * 1000, 3)
            if status in ('failed', 'completed'):
                data['finished_at'] = datetime.now(timezone.utc).isoformat()
            conn.execute('''UPDATE jobs SET status = %s, data = %s, lease_token = NULL,
                lease_until = NULL, deadline = CASE WHEN %s = 'awaiting_approval'
                THEN clock_timestamp() + %s * interval '1 second' ELSE deadline END
                WHERE run_id = %s''',
                (status, Jsonb(data), status, self.policy.approval_seconds, job['run_id']))
            self.event(conn, job['run_id'], status, values)

    def approve(self, run_id, payload, identity):
        run_id = uuid_text(run_id)
        if (not isinstance(payload, dict) or set(payload) != {'tool', 'arguments'}
                or payload['tool'] != RESTART_TOOL or payload['arguments'] != ARGUMENTS):
            raise Rejected('APPROVAL_BINDING_MISMATCH', 409)
        with self.connect() as conn:
            row = conn.execute('''SELECT *, deadline > clock_timestamp() AS valid
                FROM jobs WHERE run_id = %s FOR UPDATE''', (run_id,)).fetchone()
            if not row:
                raise Rejected('RUN_NOT_FOUND', 404)
            if row['status'] != 'awaiting_approval' or not row['valid']:
                raise Rejected('APPROVAL_NOT_PENDING', 409)
            if row['data'].get('pending_approval') != payload:
                raise Rejected('APPROVAL_BINDING_MISMATCH', 409)
            approval_id = str(uuid4())
            conn.execute('''INSERT INTO approvals
                (approval_id, run_id, tool, arguments, approved_by, expires_at)
                VALUES (%s, %s, %s, %s, %s, clock_timestamp() + %s * interval '1 second')''',
                (approval_id, run_id, payload['tool'], Jsonb(payload['arguments']), identity,
                 self.policy.approval_seconds))
            data = row['data']
            data.pop('pending_approval')
            data.update(approval_id=approval_id, summary='Approved; waiting for a worker.')
            conn.execute('''UPDATE jobs SET status = 'queued', data = %s,
                deadline = clock_timestamp() + %s * interval '1 second' WHERE run_id = %s''',
                (Jsonb(data), self.policy.deadline_seconds, run_id))
        return self.get(run_id)
