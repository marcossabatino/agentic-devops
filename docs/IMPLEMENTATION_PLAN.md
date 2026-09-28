# Implementation plan

Scope baseline: [PRD](prd.md), version 0.2. Resume evidence and pending decisions: [Progress](PROGRESS.md).

Work through one guided learning increment at a time. Before an important architectural choice, ask one focused question, discuss the answer and trade-off, and then implement the agreed increment. Close each checkpoint with executed validation evidence and the next task. A completed inspection does not imply an acceptance scenario has passed.

| Task | Status | Deliverable and validation | Acceptance criteria |
|---|---|---|---|
| T01 — Establish repository and environment baseline | Complete | Repository and QEMU baseline recorded; OpenTofu 1.10.6 installed with checksum/signature verification; real host `make doctor` passed with zero failures. Full cluster compatibility remains T04. | A01 prerequisite only |
| T02 — Minimal simulated execution | Complete locally | Local interface and deterministic read-only tool execution implemented, labeled SIMULATED. Healthy and degraded scenarios expose run ID, evidence, and outcome. A04 passed through localhost HTTP with retrieval by ID. | A04, local scope |
| T03 — Durable execution and tool contracts | Pending | Add PostgreSQL job claims/leases, bounded execution, service authentication, approval binding, and idempotency; verify recovery and rejected requests. | A05, A07, A08, A09, A10 |
| T04 — Reproducible local platform | Pending | Ansible bootstrap, dedicated Minikube profile with Calico, OpenTofu platform ownership, and Helm application deployment. Verify readiness, a second bootstrap, and a stable post-apply plan. | A01, A02, A03 |
| T05 — Network isolation | Pending | Default-deny policies and required flows; bounded positive and negative connectivity tests separate from authorization tests. | A06, A07 |
| T06 — Observability and controlled failures | Pending | Correlated JSON logs, metrics, traces, dashboards, scenario/reset commands, and deadline/step-limit evidence. | A05, A10, A11 |
| T07 — CI and deployment provenance | Pending | GitHub checks and image builds; intentional failure evidence; local deployment identifies the validated commit. | A12 |
| T08 — Verification, cleanup, and demonstration | Pending | `make verify` report, scoped cleanup with profile/context checks, and a ten-minute demonstration guide. | A01–A13 |
| T09 — AWS integration | Deferred to M2 | Define account, region/model, budget, temporary credentials, connector egress, separate state, and OIDC scope before implementation. | A14 |

The ordering follows PRD section 13. Individual tasks may span multiple 60–90-minute learning sessions. M3 extensions remain optional and outside the current increment.

## Current learning checkpoint

The user selected QEMU for the dedicated `agentic-devops` profile. [ADR 0001](decisions/0001-qemu-lab-profile.md) records the choice, network limitations, and version-selection evidence. The existing `minikube` profile remains untouched.

`make doctor` now passes on the host, and `make test` passes 23 tests covering preflight, execution, and HTTP contracts. `make verify-local` passes A04 within the local simulation scope. Use `make run` and the [local demonstration](LOCAL_DEMO.md) to inspect the result. [ADR 0002](decisions/0002-local-simulated-execution.md) records the synchronous in-memory boundary.

Next is T03: PostgreSQL persistence, job claims/leases, service credentials/scopes, approval, and idempotency. No Minikube cluster has been created; T04 still owns cluster/bootstrap/deployment validation. The next learning discussion is why a completed diagnosis can report a degraded service, followed by the job-claim/lease design.
