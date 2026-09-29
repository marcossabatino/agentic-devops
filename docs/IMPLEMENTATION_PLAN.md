# Implementation plan

Scope baseline: [PRD](prd.md), version 0.2. Resume evidence and pending decisions: [Progress](PROGRESS.md).

Work through one guided learning increment at a time. Before an important architectural choice, ask one focused question, discuss the answer and trade-off, and then implement the agreed increment. Close each checkpoint with executed validation evidence and the next task. A completed inspection does not imply an acceptance scenario has passed.

| Task | Status | Deliverable and validation | Acceptance criteria |
|---|---|---|---|
| T01 — Establish repository and environment baseline | Complete | Repository and QEMU baseline recorded; OpenTofu 1.10.6 installed with checksum/signature verification; real host `make doctor` passed with zero failures. Cluster compatibility verified in T04. | A01 prerequisite only |
| T02 — Minimal simulated execution | Complete locally | Local interface and deterministic read-only tool execution implemented, labeled SIMULATED. Healthy and degraded scenarios expose run ID, evidence, and outcome. A04 passed through localhost HTTP with retrieval by ID. | A04, local scope |
| T03 — Durable execution and tool contracts | Complete locally | PostgreSQL claims/leases, fenced writes, durable limits, HTTP service authentication, approval binding, and transactional simulated idempotency. 23 real-database tests passed, including the T04 separate effect owner. Distributed trace evidence for A05 remains T06. | A05 local behavior, A07 application scope, A08, A09, A10 |
| T04 — Reproducible local platform | Complete locally | Dedicated QEMU/Kubernetes 1.34.12 + Calico 3.30.3, Ansible repeat with changed=0, OpenTofu platform, Helm workloads, persistent PostgreSQL and localhost UI. Deployed scenarios and zero-change post-apply plan passed. | A01, A02, A03 |
| T05 — Network isolation | Complete locally | 22 NetworkPolicies: default-deny, cluster DNS, seven symmetric service paths. Bounded positive/negative tests and HTTP authorization over an allowed path. Telemetry-specific paths accompany T06 workloads. | A06, A07 |
| T06 — Observability and controlled failures | Complete locally | Collector/Prometheus/Tempo/Grafana deployed; 90 observability checks, six scenarios, 24 network connections and 26 PostgreSQL tests passed. Correlated logs/traces, bounded metrics, dashboard and scenario/reset commands verified. | A05, A10, A11 |
| T07 — CI and deployment provenance | Complete | Three GitHub jobs passed on PR and main; an intentional contract failure failed only its relevant job; deployment requires and exposes the exact successful main SHA and CI run. | A12 |
| T08 — Verification, cleanup, and demonstration | Pending | `make verify` report, remaining metrics/runbook tool catalog, scoped cleanup with profile/context checks, and a ten-minute demonstration guide. | A01–A13 |
| T09 — AWS integration | Deferred to M2 | Define account, region/model, budget, temporary credentials, connector egress, separate state, and OIDC scope before implementation. | A14 |

The ordering follows PRD section 13. Individual tasks may span multiple 60–90-minute learning sessions. M3 extensions remain optional and outside the current increment.

## Current learning checkpoint

The user selected QEMU for the dedicated `agentic-devops` profile. [ADR 0001](decisions/0001-qemu-lab-profile.md) records the choice, network limitations, and version-selection evidence. The existing `minikube` profile remains untouched.

T01–T07 have execution evidence in [Progress](PROGRESS.md). The deployed
platform includes separate services, persistent application storage, stable
OpenTofu state, tested network isolation and correlated observability. Standalone
T02/T03 demos remain available. [T06 guide](OBSERVABILITY_DEMO.md) describes the
six scenarios, dashboard, log/trace lookup, reset and ephemeral telemetry limits.

Next is **T08 — Verification, cleanup, and demonstration**: consolidate A01–A13,
complete the dedicated metrics/runbook tool catalog, add guarded cleanup, and
write the ten-minute demonstration. AWS remains deferred to M2.

Learning question: which evidence should `make verify` retain so a later reviewer
can distinguish a passed acceptance check from a capability that was only built?
