# Progress

## Last verified checkpoint — T08 / local M1, 2026-09-29

**T08 and local M1 are complete without AWS.** The final increment completes the
allowlisted diagnostic tool catalog, consolidates A01–A12 under `make verify`,
and executes A13 through guarded deletion of the dedicated lab profile. Bedrock
and all AWS controls remain an optional, separately authorized M2/T09 increment.

### Delivered

- `query_orders_metrics` and `get_orders_runbook` join `read_orders_health` as
  authenticated read-only tools. The degraded scenario records all three steps,
  including bounded five-minute synthetic metrics and the allowlisted response
  procedure. The existing restart path retains its distinct scope, approval
  binding and transactional idempotency.
- `make verify` runs preflight, standard tests, cluster-free IaC/chart checks,
  bootstrap twice, real PostgreSQL contracts, live cluster scenarios, network
  isolation and correlated observability. It requires the second Ansible recap
  to have zero changes and writes `artifacts/m1-verification.json` plus per-step
  logs. A01–A12 must pass; A13 stays visibly NOT_RUN until teardown executes.
- `make destroy CONFIRM=agentic-devops` validates the recorded target and pinned
  profile configuration, checks the live cluster UID when running, snapshots
  unrelated Minikube profiles and the global kubectl configuration, deletes only
  the named profile, and requires those snapshots to remain equal. Only private
  platform data and local OpenTofu/Ansible runtime files are then removed.
- The [final ten-minute demonstration](FINAL_DEMO.md),
  [ADR 0007](decisions/0007-verification-and-scoped-cleanup.md), refreshed HLD,
  architecture artwork, platform guide, task plan and README close local M1.

### Executed evidence

- The real PostgreSQL suite passed all **26 tests** with no skips, including the
  new three-tool degraded diagnosis and the existing authorization, approval,
  concurrency, idempotency, recovery, deadline and step-limit contracts.
- `make verify` completed every step and retained PASS evidence for A01–A12. The
  live deployment matched the exact successful `main` CI push revision; the
  deployed degraded scenario used health, metrics and runbook in that order.
- Guarded cleanup removed only the `agentic-devops` profile. The unrelated
  `minikube` profile and the host's Kubernetes contexts were canonically
  identical before and after deletion. The cleanup
  report promoted A13 and the consolidated M1 result to **PASS**.

Generated evidence remains ignored under `artifacts/`, including
`m1-verification.json`, `verify/*.log`, and `a13-cleanup.json`. Cleanup removes
the private kubeconfig, credentials, cluster identity, build metadata, local
state/plan and VM-backed PostgreSQL data. Git source, Docker cache and sanitized
acceptance evidence remain.

### Boundary after M1

This lab demonstrates a deterministic simulated agent platform on one local
cluster. It does not claim real LLM inference, AWS IAM/OIDC, cloud networking,
production availability, backup recovery, artifact signing, or a published image.
There is no required next task. If M2 is chosen, first define the AWS account,
region/model availability, budget, temporary credentials, connector egress,
separate state and OIDC scope before implementing T09.

## Previous verified checkpoint — T07, 2026-09-29

**T07 is complete.** GitHub now checks application contracts, infrastructure and
charts, and the Docker build on pull requests and pushes to `main`. Local cluster
deployment fails closed unless the clean local `main` commit exactly matches
`origin/main` and that SHA has a successful completed CI push run.

### Delivered

- A three-job [GitHub Actions workflow](../.github/workflows/ci.yml) with read-only
  repository permission, bounded timeouts and concurrency cancellation. All
  external actions are pinned to full commits and use their Node 24 releases.
- Python/HTTP regression and real disposable PostgreSQL contracts; Ruff and
  JavaScript syntax; Ansible lint; cluster-free OpenTofu format/init/validate;
  Helm lint/render; and an application image build from the pinned base digest.
- `make verify-static` shares the cluster-free infrastructure and chart checks
  with local development. CI receives no lab kubeconfig, state or credentials
  and does not contact the localhost Kubernetes API.
- A deployment provenance gate that requires clean `main`, exact `origin/main`,
  and a green **push** run for the full SHA before credentials, image build or
  cluster changes. A green pull-request run alone is rejected.
- The full validated SHA is injected into every workload and exposed by API info,
  new run history, UI and startup logs. Private `data/platform/build.json` records
  the CI run/URL, image ID/tag, pinned PostgreSQL image and guarded cluster UID.
- [CI demonstration](CI_DEMO.md), [ADR 0006](decisions/0006-ci-and-deployment-provenance.md),
  README/HLD updates and stronger cluster provenance checks.

### Executed evidence

- [PR #1](https://github.com/marcossabatino/agentic-devops/pull/1) ran all three
  jobs. Initial and Node 24 revisions passed. A temporary failing contract at
  commit `ca4430c` caused run
  [36584005320](https://github.com/marcossabatino/agentic-devops/actions/runs/36584005320)
  to fail only **Python and PostgreSQL contracts**; infrastructure and image jobs
  remained green. The test was removed, and corrected run
  [36584133420](https://github.com/marcossabatino/agentic-devops/actions/runs/36584133420)
  passed all three jobs. Final PR run
  [36612767903](https://github.com/marcossabatino/agentic-devops/actions/runs/36612767903)
  also passed before squash integration.
- Main push run
  [36612912372](https://github.com/marcossabatino/agentic-devops/actions/runs/36612912372)
  passed all three jobs for full SHA `6317693130b140f27d4b90584385e9e84304dda5`.
  The authenticated gate accepted it and deployed image
  `agentic-devops:v6317693130b1-3a292799d922`, image ID
  `sha256:a619c764602328ab4c6ec7e854295680f88fb030a63cd254e3f301f2e2fe92aa`.
- `make verify-cluster`: **33 checks passed**. All four Deployments used the
  recorded image and full SHA; API info and all five exercised scenario histories
  returned that SHA. Persistence after PostgreSQL pod replacement and the
  OpenTofu no-change plan also passed.
- Local checks passed: **56 standard tests** (26 PostgreSQL cases intentionally
  skipped there), **26 real PostgreSQL tests**, Ansible/OpenTofu/Helm validation,
  Ruff, JavaScript syntax and a Docker build. A feature-branch `make deploy`
  stopped before any cluster mutation as designed.

Evidence is retained by GitHub at the linked runs. Sanitized local output remains
in ignored `artifacts/t07-*.log`; exact current deploy metadata remains private in
`data/platform/build.json`. The workflow builds but does not publish images.
GitHub-hosted runners do not receive access to the local cluster.

### Boundaries and next task

This is local M1 provenance, not artifact signing or a registry supply-chain
claim. GitHub and authenticated `gh` are required when deploying. Any later
source change requires its own successful main push run before another deploy.
No self-hosted runner or public Kubernetes endpoint was added.

Next: **T08 — Verification, cleanup, and demonstration**. Consolidate A01–A13 in
`make verify`, implement guarded cleanup that preserves unrelated profiles and
contexts, complete the dedicated metrics/runbook tool catalog, and write the
ten-minute demonstration. Learning question: which evidence should be retained
after cleanup so a reviewer can distinguish executed acceptance from design?

## Previous verified checkpoint — T06, 2026-09-29

**T06 is complete locally.** Correlated JSON logs, metrics, distributed traces,
Grafana dashboards and six controlled scenarios run on the dedicated QEMU lab.
The user requested resuming and delivering the next task with progress updates.
The pre-existing partial T06 implementation was completed and validated. The
user subsequently authorized committing and pushing all pending work to
`origin/main`; this checkpoint accompanies that publication.

### Delivered

- W3C context persisted with each job and propagated across API, worker, gateway
  and orders HTTP boundaries. The UI and scenario commands expose the trace ID.
  Spans cover publication, execution/claim, simulated model decisions, tool calls,
  approval resumption, limits and persistence.
- JSON logs correlate validated run/trace IDs, service, step, tool, duration,
  status and error code. Prompt text, credentials, headers, DSNs and exception
  messages are excluded. Connection failures and timeouts have distinct categories.
- Prometheus endpoints on all four services; bounded metric labels for terminal
  runs, correctness, duration, pending jobs, steps, tool failures, retries and
  denials. Terminal totals derive from durable history to avoid double-counting.
- OpenTofu-owned local Helm release for digest-pinned Collector, Prometheus,
  Tempo and Grafana, with restricted pods, resource limits and internal Services.
  Eleven telemetry paths have symmetric ingress/egress rules (22 new policies;
  44 NetworkPolicies total). Application internet access remains denied.
- Provisioned ten-panel Grafana dashboard with Prometheus/Tempo datasources and
  localhost-only access via `make dashboards`. Anonymous access is Viewer only.
- Authenticated scenario selection, a named total-deadline scenario,
  `make scenario CASE=...`, `make reset`, `make logs RUN_ID=...` and
  `make verify-observability`. Reset selects healthy and executes a healthy run,
  preserving history. Restart still requires explicit approval.
- [Observability guide](OBSERVABILITY_DEMO.md), [ADR 0005](decisions/0005-observability-and-controlled-failures.md),
  updated README/HLD/task backlog and refreshed SVG/PNG implementation boundaries.

### Executed evidence

- `make verify-observability`: **90 checks passed**, including all six scenarios,
  trace parent graphs, four-service correlation, orders dependency timeout spans,
  three bounded timeout calls, five-step limit, total deadline, explicit approval
  and one simulated effect. All four Prometheus targets, required metrics and ten
  dashboard queries were verified through Grafana's actual datasource proxies.
  Logs correlate to the run's trace; credentials and prompt text were absent.
- `make verify-network`: **24 TCP checks passed**, including four application
  exporters reaching Collector and denied unauthorized telemetry/metrics access.
  Cluster DNS, host internet control, application egress denials and independent
  HTTP authorization (401/401/200/403) passed. The temporary test pod was removed.
- `make verify-durable`: **26 real PostgreSQL tests passed without skips**,
  including new scenario scope/reset, named deadline and queue/HTTP trace
  continuity/redaction tests. Existing approval/idempotency/recovery tests passed.
- `make verify-cluster`: **23 checks passed**, including persistent history after
  PostgreSQL pod replacement and the final OpenTofu **no-change** plan.
- `make test`: **27 standard-library checks passed**; PostgreSQL tests remain
  intentionally skipped here and are covered separately above. Helm lint,
  OpenTofu formatting/validation, JavaScript syntax and whitespace checks passed.
- Chromium loaded the dashboard with visible availability, outcome, latency and
  correctness data and no JavaScript errors. The viewport screenshot and refreshed
  architecture image were inspected. Full-page Grafana screenshots were replaced
  with viewport capture because Grafana virtualizes off-screen panels.
- The public scenario/healthy reset/log lookup commands passed against the
  deployed application. The active scenario was left healthy.

Evidence remains in ignored local files: `artifacts/t06-observability.json`,
`t06-trace-*.json`, `t06-correlated-logs.json`, `t06-dashboard.png`,
`t06-browser.json`, `t06-command-*.json*`, `t05-network.json`, `t03-durable.json`,
`t04-cluster.json` and `t04-post-apply-plan.log`. The deployed image/source are in
`data/platform/build.json`; the revision includes `-dirty` until committed.

### Environment recovery and boundaries

The VM was stopped at session start. On resume, Minikube rewrote the private
kubeconfig endpoint without certificate data and retained the previous API port
in profile metadata. Existing certificates were used with TLS verification;
the recorded kube-system UID matched before repairing the private kubeconfig
and synchronizing only the dedicated profile's API port. A private metadata
backup was retained. No cluster was recreated, TLS was not disabled and unrelated
contexts were not changed. A subsequent `make bootstrap` passed with
**ok=8, changed=0**, recorded in `artifacts/t06-bootstrap-repaired.log`.

Prometheus and Tempo storage is ephemeral (`emptyDir`); pod replacement can lose
telemetry. Tempo retains one hour; Prometheus retains 24 hours or 256 MB.
Application history remains in PostgreSQL. Logs use Kubernetes retention; no
central log store is claimed. Export queues/timeouts are bounded and can drop
telemetry during an outage. The database-backed metrics collector is for local
lab scale. This delivery makes no CI, HA, production or real-model claim.

The dedicated VM remains running. Use `make ui` / `make dashboards` for local
access or `minikube stop -p agentic-devops` to stop compute. Validation forwards
and browser processes were closed.

Next: **T07 — CI and deployment provenance**. T08 retains consolidated acceptance,
cleanup, demonstration and completion of the dedicated metrics/runbook tool
catalog. Learning question: how will the running image prove that it contains
exactly the commit validated by CI?

## Previous verified checkpoint — 2026-09-28

**T04 and T05 are complete locally.** The durable application now runs as separate
services on the dedicated QEMU profile, with persistent PostgreSQL and verified
Calico isolation. T01–T03 remain available. The user authorized proceeding through
T05 and committing/pushing this delivery to `origin/main`.

### Delivered

- Ansible bootstrap for the dedicated `agentic-devops` profile: Kubernetes
  1.34.12, Calico 3.30.3, isolated kubeconfig, and recorded cluster identity.
  Other profiles and the global kubectl context are preserved.
- OpenTofu platform ownership: four namespaces with restricted pod security,
  quotas, limits, and read-only observer RBAC; locked Kubernetes provider 2.38.0.
- Helm Deployments for API, worker, tool gateway, and orders; PostgreSQL StatefulSet
  with a 2 GiB persistent claim; a versioned migration Job. Images are pinned or
  tagged from source content. Services are internal and the UI uses localhost.
- Separate service/database credentials. The orders service owns the atomic
  simulated effect, approval consumption, and deduplication. The gateway has
  read-only database access and forwards using a distinct orders credential.
- Twenty-two NetworkPolicies: default deny and DNS in all four namespaces,
  plus seven explicit application paths with ingress and egress permission.
- [Platform reproduction guide](PLATFORM_DEMO.md), [ADR 0004](decisions/0004-local-platform-and-network.md),
  and updated [high-level design](HIGH_LEVEL_DESIGN.md) and SVG/PNG artwork.

### Executed evidence

- `make bootstrap`: all tasks passed; repeating it produced **ok=8, changed=0**.
  The preflight accounts for RAM already allocated to a matching running VM.
- `make verify-cluster`: **23 checks passed**, including workload/Calico readiness,
  internal Services, authentication, all five scenarios, explicit restart approval,
  one simulated effect, history after PostgreSQL pod replacement, and a zero-change
  OpenTofu plan. The same checks passed with default-deny policies active.
- `make verify-network`: **16 TCP checks passed** (allowed service paths,
  prohibited paths, and workload internet denials). Cluster DNS resolved correctly.
  A reachable host control verified the external destination. HTTP authorization
  on the allowed worker/tools path returned 401/401/200/403 as expected for missing,
  invalid, valid, and valid-but-unapproved requests. The temporary pod was removed.
- `make verify-durable`: **23 real PostgreSQL integration tests passed** without
  skips, including separate gateway/effect ownership, denied database writes,
  and concurrent duplicate calls producing one effect.
- `make test`: **27 standard-library regression/guard tests passed**; its 23
  PostgreSQL cases are explicitly skipped and covered by `make verify-durable`.
- Helm lint and OpenTofu formatting/validation passed. Generated architecture
  SVG/PNG assets were inspected. Secret values, kubeconfig, state, and runtime
  reports remain ignored local files.
- Reproducible evidence: `artifacts/t04-cluster.json`,
  `artifacts/t04-post-apply-plan.log`, `artifacts/t04-bootstrap-second.log`,
  `artifacts/t05-network.json`, and `artifacts/t03-durable.json`.
  `data/platform/build.json` records the deployed image and source revision.

### Boundaries and next task

The dedicated lab VM remains running. Use `make ui` for local access or
`minikube stop -p agentic-devops` to stop its compute. Persistence was verified
across PostgreSQL pod replacement; VM deletion recovery and high availability
are not claimed. The restart is a simulated database effect, not a real service
operation. No LLM or AWS calls are made.

Next: **T06 — Observability and controlled failures**. Implement correlated logs,
metrics, traces, dashboards, and scenario/reset commands. Add telemetry network
paths together with those workloads. Distributed A05 trace evidence, CI (T07),
and full teardown (T08) remain pending.

## Previous verified checkpoint — T03, 2026-09-28

Documentation follow-up: added the [high-level design](HIGH_LEVEL_DESIGN.md) with
target application, approval, delivery, observability, and M2 model-path diagrams.
It distinguishes the implemented T03 harness from the complete platform and
records the remaining metrics/runbook tool and service-packaging decisions.
This follow-up changes documentation only; T04 remains the next implementation task.

Visual follow-up: added original architecture artwork in editable SVG and
5120 × 3560 PNG under `docs/assets/`, embedded in the README and HLD. The image
shows numbered execution steps, deployment namespaces, delivery, observability,
and the current/future boundary. `scripts/render_architecture.py` regenerates
the assets; SVG generation and PNG export were executed and visually inspected.

**T03 is complete within its local scope.** T01/T02 remain available. The new
PostgreSQL mode provides asynchronous runs, atomic job claims, expiring leases,
fenced worker writes, durable step/attempt/deadline limits, HTTP service
credentials and scopes, explicit user approval, and transactional simulated
restart idempotency. Kubernetes and distributed observability are not validated.

### Delivered

- `make setup`, `make run-durable`, and `make verify-durable`, with pinned Psycopg
  3.2.10 and a private native PostgreSQL cluster. No existing database or cluster
  is modified. Persistent demo files live in ignored `data/t03/`.
- SQL schema for jobs, events, approvals, tool results, and per-run simulator
  state; separate API, worker, and tool roles with tested denied permissions.
- HTTP 202 creation, authenticated run retrieval and approval, interface polling,
  visible pending action, explicit approval button, and failure scenarios.
- Default five steps, three claims, 30-second execution deadline, three-second
  lease, 0.5-second tool timeout, two transient retries, and a separate 300-second
  approval window. Limits are configurable through the durable launcher.
- [ADR 0003](decisions/0003-durable-execution.md), the [durable demonstration](DURABLE_DEMO.md),
  README updates, and the updated task backlog.

### Executed evidence

- `make verify-durable`: **22 real PostgreSQL integration tests passed**, with no
  skips. Report: ignored `artifacts/t03-durable.json`. PostgreSQL 16.13, Python
  3.13.13, Psycopg 3.2.10; source revision `4cfdf218d90c-dirty`.
- Eight competing workers claimed one job once. A terminated claiming process
  was recovered after lease expiry. The former lease holder could not complete
  the recovered job, and consumed steps were preserved.
- Eight concurrent duplicate restart calls produced one persisted effect and
  one stored result. A worker lost after the effect but before recording its
  response recovered without another restart. History and deduplication survived
  a real database stop/start.
- Reachable HTTP tool calls rejected missing/invalid credentials, missing scopes,
  invalid arguments, missing or expired approval, changed run binding, and
  conflicting idempotency keys. The worker could not approve through the API or
  insert approvals using its database role. An expired run could not execute an
  approved new effect.
- Timeout, total deadline, claim exhaustion, approval expiry, and the durable
  step limit reached visible terminal states. These are local A05/A07 behavioral
  checks; A05 distributed trace evidence remains T06.
- `make test`: **23 existing regression tests passed**. PostgreSQL integration
  cases are explicitly skipped in this dependency-free target and are executed
  by `make verify-durable`. `make verify-local` still passes all ten local A04 checks.
- Chromium walkthrough: **11 checks passed**, including all five scenarios,
  visible authentication rejection, explicit approval before a restart, one
  simulated effect, safe text rendering, a 390px layout, visible failure reasons,
  and history retrieval after restarting the whole demo/database. No page
  JavaScript errors. Screenshots were inspected.
- Browser evidence: ignored `artifacts/t03-browser.json`,
  `artifacts/t03-approval-desktop.png`, and `artifacts/t03-mobile.png`.
  Restart run ID: `ce7d7fec-97b7-4a8a-be58-511a1c6b8815`.
- `node --check app/static/app.js` and `git diff --check` passed.
- The sandbox initially denied sockets; the same HTTP/PostgreSQL checks passed
  when run with host socket access. Test databases and demo processes were
  stopped. No VM/profile/context was created or changed.

### Boundaries and next task

The local harness uses separate component threads and database credentials.
The simulator's restart counter, approval consumption, and deduplication result
share one database transaction. This demonstrates one **simulated database**
effect; it is not an exactly-once guarantee for an external service. Credentials
are generated locally and stored with restrictive permissions, not printed or
committed. Distributed container/process packaging remains T04.

Next: **T04 — Reproducible local platform**. Use the previously selected dedicated
`agentic-devops` QEMU profile. Implement Ansible bootstrap, Calico, explicit
OpenTofu platform ownership, and Helm application deployment. Verify readiness,
a second bootstrap, and a stable post-apply plan. Preserve other profiles and
contexts. A05 trace evidence and full telemetry remain T06; networking is T05.

Learning question: why can a lease recover job ownership while an external
restart still needs its own idempotency contract?

This T03 delivery is present in the local working tree. No commit or push was
performed during this task. Earlier publication notes below describe previous
checkpoints, not the current working tree.

## Previous verified checkpoint — 2026-09-27

T01 is complete: OpenTofu 1.10.6 is installed and the real host `make doctor` passes with zero failures. T02 is complete within its local scope: the SIMULATED interface executes a deterministic health-tool call, exposes its evidence, and retains results by run ID in memory. All 23 tests pass; A04 passed through local HTTP, and the interface passed a Chromium walkthrough. Kubernetes and the remaining acceptance criteria are not yet validated.

### Current completion evidence

- OpenTofu installed under `~/.local/share/opentofu/1.10.6`, with `~/.local/bin/tofu` pointing to the binary. The official standalone installer was inspected and run without root privileges, with verification enabled and a temporary GPG home.
- Verified archive: `tofu_1.10.6_linux_amd64.zip`; SHA-256 `15b7bed76420b50da3e121769c43341df8cd57d751ca14e6dbe9c850124c6dac`. The signed checksums verified against fingerprint `E3E6E43D84CB852EADB0051D0C0AF313E5FD9F80`. Source: [official installation procedure](https://opentofu.org/docs/intro/install/standalone/).
- `make doctor` outside the sandbox exited 0: host capacity, KVM, and all pinned CLIs passed. The absent lab profile and unset/outside current context remain informational.
- `make test` passed 23 tests: eight preflight tests, seven execution/store/tool tests, and eight HTTP integration tests. HTTP tests bind temporary localhost ports and shut down afterwards.
- `node --check app/static/app.js` passed.
- `make verify-local` exited 0 and wrote `artifacts/a04-local.json`. All ten checks passed: creation, mode, completion, outcome, no execution error, UUID, tool call, tool completion, healthy evidence, and retrieval by ID. Run ID: `ed646d5e-5394-47b3-950a-f52d3aae7554`; source revision: `0271ae70b42c-dirty`.
- Chromium walkthrough passed: healthy and degraded scenarios via the actual form, unique IDs, visible tool evidence, question text rendered without executing HTML, 390px layout without horizontal overflow, visible HTTP failure/re-enabled submit, and no page JavaScript errors. Evidence is in ignored `artifacts/t02-browser.json`, `artifacts/t02-desktop.png`, and `artifacts/t02-mobile.png`. Playwright was used from a temporary environment, not added as an application dependency.
- Browser run IDs: healthy `888a2669-f4c9-4e9c-8687-7b2128745314`; degraded `29686773-696b-4289-9dc2-2d4e5898551e`. Screenshots were inspected for layout.
- The application binds only to `127.0.0.1`; no lab VM was created and no existing cluster/profile/context was changed. Test servers were stopped after validation.

Run the demo with `make run`, then open `http://127.0.0.1:8080`. See [LOCAL_DEMO.md](LOCAL_DEMO.md) and [ADR 0002](decisions/0002-local-simulated-execution.md). This record accompanies the T01/T02 implementation checkpoint.

### End-of-session handoff

The user ended today's learning session after T01/T02 and requested committing and
pushing the pending work to `origin/main`. Resume with T03 at the next session:
review the completed-diagnosis/degraded-service distinction, then agree on the
PostgreSQL schema and atomic job-claim/lease contract before implementation.
Do not repeat repository setup, the QEMU decision, OpenTofu installation, or T02
implementation. Existing validation evidence is recorded above; rerun checks when
code changes or the environment warrants it. No lab cluster or demo server was
left running by this implementation session.

### Repository evidence

- User supplied repository: https://github.com/marcossabatino/agentic-devops (public at inspection).
- `git ls-remote` returned `d9f1a08a35f73509ee4ccc270e92b8e54f620aef` for HEAD and `refs/heads/main`.
- A temporary clone showed only `README.md` and the MIT `LICENSE`, with commit `d9f1a08 Initial commit`.
- The working directory was initialized and connected to `origin`; local `main` tracks `origin/main` at that initial commit. Existing `docs/prd.md` was preserved.
- `git status --short --branch` after connection showed `main...origin/main` and untracked `docs/`. No commit or push was performed.
- `AGENTS.md`, `docs/IMPLEMENTATION_PLAN.md`, and `docs/PROGRESS.md` were absent before this session. This plan and progress record were created from the PRD and observed evidence; they do not reconstruct unknown prior work. No `AGENTS.md` was created.
- The scope baseline is currently named `docs/prd.md`, with lowercase letters; `docs/PRD.md` is not a separate file.

### Initial environment evidence (before T01 completion)

| Check | Observed result |
|---|---|
| `/etc/os-release` | Fedora Linux 42 Workstation |
| `nproc` | 8 logical CPUs visible |
| `free -h` | 31 GiB total RAM; approximately 18 GiB available at inspection |
| `df -h .` | 212 GiB available on the workspace filesystem |
| `git --version` | 2.54.0 |
| `python3 --version` | 3.13.13 |
| `docker --version` and `docker info` | Client and daemon 29.5.3; daemon reports 8 CPUs |
| `minikube version --short` | v1.37.0 |
| `kubectl version --client -o yaml` | v1.34.12 |
| `helm version --short` | v3.19.0 |
| `ansible --version` with a writable temporary directory | ansible-core 2.20.5 |
| `make --version` | GNU Make 4.4.1 |
| `command -v tofu` | Not found in PATH |
| `minikube profile list -o json` | Existing `minikube` profile stopped; QEMU driver; configured Kubernetes v1.34.0, 4 CPUs, 8192 MiB RAM |
| `kubectl config current-context` | No current context set |
| `kubectl config get-contexts -o name` | Existing Minikube and unrelated EKS contexts; left untouched |

Sandbox restrictions initially prevented GitHub DNS access, Docker socket access, and Ansible temporary-directory creation. Remote reads and Docker inspection succeeded outside the sandbox; Ansible succeeded with `ANSIBLE_LOCAL_TEMP=/tmp/agentic-devops-ansible-check`. These initial errors are not evidence of broken host installations. Podman is present but its version check was blocked by a runtime-directory restriction and was not pursued.

### Decision boundary and next task

- Confirmed scope: local M1 with deterministic simulation; AWS remains M2.
- Repository destination is known. The previous documentation/preflight baseline was published in commit `0271ae70b42c4efb5aa93b9a6744fe6f4a72a291`, confirmed at `origin/main`; this checkpoint adds the completed local T01/T02 increment.
- The user selected QEMU. Use driver `qemu2` and network `builtin` in a dedicated `agentic-devops` profile; see [ADR 0001](decisions/0001-qemu-lab-profile.md). Do not ask for the driver choice again.
- Added `config/lab.json`, `scripts/doctor.py`, `Makefile`, eight preflight tests, documentation, and ignores for research cache, Python artifacts, local secrets, and IaC state/plans.
- QEMU and qemu-img both report 9.2.4. Read/write access to `/dev/kvm` passed outside the execution sandbox.
- The initial eight preflight tests passed; the suite now includes 23 tests as recorded above.
- The initial doctor failure for missing OpenTofu is resolved; the current host check passes.
- Exact CLI pins are recorded, and Minikube 1.34 support plus kubectl version skew were checked against official sources. Full QEMU/Kubernetes/Calico/Helm/provider integration has not been tested.
- T02 uses a synchronous runner, separate adapter/tool/simulator components within one process, and a bounded in-memory store. The question is recorded but not interpreted. No LLM, shell, service restart, or external operational action is available.
- Next task is T03: define the PostgreSQL schema and atomic job-claim/lease contract, then implement durable execution and service authorization. Approval binding and idempotency follow before any simulated state-changing tool is exposed.
- Learning question before the next increment: why can a diagnosis be completed while the orders service is degraded, and how should monitoring distinguish those outcomes?
- No lab VM was created, and no existing profile or Kubernetes context was changed. The preflight checkpoint itself did not include a commit or push.
- Deferred: PostgreSQL, distributed worker/services, authentication/scopes, approval/idempotency, dependency deadlines/retries, cluster creation, Ansible/OpenTofu/Helm implementation, full telemetry, CI, remaining acceptance scenarios, and AWS integration.

Resume by reading this record, the implementation plan, and `docs/prd.md`; inspect the working-tree diff. Do not repeat repository setup or the full host inventory unless the environment has changed.

### Previous repository documentation and publication

- Expanded the English README to describe the project, implemented functionality, planned architecture, prerequisites, available commands, isolation design, roadmap, documentation, and license.
- Expanded `.gitignore` for Python caches/environments, local credentials, kubeconfigs, IaC state/plans, Ansible runtime files, Helm dependencies, QEMU images, runtime databases, research cache, and editor artifacts. Dependency lock files and sanitized examples remain eligible for version control.
- Updated the PRD repository reference to the destination supplied by the user.
- Validation before publication: `make test` passed all eight tests; 25 representative local/artifact paths were confirmed ignored and 17 source/example/lock paths confirmed retained. Whitespace, local documentation links, and a scan for common credential formats passed. `git fetch origin` confirmed no divergence from `origin/main` before the commit.
- The user authorized publication to `origin/main`; commit `0271ae70b42c4efb5aa93b9a6744fe6f4a72a291` was pushed successfully and independently confirmed with `git ls-remote origin refs/heads/main`.
