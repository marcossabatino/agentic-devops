"""Durable HTTP API; only an authenticated lab user can record approval."""

from app.contracts import SCENARIOS, Rejected, uuid_text
from app.http_service import service_server
from app.server import STATIC
from app import telemetry as tel


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
                             scenarios=SCENARIOS, active_scenario=db.scenario()), 'application/json'
        authorization = headers.get('Authorization')
        if method == 'POST' and path == '/api/scenario':
            credentials.authorize(authorization, 'runs:configure')
            if not isinstance(payload, dict) or set(payload) != {'scenario'}:
                raise Rejected('INVALID_REQUEST', 400)
            return 200, {'scenario': db.scenario(payload['scenario'])}, 'application/json'
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
                run_id = uuid_text(suffix.removesuffix('/approval'))
                previous = db.get(run_id)
                with tel.span('approval.resume', parent=(previous or {}).get('trace_context'), run_id=run_id):
                    run = db.approve(run_id, payload, identity)
                return 202, run, 'application/json'
        raise Rejected('NOT_FOUND', 404)
    return service_server(dispatch, port, **transport)
