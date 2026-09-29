"""Authenticated tools; restart effect and deduplication share one transaction."""

from time import sleep

from psycopg.types.json import Jsonb

from app.contracts import ARGUMENTS, READ_TOOL, RESTART_TOOL, Rejected, uuid_text
from app.http_service import service_server
from app.runtime import OrdersSimulator
from app import telemetry as tel


def validate_call(credentials, authorization, payload):
    credentials.authorize(authorization, 'tools:read')
    if not isinstance(payload, dict) or set(payload) != {'run_id', 'tool', 'arguments', 'idempotency_key'}:
        raise Rejected('INVALID_TOOL_REQUEST', 400)
    tool, arguments, key = payload['tool'], payload['arguments'], payload['idempotency_key']
    if tool not in (READ_TOOL, RESTART_TOOL) or arguments != ARGUMENTS:
        raise Rejected('INVALID_TOOL_ARGUMENTS', 400)
    run_id = uuid_text(payload['run_id'])
    if tool == RESTART_TOOL:
        credentials.authorize(authorization, 'tools:restart')
        if not isinstance(key, str) or not 1 <= len(key) <= 128:
            raise Rejected('IDEMPOTENCY_KEY_REQUIRED', 400)
    return run_id, tool, arguments, key


class DurableTools:
    def __init__(self, db, credentials):
        self.db, self.credentials = db, credentials

    def execute(self, authorization, payload):
        # Authenticate before processing tool arguments. Never trust client-supplied scopes.
        run_id, tool, arguments, key = validate_call(self.credentials, authorization, payload)
        with self.db.connect() as conn:
            row = conn.execute('SELECT data FROM jobs WHERE run_id = %s', (run_id,)).fetchone()
            if not row:
                raise Rejected('RUN_NOT_FOUND', 404)
            if tool == READ_TOOL:
                scenario = row['data']['scenario']
                if scenario in ('tool-timeout', 'deadline-exceeded'):
                    # Bounded delay, larger than the default client deadline.
                    sleep(0.75)
                    raise Rejected('TOOL_UNAVAILABLE', 503)
                state = conn.execute('SELECT restart_count FROM orders_state WHERE run_id = %s',
                                     (run_id,)).fetchone()
                healthy = scenario in ('healthy', 'step-limit') or bool(state and state['restart_count'])
                return OrdersSimulator().health('healthy' if healthy else 'orders-errors')
            # Serialize on the key as well as the approval to cover concurrent duplicates
            # and a caller reusing the same key for a different run.
            conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))', (key,))
            existing = conn.execute('SELECT * FROM tool_results WHERE idempotency_key = %s', (key,)).fetchone()
            if existing:
                if (str(existing['run_id']) != run_id or existing['tool'] != tool
                        or existing['arguments'] != arguments):
                    raise Rejected('IDEMPOTENCY_CONFLICT', 409)
                return existing['result']
            approval = conn.execute('''SELECT *, expires_at > clock_timestamp() AS valid
                FROM approvals WHERE run_id = %s FOR UPDATE''', (run_id,)).fetchone()
            if (not approval or not approval['valid'] or approval['tool'] != tool
                    or approval['arguments'] != arguments):
                raise Rejected('APPROVAL_REQUIRED')
            if approval['consumed_key'] is not None:
                raise Rejected('APPROVAL_ALREADY_USED', 409)
            active = conn.execute('''SELECT 1 FROM jobs WHERE run_id = %s
                AND status IN ('queued', 'running') AND deadline > clock_timestamp()''',
                (run_id,)).fetchone()
            if not active:
                raise Rejected('RUN_NOT_ACTIVE', 409)
            state = conn.execute('''INSERT INTO orders_state (run_id, restart_count) VALUES (%s, 1)
                ON CONFLICT (run_id) DO UPDATE SET restart_count = orders_state.restart_count + 1
                RETURNING restart_count''', (run_id,)).fetchone()
            result = {'service': 'orders', 'status': 'healthy', 'simulated': True,
                      'restart_count': state['restart_count']}
            conn.execute('''INSERT INTO tool_results
                (idempotency_key, run_id, tool, arguments, result) VALUES (%s, %s, %s, %s, %s)''',
                (key, run_id, tool, Jsonb(arguments), Jsonb(result)))
            conn.execute('UPDATE approvals SET consumed_key = %s WHERE run_id = %s', (key, run_id))
            return result

    def server(self, port=0, **transport):
        def dispatch(method, path, headers, payload):
            if method == 'POST' and path == '/tools/execute':
                run_id, tool, _, _ = validate_call(self.credentials, headers.get('Authorization'), payload)
                tel.enrich(run_id=run_id, tool=tool)
                with tel.span('tool.execute', run_id=run_id, tool=tool):
                    return 200, self.execute(headers.get('Authorization'), payload), 'application/json'
            if method == 'GET' and path == '/healthz':
                with self.db.connect() as conn:
                    conn.execute('SELECT 1')
                return 200, {'status': 'ok', 'mode': 'SIMULATED'}, 'application/json'
            raise Rejected('NOT_FOUND', 404)
        return service_server(dispatch, port, **transport)
