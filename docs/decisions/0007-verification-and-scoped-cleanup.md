# ADR 0007 — Consolidated verification and scoped cleanup

- Date: 2026-09-29
- Status: Accepted for local M1
- Scope: T08

## Decision

Close M1 with one local `make verify` entry point that runs the existing test and
acceptance surfaces in a fixed order and retains a machine-readable report plus
one log per step. Run bootstrap twice and require the second Ansible recap to
report zero changes. Report A01–A12 before destruction; leave A13 explicitly
NOT_RUN rather than treating the existence of cleanup code as cleanup evidence.

Require `make destroy CONFIRM=agentic-devops` for A13. Before deletion, validate
the recorded identity, exact profile name, driver, CPU, memory, network, and
Kubernetes version. If the profile is running, also validate its live
`kube-system` UID. Snapshot unrelated Minikube profiles and the global kubectl
configuration, delete only the named profile without purge, then require both
snapshots to be unchanged. Remove only project-private platform data and local
OpenTofu/Ansible runtime files. Retain sanitized evidence under ignored
`artifacts/` and promote the consolidated report to PASS only after these checks.

Complete the M1 tool catalog as explicit allowlisted operations. Health, synthetic
metrics, and runbook retrieval share the read scope; only the simulated restart
requires the restart scope, exact approval binding, and idempotency key.

## Consequences

Full verification requires the dedicated VM, host tools, network control, local
PostgreSQL binaries, and an already deployed image from a successful exact-main
CI run. It takes longer than a unit suite because it exercises real platform
boundaries. The report is local and sanitized; GitHub retains the independent CI
evidence.

Cleanup deliberately destroys the lab database, private credentials, kubeconfig,
cluster identity, and local state. Recreating the lab produces a new identity and
credentials. Global kubectl contexts, unrelated Minikube profiles, repository
source, generated acceptance evidence, and Docker cache are outside the deletion
set. A stopped matching profile can be deleted from its validated configuration;
a running profile receives the stronger live UID check.

M1 is complete without AWS. Bedrock, AWS IAM/OIDC, separate cloud state, egress,
and usage/cost evidence remain an independently authorized M2 task.
