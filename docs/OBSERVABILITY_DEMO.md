# Observability and controlled failures

T06 adds OpenTelemetry traces, JSON application logs, Prometheus metrics and a
provisioned Grafana dashboard to the dedicated `agentic-devops` lab. All diagnosis
and restart behavior remains **SIMULATED**. No model, AWS or real restart is used.

## Deploy and access

With the T04/T05 lab bootstrapped:

```sh
make setup
make infra-plan
# Inspect the saved plan before applying it.
make infra-apply
make deploy
make verify-observability
make verify-network
make dashboards
```

Open <http://127.0.0.1:3000/d/agentic-devops>. Grafana has anonymous **Viewer** access,
no login form or initial administrator, and no external Service. The port-forward
binds only to loopback. Use `DASHBOARD_PORT=3001` to select another local port.
Stop it with Ctrl+C. Run `make ui` separately for the authenticated application.

OpenTofu owns a local Helm release containing Collector, Prometheus, Tempo and
Grafana, their configuration, and 22 additional NetworkPolicies. The application
chart owns its metrics endpoints and exporter configuration. Both directions of
every permitted telemetry connection are explicit; application internet access
remains denied. Image digests are in `config/observability-images.json`.

## Exercise and correlate

```sh
make scenario CASE=healthy
make scenario CASE=orders-errors
make scenario CASE=tool-timeout
make scenario CASE=step-limit
make scenario CASE=deadline-exceeded
make reset
```

Each command selects the default for newly loaded UI sessions, creates a run,
waits for a terminal/approval state, and prints its run ID, trace ID and outcome.
It writes `artifacts/scenario-latest.json`. Existing runs retain their original
scenario and history. `make reset` selects healthy and executes a healthy run;
it does not erase history or counters. A browser already open must reload to
pick up the new default.

`CASE=restart-required` stops at `awaiting_approval`. Open the run by its ID in the
UI and explicitly approve the simulated restart. Approval and resumed execution
retain the persisted trace. The scenario command never approves on your behalf.

```sh
make logs RUN_ID=<run-uuid>
```

Use the same run's **Trace ID** in Grafana → Explore → Tempo → Trace ID. The
trace contains API publication, worker execution/claim, simulated model decisions,
tool gateway, orders dependency and database persistence. `lab.run_id` attributes
connect spans to the durable history. The deadline scenario can expire before
claiming a job; its `job.expire` span explains that terminal result.

| Scenario | Expected result | Evidence |
| --- | --- | --- |
| healthy | completed / healthy | Four services in one trace |
| orders-errors | completed / degraded | Diagnosis completed despite degraded orders |
| tool-timeout | failed / TOOL_TIMEOUT | Three calls, two retries, failed orders dependency spans |
| step-limit | failed / STEP_LIMIT | Five reserved steps, then a visible limit |
| deadline-exceeded | failed / DEADLINE_EXCEEDED | 0.2-second execution budget, durable expiry |
| restart-required | awaiting approval, then completed / healthy | Explicit approval, one simulated effect |

The dashboard separates scrape availability, diagnosis outcomes, deterministic
correctness, duration, queue depth, steps, retries, denied calls and tool errors.
Rates and percentiles require samples over time; immediately after deployment
some panels may show no data until scenarios and scrapes have occurred. Counts
and latency histograms for terminal runs derive from committed PostgreSQL jobs,
so API/worker restarts do not double-count a recovered job. Dependency counters
are process-local and reset on restart; Prometheus rates account for resets.

## Diagnose the failure boundary

A network timeout alone does not prove a policy denial. Use `make verify-network`
for a bounded negative connection test and a positive control to the same
protected destination. A reachable HTTP 401/403 indicates authentication or
scope/approval rejection; the denied-call metric distinguishes it from transport
failure. `TOOL_UNAVAILABLE` identifies a connection/OS failure, while
`TOOL_TIMEOUT` identifies a timeout. The controlled orders dependency returns a
bounded application error after the caller's timeout; its server span can finish
after the failed client span. Logs and traces expose that distinction.

## Validation and limits

`make verify-observability` checks all six scenarios, trace parent relationships,
four-service correlation, timeout bounds, required log fields, credential/prompt
redaction, all four scrape targets, metrics and provisioned dashboard queries
through Grafana's actual datasource proxies. It restores healthy in a `finally`
block and writes a PASS/FAIL report to `artifacts/t06-observability.json`, plus
sanitized traces and correlated logs. It explicitly approves only the test run
it creates to validate the approval flow.

Telemetry is intentionally disposable: Prometheus uses `emptyDir` with a 24-hour
or 256 MB retention limit; Tempo uses `emptyDir` with one-hour trace retention.
Pod replacement removes their stored telemetry. JSON logs are retained only by
Kubernetes pod logging/rotation; there is no Loki or centralized log store.
Durable run history stays in PostgreSQL. Exporting uses bounded queues/timeouts
and can lose spans if the collector is unavailable; telemetry is not an audit log.
The durable collector scans local lab history and is not sized for production.

The credentials file, private kubeconfig, plans/state and runtime artifacts stay
ignored. Logs and spans exclude questions, payloads, headers, DSNs and exception
messages. High-cardinality run/trace IDs are excluded from metric labels.
