"""Execute A04 against a temporary loopback server and record local-only evidence."""

import argparse
from datetime import datetime, timezone
from http.client import HTTPConnection
import json
from pathlib import Path
from threading import Thread
from uuid import UUID

from app.server import make_server


def request(port, method, path, payload=None):
    connection = HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        body = json.dumps(payload) if payload is not None else None
        connection.request(method, path, body, {"Content-Type": "application/json"})
        response = connection.getresponse()
        return response.status, json.loads(response.read())
    finally:
        connection.close()


def verify(port):
    status, run = request(port, "POST", "/api/runs", {
        "question": "Is the orders service healthy?", "scenario": "healthy",
    })
    checks = {
        "created": status == 201,
        "simulated": run.get("mode") == "SIMULATED",
        "completed": run.get("status") == "completed",
        "expected_outcome": run.get("outcome") == "healthy",
        "no_execution_error": run.get("error") is None,
    }
    try:
        checks["run_id"] = UUID(run["run_id"]).version == 4
        steps = run["steps"]
        checks["tool_called"] = len(steps) == 1 and steps[0]["tool"] == "read_orders_health"
        checks["tool_completed"] = steps[0]["status"] == "completed"
        observation = steps[0]["result"]
        checks["healthy_evidence"] = (
            observation["service"] == "orders" and observation["status"] == "healthy"
            and observation["http_status"] == 200 and observation["error_rate"] == 0
            and observation["simulated"] is True
        )
        fetched_status, fetched = request(port, "GET", "/api/runs/" + run["run_id"])
        checks["retrievable_record"] = fetched_status == 200 and fetched == run
    except (KeyError, ValueError, TypeError, IndexError):
        checks["valid_execution_record"] = False
    return {
        "criterion": "A04", "scope": "local in-process simulation; no Kubernetes validation",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "result": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "run": run,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/a04-local.json"))
    args = parser.parse_args()
    with make_server(0) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            report = verify(server.server_port)
        except Exception:
            report = {"criterion": "A04", "scope": "local", "result": "FAIL",
                      "error": "Local verification did not complete."}
        finally:
            server.shutdown()
            thread.join(timeout=5)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
