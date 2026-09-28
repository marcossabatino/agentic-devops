"""Container entrypoints with per-service mounted credentials and no Kubernetes API access."""

import argparse
import json
import os
from pathlib import Path
import signal
from threading import Event, Thread

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

from app.api import durable_server
from app.contracts import Credentials, Rejected
from app.database import Database
from app.gateway import ToolGateway
from app.http_service import service_server
from app.tools import DurableTools
from app.worker import ToolClient, Worker


def database_dsn(config, role):
    return make_conninfo(host=os.environ.get('DATABASE_HOST', 'postgres.lab-data.svc.cluster.local'),
                         dbname='lab', user='lab_' + role, password=config['database_password'])


def migrate(config):
    with psycopg.connect(database_dsn(config, 'owner'), connect_timeout=3) as conn:
        conn.execute('REVOKE CREATE ON SCHEMA public FROM PUBLIC')
        for role, password in config['roles'].items():
            if role not in ('api', 'worker', 'tools', 'orders'):
                raise ValueError('Unexpected database role.')
            name = 'lab_' + role
            if not conn.execute('SELECT 1 FROM pg_roles WHERE rolname = %s', (name,)).fetchone():
                conn.execute(sql.SQL('CREATE ROLE {} LOGIN PASSWORD {}').format(sql.Identifier(name), sql.Literal(password)))
        for migration in sorted(Path(__file__).with_name('migrations').glob('*.sql')):
            conn.execute(migration.read_text())
    print('Database schema and restricted service grants are ready.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('component', choices=['api', 'worker', 'tools', 'orders', 'migrate'])
    args = parser.parse_args()
    config = json.loads(Path(os.environ.get('CREDENTIALS_FILE', '/var/run/lab/credentials.json')).read_text())
    if args.component == 'migrate':
        migrate(config)
        return
    role = args.component
    db = Database(database_dsn(config, role))
    transport = {'bind_address': '0.0.0.0',
                 'allowed_hosts': tuple(os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(','))}
    if role == 'api':
        auth = Credentials({'lab-user': {'token': config['user_token'], 'scopes': ['runs:create', 'runs:read', 'runs:approve']}})
        server = durable_server(db, auth, os.environ.get('SOURCE_REVISION', 'unknown'), 8080, **transport)
    elif role == 'tools':
        auth = Credentials({'agent-worker': {'token': config['worker_token'], 'scopes': ['tools:read', 'tools:restart']}})
        server = ToolGateway(db, auth, os.environ['ORDERS_HOST'], config['orders_token']).server(8080, **transport)
    elif role == 'orders':
        auth = Credentials({'tool-service': {'token': config['orders_token'], 'scopes': ['tools:read', 'tools:restart']}})
        server = DurableTools(db, auth).server(8080, **transport)
    else:
        def health(method, path, headers, payload):
            if method != 'GET' or path != '/healthz':
                raise Rejected('NOT_FOUND', 404)
            with db.connect() as conn:
                conn.execute('SELECT 1')
            return 200, {'status': 'ok'}, 'application/json'
        server = service_server(health, 8080, **transport)
    stop = Event()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: stop.set())
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(json.dumps({'service': role, 'status': 'started', 'mode': 'SIMULATED',
                      'revision': os.environ.get('SOURCE_REVISION', 'unknown')}), flush=True)
    try:
        if role == 'worker':
            Worker(db, ToolClient(8080, config['worker_token'], os.environ['TOOLS_HOST'])).run(stop)
        else:
            stop.wait()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__ == '__main__':
    main()
