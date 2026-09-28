"""Loopback-only development HTTP interface; distributed services belong to T03/T04."""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
from urllib.parse import urlsplit

from app.runtime import MODE, SCENARIOS, Runner

STATIC = Path(__file__).with_name("static")
MAX_BODY_BYTES = 8192


def revision():
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"], cwd=STATIC.parent,
            capture_output=True, text=True, timeout=3, check=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"], cwd=STATIC.parent,
            capture_output=True, text=True, timeout=3, check=True,
        ).stdout.strip()
        return sha + ("-dirty" if dirty else "")
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def make_server(port=8080, runner=None):
    """Binding is deliberately fixed to IPv4 loopback, including in tests."""
    runtime = runner or Runner(revision=revision())

    class Handler(BaseHTTPRequestHandler):
        server_version = "AgenticDevOpsLab"

        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def log_message(self, format, *args):
            # Do not log questions or arbitrary request bodies/paths.
            pass

        def respond(self, status, body, content_type="application/json; charset=utf-8"):
            if not isinstance(body, bytes):
                body = json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy",
                             "default-src 'self'; script-src 'self'; style-src 'self'; "
                             "base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

        def allowed_host(self):
            port = self.server.server_port
            return self.headers.get("Host") in {f"127.0.0.1:{port}", f"localhost:{port}"}

        def do_GET(self):
            if not self.allowed_host():
                self.respond(403, {"error": "Local host required."})
                return
            path = urlsplit(self.path).path
            assets = {
                "/": ("index.html", "text/html; charset=utf-8"),
                "/assets/app.css": ("app.css", "text/css; charset=utf-8"),
                "/assets/app.js": ("app.js", "text/javascript; charset=utf-8"),
            }
            if path in assets:
                name, content_type = assets[path]
                self.respond(200, (STATIC / name).read_bytes(), content_type)
            elif path == "/healthz":
                self.respond(200, {"status": "ok", "mode": MODE})
            elif path == "/api/info":
                self.respond(200, {"mode": MODE, "scenarios": SCENARIOS,
                                   "revision": runtime.revision, "storage": "memory",
                                   "run_capacity": runtime.store.capacity})
            elif path.startswith("/api/runs/"):
                run = runtime.store.get(path.removeprefix("/api/runs/"))
                self.respond(200 if run else 404, run or {"error": "Run not found."})
            else:
                self.respond(404, {"error": "Not found."})

        def do_POST(self):
            if not self.allowed_host():
                self.respond(403, {"error": "Local host required."})
                return
            if self.path != "/api/runs":
                self.respond(404, {"error": "Not found."})
                return
            origin = self.headers.get("Origin")
            if origin and origin != "http://" + self.headers.get("Host", ""):
                self.respond(403, {"error": "Same-origin requests required."})
                return
            if self.headers.get_content_type() != "application/json":
                self.respond(415, {"error": "Use application/json."})
                return
            if self.headers.get("Transfer-Encoding"):
                self.respond(400, {"error": "Transfer encoding is not supported."})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self.respond(400, {"error": "Invalid Content-Length."})
                return
            if not 0 < length <= MAX_BODY_BYTES:
                self.respond(413, {"error": "Request body must contain 1–8192 bytes."})
                return
            try:
                raw = self.rfile.read(length)
                if len(raw) != length:
                    raise ValueError("Incomplete request body.")
                payload = json.loads(raw)
                run = runtime.run(payload)
            except (ValueError, UnicodeDecodeError, RecursionError):
                self.respond(400, {"error": "Invalid request. Provide a question (1–1000 characters) and a supported scenario."})
                return
            except TimeoutError:
                self.respond(408, {"error": "Request body timed out."})
                return
            # A diagnosis may complete successfully and report a degraded service.
            self.respond(201, run)
            print(json.dumps({
                "timestamp": run["finished_at"], "service": "local-api", "mode": MODE,
                "run_id": run["run_id"], "status": run["status"], "outcome": run["outcome"],
                "duration_ms": run["duration_ms"], "revision": runtime.revision,
            }), flush=True)

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main():
    parser = argparse.ArgumentParser(description="Run the local SIMULATED diagnosis lab.")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    with make_server(args.port) as server:
        print(f"SIMULATED lab: http://127.0.0.1:{server.server_port} (Ctrl+C to stop)", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
