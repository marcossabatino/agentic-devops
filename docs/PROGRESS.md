# Progress

## Last verified checkpoint — 2026-09-27

Repository connection, environment inspection, and the QEMU preflight implementation are complete. Eight preflight tests pass. The real host `make doctor` reports one failure: OpenTofu is missing. No application or infrastructure acceptance scenario has been executed. T01 remains partial until the missing prerequisite is resolved.

### Repository evidence

- User supplied repository: https://github.com/marcossabatino/agentic-devops (public at inspection).
- `git ls-remote` returned `d9f1a08a35f73509ee4ccc270e92b8e54f620aef` for HEAD and `refs/heads/main`.
- A temporary clone showed only `README.md` and the MIT `LICENSE`, with commit `d9f1a08 Initial commit`.
- The working directory was initialized and connected to `origin`; local `main` tracks `origin/main` at that initial commit. Existing `docs/prd.md` was preserved.
- `git status --short --branch` after connection showed `main...origin/main` and untracked `docs/`. No commit or push was performed.
- `AGENTS.md`, `docs/IMPLEMENTATION_PLAN.md`, and `docs/PROGRESS.md` were absent before this session. This plan and progress record were created from the PRD and observed evidence; they do not reconstruct unknown prior work. No `AGENTS.md` was created.
- The scope baseline is currently named `docs/prd.md`, with lowercase letters; `docs/PRD.md` is not a separate file.

### Environment evidence

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
- Repository destination is known. The user has explicitly requested committing and publishing all project files, excluding ignored local artifacts and credentials.
- The user selected QEMU. Use driver `qemu2` and network `builtin` in a dedicated `agentic-devops` profile; see [ADR 0001](decisions/0001-qemu-lab-profile.md). Do not ask for the driver choice again.
- Added `config/lab.json`, `scripts/doctor.py`, `Makefile`, eight preflight tests, documentation, and ignores for research cache, Python artifacts, local secrets, and IaC state/plans.
- QEMU and qemu-img both report 9.2.4. Read/write access to `/dev/kvm` passed outside the execution sandbox.
- `make test`: eight tests passed, covering missing tools, version formats/mismatch, timeout handling, malformed inventories, unrelated profiles, conflicting lab profiles, and a matching stopped profile.
- `make doctor` outside the sandbox: capacity, KVM access, and all installed pinned tools passed. OpenTofu failed as absent from PATH. The doctor script exits 1; GNU Make reports exit 2 for the failing target. The absent lab profile and unset/outside current context are informational.
- Exact CLI pins are recorded, and Minikube 1.34 support plus kubectl version skew were checked against official sources. Full QEMU/Kubernetes/Calico/Helm/provider integration has not been tested.
- Next task: install and verify OpenTofu 1.10.6, rerun `make doctor`, and then proceed to the minimal simulated execution in T02. Tool installation was not performed in this checkpoint.
- Learning question before the next increment: why does VM isolation not replace pod NetworkPolicies or service authorization?
- No lab VM was created, and no existing profile or Kubernetes context was changed. The preflight checkpoint itself did not include a commit or push.
- Deferred: tool installation, cluster creation, application code, Ansible/OpenTofu/Helm implementation, CI, acceptance tests, and AWS integration.

Resume by reading this record, the implementation plan, and `docs/prd.md`; inspect the working-tree diff. Do not repeat repository setup or the full host inventory unless the environment has changed.

### Repository documentation and publication preparation

- Expanded the English README to describe the project, implemented functionality, planned architecture, prerequisites, available commands, isolation design, roadmap, documentation, and license.
- Expanded `.gitignore` for Python caches/environments, local credentials, kubeconfigs, IaC state/plans, Ansible runtime files, Helm dependencies, QEMU images, runtime databases, research cache, and editor artifacts. Dependency lock files and sanitized examples remain eligible for version control.
- Updated the PRD repository reference to the destination supplied by the user.
- Validation before publication: `make test` passed all eight tests; 25 representative local/artifact paths were confirmed ignored and 17 source/example/lock paths confirmed retained. Whitespace, local documentation links, and a scan for common credential formats passed. `git fetch origin` confirmed no divergence from `origin/main` before the commit.
- Publication target: `origin/main`. The user explicitly authorized the commit and push. Publication outcome must be verified against the remote commit; preparation alone is not evidence of a successful push.
