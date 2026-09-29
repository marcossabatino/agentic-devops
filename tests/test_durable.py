"""Integration contracts against a disposable real PostgreSQL instance."""

from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import Thread
import time
import unittest

ENABLED = os.environ.get('LAB_POSTGRES_TESTS') == '1'
if ENABLED:
    import psycopg
    from app.api import durable_server
    from app.contracts import ARGUMENTS, READ_TOOL, RESTART_TOOL, Credentials, Policy, Rejected
    from app.database import Database
    from app.tools import DurableTools
    from app.worker import ToolClient, Worker
    from scripts.durable_demo import credentials
    from scripts.local_database import local_database


@unittest.skipUnless(ENABLED, 'Use make verify-durable for real PostgreSQL integration tests.')
class DurableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='agentic-devops-tests-')
        cls.cluster = local_database(cls.temp.name)
        cls.dsns, cls.config = cls.cluster.__enter__()
        cls.auth = credentials(cls.config)
        cls.auth.entries['read-only-worker'] = {'token': 'r' * 40, 'scopes': ['tools:read']}
        cls.api_db = Database(cls.dsns['api'])
        cls.tool_service = DurableTools(Database(cls.dsns['tools']), cls.auth)
        cls.tool_server = cls.tool_service.server()
        cls.api_server = durable_server(cls.api_db, cls.auth, revision='integration-test', port=0)
        cls.threads = []
        for server in (cls.tool_server, cls.api_server):
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            cls.threads.append(thread)

    @classmethod
    def tearDownClass(cls):
        for server in (cls.api_server, cls.tool_server):
            server.shutdown()
            server.server_close()
        for thread in cls.threads:
            thread.join(timeout=5)
        cls.cluster.__exit__(None, None, None)
        cls.temp.cleanup()

    def setUp(self):
        with psycopg.connect(self.dsns['owner']) as conn:
            conn.execute('TRUNCATE jobs, events, approvals, tool_results, orders_state RESTART IDENTITY')
        self.db = Database(self.dsns['worker'])
        self.worker = Worker(self.db, ToolClient(self.tool_server.server_port, self.config['worker_token']))

    def sql(self, query, params=()):
        with psycopg.connect(self.dsns['owner']) as conn:
            cursor = conn.execute(query, params)
            return cursor.fetchall() if cursor.description else None

    def create(self, scenario='healthy', db=None):
        return (db or self.api_db).create({'question': 'Diagnose orders', 'scenario': scenario}, 'test')

    def http(self, server, path, payload=None, token=None, extra=None):
        conn = HTTPConnection('127.0.0.1', server.server_port, timeout=3)
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        headers.update(extra or {})
        try:
            conn.request('POST' if payload is not None else 'GET', path,
                         json.dumps(payload) if payload is not None else None, headers)
            response = conn.getresponse()
            return response.status, json.loads(response.read())
        finally:
            conn.close()

    def tool_payload(self, run_id, tool=RESTART_TOOL if ENABLED else '', key='restart-key'):
        return dict(run_id=run_id, tool=tool, arguments=ARGUMENTS, idempotency_key=key)

    def pending(self):
        run = self.create('restart-required')
        self.worker.once()
        current = self.api_db.get(run['run_id'])
        self.assertEqual(current['status'], 'awaiting_approval')
        return current

    def approved(self):
        run = self.pending()
        return self.api_db.approve(run['run_id'], run['pending_approval'], 'lab-user')

    def test_a04_async_http_and_retrieval(self):
        status, run = self.http(self.api_server, '/api/runs',
                                {'question': 'Health?', 'scenario': 'healthy'}, self.config['user_token'])
        self.assertEqual(status, 202)
        self.assertEqual(run['status'], 'queued')
        self.worker.once()
        status, result = self.http(self.api_server, '/api/runs/' + run['run_id'], token=self.config['user_token'])
        self.assertEqual(status, 200)
        self.assertEqual((result['status'], result['outcome']), ('completed', 'healthy'))
        self.assertEqual(result['steps'][0]['result']['http_status'], 200)
        self.assertEqual([e['kind'] for e in result['events']], ['claimed', 'tool_started', 'tool_completed', 'completed'])

    def test_degraded_diagnosis_completes(self):
        run = self.create('orders-errors')
        self.worker.once()
        result = self.api_db.get(run['run_id'])
        self.assertEqual((result['status'], result['outcome']), ('completed', 'degraded'))

    def test_a07_authentication_and_scope_on_reachable_tool(self):
        run = self.create()
        for token, expected in ((None, 401), ('incorrect', 401), (self.config['user_token'], 403)):
            with self.subTest(expected=expected, token_type=bool(token)):
                status, _ = self.http(self.tool_server, '/tools/execute',
                                       self.tool_payload(run['run_id'], READ_TOOL), token)
                self.assertEqual(status, expected)
        status, _ = self.http(self.tool_server, '/tools/execute',
                               self.tool_payload(run['run_id'], READ_TOOL), self.config['worker_token'])
        self.assertEqual(status, 200)
        status, _ = self.http(self.tool_server, '/tools/execute', self.tool_payload(run['run_id']), 'r' * 40)
        self.assertEqual(status, 403)

    def test_api_authentication_and_worker_cannot_approve(self):
        run = self.pending()
        path = '/api/runs/' + run['run_id']
        self.assertEqual(self.http(self.api_server, path)[0], 401)
        self.assertEqual(self.http(self.api_server, path + '/approval', run['pending_approval'], self.config['worker_token'])[0], 403)
        self.assertEqual(self.http(self.api_server, path + '/approval', run['pending_approval'], self.config['user_token'])[0], 202)
        self.assertEqual(self.sql('SELECT approved_by FROM approvals')[0][0], 'lab-user')

    def test_a08_approval_binding_and_restart(self):
        run = self.pending()
        payload = self.tool_payload(run['run_id'])
        self.assertEqual(self.http(self.tool_server, '/tools/execute', payload, self.config['worker_token'])[0], 403)
        path = '/api/runs/' + run['run_id'] + '/approval'
        changed = {'tool': RESTART_TOOL, 'arguments': {'service': 'production'}}
        self.assertEqual(self.http(self.api_server, path, changed, self.config['user_token'])[0], 409)
        self.assertEqual(self.sql('SELECT count(*) FROM orders_state')[0][0], 0)
        self.assertEqual(self.http(self.api_server, path, run['pending_approval'], self.config['user_token'])[0], 202)
        self.worker.once()
        result = self.api_db.get(run['run_id'])
        self.assertEqual((result['status'], result['outcome']), ('completed', 'healthy'))
        self.assertEqual(self.sql('SELECT restart_count FROM orders_state')[0][0], 1)

    def test_changed_tool_arguments_and_run_cannot_use_approval(self):
        approved = self.approved()
        other = self.create()
        payload = self.tool_payload(approved['run_id'])
        payload['arguments'] = {'service': 'production'}
        self.assertEqual(self.http(self.tool_server, '/tools/execute', payload, self.config['worker_token'])[0], 400)
        payload = self.tool_payload(other['run_id'])
        self.assertEqual(self.http(self.tool_server, '/tools/execute', payload, self.config['worker_token'])[0], 403)
        payload['tool'] = 'shell'
        self.assertEqual(self.http(self.tool_server, '/tools/execute', payload, self.config['worker_token'])[0], 400)
        self.assertEqual(self.sql('SELECT count(*) FROM orders_state')[0][0], 0)

    def test_a09_concurrent_duplicate_requests_have_one_effect(self):
        run = self.approved()
        payload = self.tool_payload(run['run_id'])
        def call(_):
            return self.http(self.tool_server, '/tools/execute', payload, self.config['worker_token'])
        with ThreadPoolExecutor(max_workers=8) as pool:
            replies = list(pool.map(call, range(8)))
        self.assertTrue(all(status == 200 for status, _ in replies), replies)
        self.assertTrue(all(body == replies[0][1] for _, body in replies))
        self.assertEqual(self.sql('SELECT restart_count FROM orders_state')[0][0], 1)
        self.assertEqual(self.sql('SELECT count(*) FROM tool_results')[0][0], 1)
        payload['idempotency_key'] = 'another-key'
        self.assertEqual(self.http(self.tool_server, '/tools/execute', payload, self.config['worker_token'])[0], 409)
        payload = self.tool_payload(self.create()['run_id'])
        self.assertEqual(self.http(self.tool_server, '/tools/execute', payload, self.config['worker_token'])[0], 409)

    def test_expired_approval_cannot_change_state(self):
        run = self.approved()
        self.sql("UPDATE approvals SET expires_at = clock_timestamp() - interval '1 second'")
        self.assertEqual(self.http(self.tool_server, '/tools/execute', self.tool_payload(run['run_id']), self.config['worker_token'])[0], 403)
        self.assertEqual(self.sql('SELECT count(*) FROM orders_state')[0][0], 0)

    def test_expired_run_cannot_execute_approved_effect(self):
        run = self.approved()
        self.sql("UPDATE jobs SET deadline = clock_timestamp() - interval '1 second'")
        status, body = self.http(self.tool_server, '/tools/execute',
                                 self.tool_payload(run['run_id']), self.config['worker_token'])
        self.assertEqual((status, body['error']), (409, 'RUN_NOT_ACTIVE'))
        self.assertEqual(self.sql('SELECT count(*) FROM orders_state')[0][0], 0)

    def test_bearer_scheme_is_required_and_secrets_are_not_returned(self):
        run = self.create()
        status, body = self.http(self.tool_server, '/tools/execute',
                                 self.tool_payload(run['run_id'], READ_TOOL),
                                 extra={'Authorization': self.config['worker_token']})
        self.assertEqual(status, 401)
        self.assertNotIn(self.config['worker_token'], json.dumps(body))

    def test_total_deadline_bounds_retries_and_is_reaped(self):
        policy = Policy(deadline_seconds=0.3, lease_seconds=0.2,
                        dependency_timeout=0.1, retries=5)
        run = self.create('tool-timeout', Database(self.dsns['api'], policy))
        worker = Worker(Database(self.dsns['worker'], policy), self.worker.client)
        started = time.monotonic()
        worker.once()
        time.sleep(0.1)
        worker.once()
        result = self.api_db.get(run['run_id'])
        self.assertEqual((result['status'], result['error']), ('failed', 'DEADLINE_EXCEEDED'))
        self.assertLess(time.monotonic() - started, 2)
        self.assertLessEqual(result['step_count'], 3)
        time.sleep(0.8)  # Release the bounded delayed handlers before database teardown.

    def test_pending_approval_expires_separately(self):
        run = self.pending()
        self.sql("UPDATE jobs SET deadline = clock_timestamp() - interval '1 second'")
        self.assertFalse(self.worker.once())
        self.assertEqual(self.api_db.get(run['run_id'])['error'], 'APPROVAL_EXPIRED')
        with self.assertRaises(Rejected):
            self.api_db.approve(run['run_id'], run['pending_approval'], 'lab-user')

    def test_claim_is_atomic_with_competing_workers(self):
        run = self.create()
        with ThreadPoolExecutor(max_workers=8) as pool:
            jobs = list(pool.map(lambda _: self.db.claim(), range(8)))
        claimed = [job for job in jobs if job]
        self.assertEqual(len(claimed), 1)
        self.assertEqual(str(claimed[0]['run_id']), run['run_id'])

    def test_lease_recovery_fences_old_worker_and_retains_step_budget(self):
        run = self.create('step-limit')
        old = self.db.claim()
        self.db.reserve_step(old, READ_TOOL, ARGUMENTS)
        self.sql("UPDATE jobs SET lease_until = clock_timestamp() - interval '1 second'")
        recovered = self.db.claim()
        self.assertNotEqual(old['lease_token'], recovered['lease_token'])
        self.assertEqual(recovered['step_count'], 1)
        with self.assertRaises(Rejected) as rejected:
            self.db.finish(old, 'completed', outcome='healthy')
        self.assertEqual(rejected.exception.code, 'LEASE_LOST')
        with self.assertRaises(Rejected) as rejected:
            self.worker.execute(recovered)
        self.assertEqual(rejected.exception.code, 'STEP_LIMIT')
        self.assertEqual(self.api_db.get(run['run_id'])['step_count'], 5)

    def test_killed_claiming_process_is_recovered(self):
        run = self.create()
        child_code = '''import os, time
from app.database import Database
from app.contracts import Policy
db = Database(os.environ['TEST_CLAIM_DSN'], Policy(lease_seconds=0.15, dependency_timeout=0.05))
assert db.claim()
print('claimed', flush=True)
time.sleep(30)
'''
        child = subprocess.Popen([sys.executable, '-B', '-c', child_code], stdout=subprocess.PIPE,
                                 text=True, env={**os.environ, 'TEST_CLAIM_DSN': self.dsns['worker']})
        try:
            import selectors
            with selectors.DefaultSelector() as selector:
                selector.register(child.stdout, selectors.EVENT_READ)
                self.assertTrue(selector.select(timeout=5), 'Claiming process did not report readiness')
            self.assertEqual(child.stdout.readline().strip(), 'claimed')
        finally:
            child.terminate()
            child.wait(timeout=5)
            child.stdout.close()
        time.sleep(0.2)
        self.worker.once()
        result = self.api_db.get(run['run_id'])
        self.assertEqual((result['status'], result['attempts']), ('completed', 2))

    def test_lost_response_after_effect_recovers_without_duplicate(self):
        run = self.approved()
        old = self.db.claim()
        self.db.reserve_step(old, RESTART_TOOL, ARGUMENTS)
        # Tool commits, then worker disappears before recording the response.
        self.worker.client.call(run['run_id'], RESTART_TOOL, 1)
        self.sql("UPDATE jobs SET lease_until = clock_timestamp() - interval '1 second'")
        self.worker.once()
        self.assertEqual(self.api_db.get(run['run_id'])['status'], 'completed')
        self.assertEqual(self.sql('SELECT restart_count FROM orders_state')[0][0], 1)

    def test_a05_tool_timeout_has_bounded_retries(self):
        run = self.create('tool-timeout')
        start = time.monotonic()
        self.worker.once()
        elapsed = time.monotonic() - start
        result = self.api_db.get(run['run_id'])
        self.assertEqual((result['status'], result['error']), ('failed', 'TOOL_TIMEOUT'))
        self.assertEqual(result['step_count'], 3)
        self.assertLess(elapsed, 5)
        self.assertTrue(all(step['error'] == 'TOOL_TIMEOUT' for step in result['steps']))
        time.sleep(0.3)  # Let bounded delayed tool handlers release their database connections.

    def test_a10_step_limit_is_visible(self):
        run = self.create('step-limit')
        self.worker.once()
        result = self.api_db.get(run['run_id'])
        self.assertEqual((result['status'], result['error']), ('failed', 'STEP_LIMIT'))
        self.assertEqual(result['step_count'], 5)
        self.assertEqual(len(result['steps']), 5)

    def test_scenario_selection_requires_scope_and_preserves_existing_runs(self):
        run = self.create()
        path = '/api/scenario'
        self.assertEqual(self.http(self.api_server, path, {'scenario': 'tool-timeout'})[0], 401)
        self.assertEqual(self.http(self.api_server, path, {'scenario': 'tool-timeout'}, self.config['worker_token'])[0], 403)
        self.assertEqual(self.http(self.api_server, path, {'scenario': 'unknown'}, self.config['user_token'])[0], 400)
        for scenario in ('tool-timeout', 'healthy'):
            self.assertEqual(self.http(self.api_server, path, {'scenario': scenario}, self.config['user_token'])[0], 200)
            self.assertEqual(self.http(self.api_server, '/api/info')[1]['active_scenario'], scenario)
        self.assertEqual(self.api_db.get(run['run_id'])['scenario'], 'healthy')

    def test_named_deadline_scenario_terminates(self):
        run = self.create('deadline-exceeded')
        self.worker.once()
        time.sleep(0.25)
        self.worker.once()
        result = self.api_db.get(run['run_id'])
        self.assertEqual((result['status'], result['error']), ('failed', 'DEADLINE_EXCEEDED'))
        self.assertLessEqual(result['step_count'], 1)
        time.sleep(0.8)

    def test_trace_survives_queue_and_http_without_sensitive_content(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
        from app import telemetry as tel
        exporter = InMemorySpanExporter()
        tel.PROVIDER.add_span_processor(SimpleSpanProcessor(exporter))
        output = StringIO()
        question = 'private-prompt-marker-do-not-export'
        try:
            with redirect_stdout(output):
                status, run = self.http(self.api_server, '/api/runs',
                                        {'question': question, 'scenario': 'healthy'}, self.config['user_token'])
                self.assertEqual(status, 202)
                self.worker.once()
            spans = exporter.get_finished_spans()
            self.assertTrue(spans)
            self.assertEqual({format(s.context.trace_id, '032x') for s in spans}, {run['trace_id']})
            self.assertTrue({'job.publish', 'job.execute', 'model.decide', 'tools.call',
                             'tool.execute', 'step.persist', 'job.persist'} <= {s.name for s in spans})
            span_ids = {s.context.span_id for s in spans}
            self.assertTrue(all(s.parent is None or s.parent.span_id in span_ids for s in spans))
            serialized = output.getvalue() + ''.join(s.to_json() for s in spans)
            for secret in (question, self.config['user_token'], self.config['worker_token'], self.dsns['api']):
                self.assertNotIn(secret, serialized)
            records = [json.loads(line) for line in output.getvalue().splitlines()]
            self.assertTrue(all(r['trace_id'] == run['trace_id'] for r in records))
        finally:
            exporter.clear()

    def test_deadline_and_exhausted_claims_become_terminal(self):
        run = self.create()
        self.sql("UPDATE jobs SET deadline = clock_timestamp() - interval '1 second'")
        self.assertFalse(self.worker.once())
        self.assertEqual(self.api_db.get(run['run_id'])['error'], 'DEADLINE_EXCEEDED')
        run = self.create()
        self.db.claim()
        self.sql("UPDATE jobs SET attempts = max_attempts, lease_until = clock_timestamp() - interval '1 second' WHERE run_id = %s", (run['run_id'],))
        self.assertFalse(self.worker.once())
        self.assertEqual(self.api_db.get(run['run_id'])['error'], 'ATTEMPTS_EXHAUSTED')

    def test_database_roles_cannot_cross_sensitive_boundaries(self):
        denied = [('worker', "INSERT INTO approvals (approval_id) VALUES (gen_random_uuid())"),
                  ('api', 'SELECT * FROM orders_state'),
                  ('tools', "UPDATE jobs SET status = 'completed'"),
                  ('worker', 'UPDATE orders_state SET restart_count = 100'),
                  ('tools', "UPDATE approvals SET approved_by = 'forged'")]
        for role, query in denied:
            with self.subTest(role=role, query=query), psycopg.connect(self.dsns[role]) as conn:
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    conn.execute(query)
                conn.rollback()

    def test_invalid_requests_and_cross_origin_do_not_create_jobs(self):
        payload = {'question': 'Check', 'scenario': 'healthy', 'scope': 'admin'}
        self.assertEqual(self.http(self.api_server, '/api/runs', payload, self.config['user_token'])[0], 400)
        payload.pop('scope')
        self.assertEqual(self.http(self.api_server, '/api/runs', payload, self.config['user_token'], {'Origin': 'https://unrelated.example'})[0], 403)
        self.assertEqual(self.sql('SELECT count(*) FROM jobs')[0][0], 0)
        self.assertEqual(self.http(self.api_server, '/api/runs/not-a-uuid', token=self.config['user_token'])[0], 400)

    def test_gateway_separates_effect_owner_and_rejects_direct_worker(self):
        from psycopg import sql
        from psycopg.conninfo import make_conninfo
        from app.gateway import ToolGateway
        run = self.approved()
        orders_password = 'ephemeral-test-password-for-orders-role'
        with psycopg.connect(self.dsns['owner']) as conn:
            conn.execute(sql.SQL('CREATE ROLE lab_orders LOGIN PASSWORD {}').format(sql.Literal(orders_password)))
            conn.execute(Path('app/migrations/002_orders_owner.sql').read_text())
        orders_db = Database(make_conninfo(self.dsns['owner'], user='lab_orders', password=orders_password))
        orders_token = 'orders-service-only-test-token-' + 'x' * 16
        orders_auth = Credentials({'tool-service': {'token': orders_token, 'scopes': ['tools:read', 'tools:restart']}})
        orders = DurableTools(orders_db, orders_auth).server()
        gateway = ToolGateway(Database(self.dsns['tools']), self.auth, '127.0.0.1', orders_token, orders.server_port).server()
        threads = [Thread(target=server.serve_forever, daemon=True) for server in (orders, gateway)]
        for thread in threads:
            thread.start()
        try:
            payload = self.tool_payload(run['run_id'])
            self.assertEqual(self.http(orders, '/tools/execute', payload, self.config['worker_token'])[0], 401)
            self.assertEqual(self.http(gateway, '/tools/execute', payload, orders_token)[0], 401)
            with ThreadPoolExecutor(max_workers=4) as pool:
                replies = list(pool.map(lambda _: self.http(gateway, '/tools/execute', payload, self.config['worker_token']), range(4)))
            self.assertTrue(all(status == 200 for status, _ in replies), replies)
            self.assertEqual(self.sql('SELECT restart_count FROM orders_state')[0][0], 1)
            with psycopg.connect(self.dsns['tools']) as conn:
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    conn.execute('UPDATE orders_state SET restart_count = 100')
                conn.rollback()
            other = self.create()
            self.assertEqual(self.http(gateway, '/tools/execute', self.tool_payload(other['run_id'], key='unapproved'), self.config['worker_token'])[0], 403)
        finally:
            for server in (gateway, orders):
                server.shutdown()
                server.server_close()
            for thread in threads:
                thread.join(timeout=5)
            with psycopg.connect(self.dsns['owner']) as conn:
                conn.execute(Path('app/migrations/001_durable.sql').read_text())


@unittest.skipUnless(ENABLED, 'Use make verify-durable for real PostgreSQL integration tests.')
class PersistenceTests(unittest.TestCase):
    def test_database_restart_preserves_history_and_idempotency(self):
        with tempfile.TemporaryDirectory(prefix='agentic-devops-persistence-') as directory:
            with local_database(directory) as (dsns, config):
                api = Database(dsns['api'])
                worker_db = Database(dsns['worker'])
                run = api.create({'question': 'Restart?', 'scenario': 'restart-required'}, 'test')
                job = worker_db.claim()
                worker_db.finish(job, 'awaiting_approval', pending_approval={'tool': RESTART_TOOL, 'arguments': ARGUMENTS})
                api.approve(run['run_id'], {'tool': RESTART_TOOL, 'arguments': ARGUMENTS}, 'lab-user')
                payload = dict(run_id=run['run_id'], tool=RESTART_TOOL, arguments=ARGUMENTS, idempotency_key='persisted-key')
                auth = 'Bearer ' + config['worker_token']
                before = DurableTools(Database(dsns['tools']), credentials(config)).execute(auth, payload)
            with local_database(directory) as (dsns, config):
                self.assertEqual(Database(dsns['api']).get(run['run_id'])['run_id'], run['run_id'])
                after = DurableTools(Database(dsns['tools']), credentials(config)).execute(auth, payload)
                self.assertEqual(before, after)
                self.assertEqual(after['restart_count'], 1)
                self.assertEqual(Path(directory, 'settings.json').stat().st_mode & 0o777, 0o600)
