# T02 local demonstration

## Start and inspect

From the repository root, with Python 3.11+ and GNU Make:

```sh
make test
make verify-local
make run
```

Open <http://127.0.0.1:8080>. To use another port, run `make run PORT=8081`.
Stop the application with Ctrl+C. No Minikube profile is started or modified.

1. Confirm the **SIMULATED** badge. The adapter uses scripted behavior, not an LLM.
2. Choose **Healthy service** and submit a question. The question is recorded;
   it does not change the fixed tool-selection logic.
3. Confirm execution `completed`, orders outcome `healthy`, a unique run ID,
   and a `read_orders_health` tool call with HTTP 200 and zero error rate.
4. Expand **Full execution record** to inspect the question, scenario, timestamps,
   arguments, tool result, duration, and source revision.
5. Choose **Service returning errors** and run again. Execution still completes,
   but the orders outcome is `degraded`, with HTTP 503 and a 35% synthetic error rate.
6. Restart the process. Previous IDs are no longer available: storage is temporary
   and bounded to the latest 100 completed/failed runs.

## HTTP interface

```sh
curl --fail-with-body http://127.0.0.1:8080/api/info
curl --fail-with-body http://127.0.0.1:8080/api/runs \
  -H 'Content-Type: application/json' \
  -d '{"question":"Is the orders service healthy?","scenario":"healthy"}'
```

Use the returned `run_id` in `GET /api/runs/<run_id>` to fetch its record. A missing
or evicted ID returns 404. The allowed scenarios are `healthy` and `orders-errors`.
Questions must contain 1–1000 characters and the API accepts only the `question`
and `scenario` fields. There is no restart/action endpoint.

## Evidence and limits

`make verify-local` starts an independent ephemeral localhost server, executes the
healthy scenario, checks the outcome/tool/UUID/retrieval, stops the server, and
writes `artifacts/a04-local.json`. The report contains the run and individual
checks. It exits nonzero on failure. Raw artifacts are ignored by Git; checkpoint
evidence is summarized in [PROGRESS.md](PROGRESS.md).

The application and tests use only Python's standard library. Tests that bind a
localhost socket need an execution environment that allows local networking.
`make doctor` additionally needs host visibility for KVM and the platform tools.

This increment is synchronous, in memory, and unauthenticated for the local lab
user. It does not yet validate persistence, job leases, service authorization,
approval, idempotency, Kubernetes networking, or telemetry correlation. Those
remain explicit tasks in the [implementation plan](IMPLEMENTATION_PLAN.md).

Learning question: why can an execution be `completed` while the diagnosed service
is `degraded`, and which of those signals should each dashboard measure?
