# T03 durable local demonstration

This mode uses a private native PostgreSQL cluster and authenticated localhost
HTTP. It does not create a VM or contact Kubernetes or AWS. The T02 demo is still
available through `make run` without Python dependencies.

## Start

Prerequisites: Python 3.11+, PostgreSQL 16 tools (`initdb`, `postgres`, `pg_ctl`),
and GNU Make. PostgreSQL 16.13 and Python 3.13.13 were used for validation.
Run as your normal user; `initdb` must not run as root.

```sh
make setup
make verify-durable
make run-durable
```

Open <http://127.0.0.1:8080>. The startup message identifies
`data/t03/settings.json`. Locally copy **only `user_token`** from that file into
the password field in the interface. Do not paste it into chat, commit it, or
share the file: it also contains local database and worker credentials.

Credentials and database data are generated under the ignored `data/t03/`
directory with restrictive permissions. They survive Ctrl+C and the next launch.
The browser retains the token only until the page closes or reloads.
`make run-durable PORT=8081` selects a different interface port.

## Exercise the scenarios

1. **Healthy service:** execution moves from queued/running to completed, with a
   healthy outcome, HTTP 200 tool evidence, a run ID, and durable events.
2. **Service returning errors:** execution completes with a degraded outcome and
   synthetic HTTP 503 evidence. This is a successful diagnosis of a failure.
3. **Service needs a simulated restart:** execution reaches `awaiting_approval`.
   Inspect the run ID and exact `restart_orders` / `{"service":"orders"}` action.
   Click **Approve simulated restart**. The worker resumes and records one
   simulated restart, then completes with a healthy outcome. No real service
   restarts. Doing nothing allows the approval request to expire.
4. **Tool unavailable / timeout:** three bounded attempts fail with `TOOL_TIMEOUT`.
5. **Repeated tool requests / step limit:** five calls end with `STEP_LIMIT`.

The raw execution record includes steps, attempts, durable events, and errors.
Keep a run ID, stop with Ctrl+C, and launch again. Its authenticated API record
remains available after the application and database restart. There is no history
list or resume-by-ID form in this increment.

## API contract

Use `Authorization: Bearer <user_token>` for the following routes. Do not put
credentials in URLs or command history; read the local settings file in a client.

| Method and route | Body | Result |
| --- | --- | --- |
| `POST /api/runs` | `{"question":"Check orders","scenario":"healthy"}` | 202, queued run |
| `GET /api/runs/{run_id}` | None | 200, durable status, steps and events |
| `POST /api/runs/{run_id}/approval` | Exact `pending_approval` from the run | 202, approved and queued |
| `GET /api/info` | None; public | Mode, revision, PostgreSQL storage, scenarios |
| `GET /healthz` | None; public | API/database readiness |

Example of retrieving an existing run without exposing the credential:

```sh
.venv/bin/python - EXISTING_RUN_ID <<'PY'
import json
from pathlib import Path
import sys
from urllib.request import Request, urlopen
settings = json.loads(Path('data/t03/settings.json').read_text())
request = Request('http://127.0.0.1:8080/api/runs/' + sys.argv[1],
                  headers={'Authorization': 'Bearer ' + settings['user_token']})
with urlopen(request, timeout=3) as response:
    print(json.dumps(json.load(response), indent=2))
PY
```

The private tool HTTP service requires worker scopes. It accepts only
`read_orders_health`, `query_orders_metrics`, `get_orders_runbook`, and
`restart_orders`, with exact orders arguments. The first three are read-only;
the degraded diagnosis records them in that order. Restart additionally requires
the restart scope, an unexpired bound approval, and an idempotency key.
Two identical authorized requests return the same stored result with one effect.
Reusing the approval with another key or using the key for another run fails.

## Limits and verification

Defaults: five total steps, three total claims, 30-second execution deadline,
three-second lease, 0.5-second dependency timeout, two retries, 300-second approval
window. Queue wait counts toward the execution deadline; human approval has its
own window and grants a fresh execution deadline. Steps and claims never reset.

```sh
.venv/bin/python -m scripts.durable_demo --help
.venv/bin/python -m scripts.durable_demo --max-steps 3 --deadline 15
```

`make verify-durable` creates disposable databases in private temporary
directories, runs the real integration contracts, shuts the databases down, and
writes the sanitized `artifacts/t03-durable.json` report. Missing dependencies or
failed/skipped integration checks produce a nonzero exit. `make test` keeps the
standard-library regression suite and explicitly skips the PostgreSQL tests;
run both commands for full local verification. Sandboxes that deny sockets must
allow the local test processes to run on the host.

`Ctrl+C` stops the demo's HTTP services, worker, and its database; persistent data
is retained. Restarting the demo reclaims abandoned jobs after lease expiration.
Do not launch two demos against the same data directory. For an independent
experiment, pass a separate `--data` directory.

The launcher owns only its dedicated PostgreSQL directory and temporary socket.
It never stops another cluster or changes a Kubernetes context. Full lab cleanup
and Kubernetes deployment belong to later tasks.
