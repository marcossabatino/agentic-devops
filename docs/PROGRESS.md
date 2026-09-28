# Progress

## Last verified checkpoint — 2026-09-28

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
