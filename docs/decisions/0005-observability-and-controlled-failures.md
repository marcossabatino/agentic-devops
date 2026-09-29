# ADR 0005 — Local observability and controlled failures

- Date: 2026-09-29
- Status: Accepted for local M1
- Scope: T06, continuing the stack and ownership defined in the PRD

## Decision

Keep the existing API/worker/tools/orders boundaries and propagate W3C trace
context through the persisted job and HTTP calls. Persist each run's trace ID for
lookup. Instrument bounded spans around publication, execution/claim, simulated
model decisions, dependency calls and persistence. Approval resumes the stored
trace; an unrelated inbound approval HTTP request has its own transport span.
Only validated identifiers and categorical fields enter JSON application logs.

OpenTofu manages one repository-owned Helm chart for Collector, Prometheus, Tempo
and Grafana. Digest-pinned images, resource limits, restricted pod settings,
internal Services and symmetric telemetry policies preserve the T05 boundary.
Grafana exposes anonymous Viewer access solely through a localhost port-forward.
Keep logs in Kubernetes and retrieve them by run ID; adding Loki is unnecessary
for this local acceptance increment.

Terminal run counters/histograms are computed from committed PostgreSQL history.
This avoids double-counting worker retries and survives process restarts. Tool
attempts, retries and denials use bounded-label process counters. Availability,
completed diagnosis, degraded outcome and scenario correctness are separate
signals. No run IDs, users or questions become metric labels.

Provide authenticated default-scenario selection for newly loaded UI sessions;
each run keeps an immutable scenario. Reset restores healthy and demonstrates a
healthy execution without deleting evidence. The new deadline scenario uses a
0.2-second budget with the existing bounded slow dependency. Simulated restart
still requires explicit approval.

## Consequences

Telemetry storage is ephemeral and capped. Restarting an observability pod can
remove historical traces/metrics, while durable application history survives.
Export queues and network timeouts are bounded; telemetry loss is possible and
must not prevent the diagnosis from terminating. Lab history scans are acceptable
for this single-operator demo, but require aggregation/retention for larger use.

A timeout is evidence of failed communication, not proof of NetworkPolicy
behavior. Separate positive/negative connection tests establish the policy
boundary; authenticated HTTP and dependency spans identify application failures.

## Evidence

See [observability guide](../OBSERVABILITY_DEMO.md) for reproducible commands and
[progress](../PROGRESS.md) for executed results. The acceptance verifier retrieves
traces and Prometheus queries through Grafana itself and checks the parent graph,
correlation, redaction and all controlled terminal outcomes.
