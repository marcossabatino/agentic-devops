"""Durable HTTP API; only an authenticated lab user can record approval."""

from app.contracts import SCENARIOS, Rejected
from app.http_service import service_server
from app.server import STATIC


def durable_server(db, credentials, revision='unknown', port=8080, **transport):
    def dispatch(method, path, headers, payload):
        assets = {'/': ('index.html', 'text/html; charset=utf-8'),
                  '/assets/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                  '/assets/app.css': ('app.css', 'text/css; charset=utf-8')}
        if method == 'GET' and path in assets:
            name, content_type = assets[path]
            return 200, (STATIC / name).read_bytes(), content_type
        if method == 'GET' and path == '/healthz':
            with db.connect() as conn:
                conn.execute('SELECT 1')
            return 200, {'status': 'ok', 'mode': 'SIMULATED'}, 'application/json'
        if method == 'GET' and path == '/api/info':
            return 200, dict(mode='SIMULATED', revision=revision, storage='postgresql',
                             scenarios=SCENARIOS), 'application/json'
        authorization = headers.get('Authorization')
        if method == 'POST' and path == '/api/runs':
            credentials.authorize(authorization, 'runs:create')
            return 202, db.create(payload, revision), 'application/json'
        if path.startswith('/api/runs/'):
            suffix = path.removeprefix('/api/runs/')
            if method == 'GET':
                credentials.authorize(authorization, 'runs:read')
                run = db.get(suffix)
                if not run:
                    raise Rejected('RUN_NOT_FOUND', 404)
                return 200, run, 'application/json'
            if method == 'POST' and suffix.endswith('/approval'):
                identity = credentials.authorize(authorization, 'runs:approve')
                run = db.approve(suffix.removesuffix('/approval'), payload, identity)
                return 202, run, 'application/json'
        raise Rejected('NOT_FOUND', 404)
    return service_server(dispatch, port, **transport)
