"""Small loopback HTTP transport for the local durable services."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from urllib.parse import urlsplit

import psycopg

from app.contracts import Rejected
from app import telemetry as tel


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False


def service_server(dispatch, port=0, bind_address='127.0.0.1', allowed_hosts=()):
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(3)

        def log_message(self, *args):
            pass

        def handle_request(self):
            if self.command == 'POST':
                route = '/tools/execute' if self.path == '/tools/execute' else '/api/runs'
                if self.path.endswith('/approval'):
                    route += '/{id}/approval'
                if self.path == '/api/scenario':
                    route = '/api/scenario'
                with tel.span('HTTP POST ' + route, parent={key.lower(): value for key, value in self.headers.items()}, kind=tel.SpanKind.SERVER):
                    self.respond()
            else:
                self.respond()

        def respond(self):
            try:
                host = self.headers.get('Host')
                hostname = urlsplit('//' + (host or '')).hostname
                if (host not in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}')
                        and hostname not in allowed_hosts):
                    raise Rejected('LOCAL_HOST_REQUIRED')
                origin = self.headers.get('Origin')
                if origin and origin != 'http://' + host:
                    raise Rejected('SAME_ORIGIN_REQUIRED')
                payload = None
                if self.command == 'POST':
                    if self.headers.get_content_type() != 'application/json':
                        raise Rejected('JSON_REQUIRED', 415)
                    if self.headers.get('Transfer-Encoding'):
                        raise Rejected('INVALID_BODY', 400)
                    try:
                        length = int(self.headers.get('Content-Length', '0'))
                    except ValueError:
                        raise Rejected('INVALID_BODY', 400) from None
                    if not 0 < length <= 8192:
                        raise Rejected('BODY_TOO_LARGE', 413)
                    raw = self.rfile.read(length)
                    if len(raw) != length:
                        raise Rejected('INVALID_BODY', 400)
                    payload = json.loads(raw)
                if self.command == 'GET' and self.path == '/livez':
                    status, body, content_type = 200, {'status': 'alive'}, 'application/json'
                else:
                    status, body, content_type = dispatch(
                        self.command, urlsplit(self.path).path, self.headers, payload)
            except Rejected as exc:
                status, body, content_type = exc.status, {'error': exc.code}, 'application/json'
            except (ValueError, UnicodeError, RecursionError):
                status, body, content_type = 400, {'error': 'INVALID_BODY'}, 'application/json'
            except TimeoutError:
                status, body, content_type = 408, {'error': 'REQUEST_TIMEOUT'}, 'application/json'
            except psycopg.Error:
                status, body, content_type = 503, {'error': 'DATABASE_UNAVAILABLE'}, 'application/json'
            except Exception:
                status, body, content_type = 500, {'error': 'INTERNAL_ERROR'}, 'application/json'
            if self.command == 'POST':
                if (isinstance(body, dict) and body.get('run_id')
                        and body.get('trace_id', tel.trace_id()) == tel.trace_id()):
                    tel.enrich(run_id=body['run_id'])
                if status >= 400:
                    code = tel.error_code(body.get('error', 'INTERNAL_ERROR'))
                    tel.enrich(status='failed', error_code=code)
                    tel.trace.get_current_span().set_status(tel.Status(tel.StatusCode.ERROR, code))
                    if status in (401, 403):
                        tel.DENIED.labels(code).inc()
            encoded = body if isinstance(body, bytes) else json.dumps(body).encode()
            try:
                self.send_response(status)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(encoded)))
                self.send_header('Cache-Control', 'no-store')
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.send_header('Referrer-Policy', 'no-referrer')
                self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; base-uri 'none'; frame-ancestors 'none'")
                self.end_headers()
                self.wfile.write(encoded)
            except (BrokenPipeError, ConnectionResetError):
                pass

        do_GET = handle_request
        do_POST = handle_request

    return LocalServer((bind_address, port), Handler)
