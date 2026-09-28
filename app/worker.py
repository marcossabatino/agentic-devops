"""Bounded worker with durable step reservations and fenced writes."""

from http.client import HTTPConnection
import json
import random
from time import monotonic, sleep
from datetime import datetime, timezone

import psycopg

from app.contracts import ARGUMENTS, READ_TOOL, RESTART_TOOL, Rejected
from app.runtime import SimulatedAdapter


class ToolClient:
    def __init__(self, port, token, host='127.0.0.1'):
        self.port, self.token, self.host = port, token, host

    def call(self, run_id, tool, timeout):
        connection = HTTPConnection(self.host, self.port, timeout=timeout)
        try:
            connection.request('POST', '/tools/execute', json.dumps({
                'run_id': str(run_id), 'tool': tool, 'arguments': ARGUMENTS,
                'idempotency_key': f'{run_id}:{tool}',
            }), {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + self.token})
            response = connection.getresponse()
            body = json.loads(response.read(65536))
            if response.status != 200:
                raise Rejected(body.get('error', 'TOOL_FAILED'), response.status)
            return body
        finally:
            connection.close()


class Worker:
    def __init__(self, db, client):
        self.db, self.client = db, client

    def once(self):
        job = self.db.claim()
        if not job:
            return False
        try:
            self.execute(job)
        except Rejected as exc:
            if exc.code != 'LEASE_LOST':
                try:
                    self.db.finish(job, 'failed', error=exc.code,
                                   summary='Execution stopped: ' + exc.code + '.')
                except Rejected as lost:
                    if lost.code != 'LEASE_LOST':
                        raise
        except psycopg.Error:
            # Leave the claim recoverable if the database becomes unavailable.
            raise
        except Exception:
            try:
                self.db.finish(job, 'failed', error='EXECUTION_FAILED',
                               summary='The simulated diagnosis could not complete.')
            except Rejected:
                pass
        return True

    def execute(self, job):
        data = job['data']
        restart = 'approval_id' in data
        tool = RESTART_TOOL if restart else READ_TOOL
        retries = 0
        while True:
            number = self.db.reserve_step(job, tool, ARGUMENTS)
            remaining = (job['deadline'] - datetime.now(timezone.utc)).total_seconds()
            if remaining <= 0:
                raise Rejected('DEADLINE_EXCEEDED', 409)
            started = monotonic()
            step = dict(step=number, tool=tool, arguments=ARGUMENTS, result=None)
            failure = None
            try:
                result = self.client.call(job['run_id'], tool,
                                          min(self.db.policy.dependency_timeout, remaining))
                step.update(status='completed', result=result)
            except (TimeoutError, OSError):
                failure = Rejected('TOOL_TIMEOUT', 503)
            except Rejected as exc:
                failure = exc
            if failure:
                step.update(status='failed', error=failure.code)
            step['duration_ms'] = round((monotonic() - started) * 1000, 3)
            self.db.record_step(job, step)
            if failure:
                if failure.status >= 500 and retries < self.db.policy.retries:
                    sleep(min(0.05 * 2 ** retries + random.uniform(0, 0.02), 0.3))
                    retries += 1
                    continue
                raise failure
            if data['scenario'] == 'step-limit':
                continue
            if data['scenario'] == 'restart-required' and not restart:
                self.db.finish(job, 'awaiting_approval', outcome='degraded',
                               pending_approval={'tool': RESTART_TOOL, 'arguments': ARGUMENTS},
                               summary='Orders is degraded. A simulated restart needs your approval.')
                return
            outcome, summary = SimulatedAdapter().summarize(result)
            if restart:
                summary = 'The approved simulated restart completed. Orders is healthy.'
            self.db.finish(job, 'completed', outcome=outcome, summary=summary)
            return

    def run(self, stop):
        while not stop.is_set():
            try:
                busy = self.once()
            except psycopg.Error:
                busy = False
            if not busy:
                stop.wait(0.1)
