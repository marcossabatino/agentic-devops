# Progress

## Last verified checkpoint — 2026-09-27

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
