# Final ten-minute M1 demonstration

This is the closing demonstration for the local lab. It uses the deterministic
**SIMULATED** adapter and no AWS account, credentials, resources, or model calls.
T09/Bedrock is an optional M2 extension and is not required to complete M1.

## Before the clock starts

Use a clean `main` checkout that matches `origin/main` and has a successful CI
push run. If the lab was previously removed, recreate it with:

```sh
make doctor
make bootstrap
make infra-plan
# Review the saved plan before applying it.
make infra-apply
make deploy
```

Keep `make ui` and `make dashboards` running in separate terminals. Read the
private `user_token` from `data/platform/credentials.json`; do not copy service
credentials into the browser, logs, chat, or Git.

## 0:00–2:00 — Scope and architecture

Show the architecture diagram and state the boundaries: API and worker in
`lab-app`, gateway and orders simulator in `lab-tools`, PostgreSQL in `lab-data`,
and the observability stack in `lab-observability`. All Services are internal;
browser access is a localhost port-forward. The worker uses a scripted model
adapter and has no shell, cluster-admin, AWS, or direct orders access.

## 2:00–4:00 — Diagnosis and tool catalog

In the UI, select `orders-errors` and submit “Why is orders returning errors?”.
Show the run ID and the three read-only steps:

1. `read_orders_health` returns degraded synthetic health.
2. `query_orders_metrics` returns a bounded five-minute synthetic metric set.
3. `get_orders_runbook` returns the allowlisted response procedure.

The run completes successfully with a `degraded` diagnosis. Tool arguments are
fixed to the fictional `orders` service; prompt text cannot select arbitrary
tools or arguments.

## 4:00–6:00 — Approval and idempotency

Select `restart-required`. Show that the first worker pass stops at
`awaiting_approval`; no restart count exists yet. Approve the exact displayed
tool and arguments, then show the completed simulated restart. Explain that the
orders service revalidates the approval and commits effect, approval consumption,
and idempotency result in one PostgreSQL transaction. Duplicate keys return the
stored result and do not repeat the effect.

## 6:00–8:00 — Failure, isolation, and telemetry

Run `make scenario CASE=tool-timeout`, then use its run and trace IDs in the UI,
`make logs RUN_ID=<run-uuid>`, and Grafana Explore. Show three bounded attempts,
the orders dependency in the trace, structured correlated logs, and the failure
and latency metrics. Run `make reset` when finished.

Mention that `make verify-network` proves allowed paths and policy denials with
bounded TCP checks, then separately proves HTTP authentication and authorization
over a reachable connection. NetworkPolicy and service credentials are distinct
controls.

## 8:00–9:00 — Consolidated evidence and provenance

Run or show the retained result of:

```sh
make verify
```

The command executes unit and real PostgreSQL contracts, static IaC/chart checks,
two bootstrap passes, deployed scenarios, network isolation, correlated telemetry,
the OpenTofu no-change plan, and exact CI/deployment provenance. Its ignored local
report is `artifacts/m1-verification.json`; per-step logs are under
`artifacts/verify/`. Before cleanup, A01–A12 are PASS and A13 is NOT_RUN.

## 9:00–10:00 — Scoped cleanup

Finish the lab with the explicit profile name:

```sh
make destroy CONFIRM=agentic-devops
```

The command refuses a different confirmation or mismatched profile contract. It
records the global Kubernetes contexts and every unrelated Minikube profile,
deletes only `agentic-devops`, compares the preserved state, and removes only the
lab's private kubeconfig/credentials and local OpenTofu runtime files. It writes
`artifacts/a13-cleanup.json` and changes A13 and the consolidated result to PASS.
Docker image cache and Git-tracked source remain available; the lab database is
destroyed with the dedicated VM.

To run the demonstration again, repeat the preparation commands. New local
credentials and a new cluster identity are created; the previous database and
ephemeral telemetry are intentionally not restored.
