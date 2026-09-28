# ADR 0002 — Local synchronous simulation for T02

Date: 2026-09-27
Status: implemented within the existing T02/T03 boundary

## Decision

Follow the implementation plan: demonstrate one complete simulated execution before
adding PostgreSQL, a durable worker, and separate services. T02 runs on localhost
in one Python process and stores at most 100 completed/failed executions in memory.
Restarting the process clears the history. The first version uses the Python
standard library and a small HTML/CSS/JavaScript interface, with no application
dependencies to install.

The execution path is API → runner → deterministic adapter → tool service → orders
simulator → summary → run store. These are code boundaries, not network isolation
boundaries. The adapter always requests the read-only `read_orders_health` tool.
It records the user's question but does not interpret it or call an LLM.

## Trade-off

This makes the run contract, tool evidence, and user interface directly observable
without waiting for infrastructure. It does not demonstrate queue recovery,
distributed execution, durable persistence, authentication, or NetworkPolicy.
The synchronous runner will evolve into a worker backed by PostgreSQL claims and
leases in T03; real service boundaries and deployment follow in T04.

The standard-library HTTP server is a local development harness. It binds only to
`127.0.0.1`, validates Host/Origin, serves a fixed asset list, and limits input size.
These controls are not a substitute for service authentication or a production
application server. There are no state-changing tools or cloud/cluster operations.

## Observable contract

- Every run has a UUID, `SIMULATED` mode, source revision, scenario, timestamps,
  duration, terminal status, tool arguments/results, summary, and error code.
- `healthy` produces a completed diagnosis with a healthy orders observation.
- `orders-errors` also produces a completed diagnosis, but reports degraded orders
  with synthetic HTTP 503 and a 35% error rate.
- A tool exception produces a failed run with `EXECUTION_FAILED`; exception text
  is not exposed.
- Run records are retrievable by ID until the process restarts or the bounded
  history evicts them. Questions are rendered as text, not HTML or commands.

## Validation boundary

`make verify-local` checks A04 through real localhost HTTP, including the health
tool evidence and retrieval by run ID. It creates and stops its own temporary
server and writes `artifacts/a04-local.json`. This is local A04 evidence, not
Kubernetes acceptance or an A01/A05–A14 pass.

T03 must add PostgreSQL, atomic job claims/leases, service identity and scopes,
approval binding, idempotency, dependency timeouts, and bounded retries. T06 owns
correlated traces/metrics; the current JSON execution log is only a starting point.
