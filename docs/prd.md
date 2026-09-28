# PRD — Agentic DevOps Platform Lab

Version: 0.2 (English edition) • Date: 2026-09-27 • Project owner: Marcos Sabatino

Status: implementation specification. This document does not create a cluster, repository, or AWS resources.

## 1. Objective and expected outcome

Build a reproducible lab on the user's computer with Minikube, OpenTofu, Ansible, GitHub Actions, micro-segmentation, and observability. Prepare for the Ciklum Expert DevOps Engineer technical interview through implementation evidence and architectural decisions.

The user must be able to open a local interface, request an operational diagnosis, inspect tool calls, view metrics and traces, inject failures, and verify access restrictions. The user should be able to explain each technology's role and limitations.

This lab does not represent Ciklum's internal architecture. Requirements are inferred from the job description.

## 2. User journey

1. Clone the repository and run prerequisite checks.
2. Prepare the environment with Ansible and create a dedicated Minikube profile.
3. Review and apply the OpenTofu plan for the local platform.
4. Deploy the application and access its interface through a localhost port-forward.
5. Select a scenario, submit a question, and observe execution.
6. Open the corresponding trace and compare metrics before and after a failure.
7. Run validation and inspect PASS/FAIL evidence.
8. Stop processes or remove only lab resources.

## 3. Use case

An operational diagnosis agent for a fictional orders service. Example: “Why is the orders service returning errors?”

Initial tools: read health, query synthetic metrics, and retrieve a runbook. A state-changing tool may restart only a simulated service, requiring explicit approval in the interface and an idempotency key.

The agent receives no unrestricted shell, cluster administrator access, or access to real user systems. The execution service validates authorization and approval independently of model output.

## 4. Incremental scope

### M1 — Verifiable local platform

- Minikube with Calico and standard Kubernetes NetworkPolicies.
- A simple Python API/interface, execution worker, tool service, and orders service simulator.
- A deterministic model adapter with scripted responses and tool calls, visibly labeled SIMULATED.
- A small PostgreSQL instance for runs, events, approvals, and idempotency keys.
- Ansible for bootstrap, OpenTofu for platform resources, and Helm for application deployment.
- GitHub validation pipeline and reproducible local deployment commands.
- Metrics, structured JSON logs, and correlated traces.
- Positive and negative tests for connectivity and authorization.

M1 demonstrates platform operations and tool contracts. It does not demonstrate autonomous LLM behavior or production AWS experience.

### M2 — Real AWS integration

- Amazon Bedrock adapter using an available model and region in the user's account.
- Temporary host credentials with controlled local injection; no credentials committed to Git. Document refresh and expiration. Do not assume EKS Pod Identity or IRSA works automatically in Minikube.
- Model credentials restricted to the integration component; no broad AWS access for the agent.
- Separate OpenTofu directory and state for AWS resources: CI IAM, S3 backend, and applicable access/provisioning controls.
- GitHub Actions OIDC for authorized AWS operations with a restricted trust policy.
- Explicit Bedrock connector egress design. Standard NetworkPolicy does not provide DNS-name allowlisting. Define an egress proxy or another supported mechanism before claiming domain restrictions.
- Application limits for steps, tokens, and concurrency. AWS Budgets provides alerts, not a guaranteed hard spending cap.
- Evidence of a real run, estimated cost, and a controlled authorization failure.

### M3 — Optional extensions

- GitHub-triggered local deployment through a dedicated self-hosted runner, trusted code only, and manual workflow dispatch.
- Telemetry export to Datadog.
- An MCP server exposing one tool with explicit authentication and authorization.
- RAG, tenant isolation, and architectural comparison with EKS, ECS, and AgentCore.

Outside MVP scope: GPUs, model training/fine-tuning, multiple agents, real high availability, service mesh, a complex portal, production use, and public internet deployment.

## 5. Proposed architecture

Namespaces: `lab-app`, `lab-tools`, `lab-data`, and `lab-observability`.

| Component | Responsibility |
|---|---|
| Interface/API | Accept requests, display execution, and record approval from an authenticated lab user |
| Agent worker | Orchestrate steps, enforce limits, and call tools/model |
| Model adapter | Switch between deterministic simulation and Bedrock while preserving the tool-calling contract |
| Tool service | Validate identity, scope, arguments, approval, and idempotency before execution |
| Simulated orders service | Produce healthy, failing, and slow responses and a controlled restart effect |
| PostgreSQL | Persist executions, history, and approvals using separate permissions |
| OpenTelemetry Collector | Receive and forward traces |
| Prometheus/Grafana/Tempo | Collect metrics, display dashboards, and query traces |

The API writes jobs to PostgreSQL. The worker acquires jobs through an atomic claim/lease mechanism. Avoid an additional message broker in the MVP. Lease expiration enables recovery; external effects still require idempotency. Retries alone do not guarantee exactly-once execution.

The interface displays model mode, run ID, status, steps, tool names, results, duration, errors, and pending approvals. Display operational events and concise user-facing explanations, not private model reasoning.

## 6. Tool ownership boundaries

| Tool | Responsibility and evidence |
|---|---|
| Ansible | Check/install pinned tool versions, prepare directories and Minikube profile; repeat execution without unnecessary changes |
| OpenTofu | Namespaces, quotas, RBAC, NetworkPolicies, and observability releases; plan/apply and drift demonstration |
| Helm | Application Deployments, Services, configuration, and service accounts; these resources must not also be managed by OpenTofu |
| GitHub Actions | Linting, contract/security tests, IaC validation, build, and evidence; optional private image publication |

OpenTofu uses Kubernetes/Helm providers with an explicit kubeconfig and context. Ansible starts the cluster before initialization and planning. Avoid using local-exec provisioners as the primary orchestration mechanism.

M1: local state excluded from Git, restricted access, single operator, and documented backup/destruction. M2: S3 backend with locking supported by selected versions, encryption, versioning, and least-privilege IAM. Separate backend bootstrap from its consumers.

## 7. Micro-segmentation and identity

Default-deny ingress and egress in application namespaces, with explicit rules for DNS and required connections. Ingress and egress policies must both permit an intended connection.

| Source | Destination | Expected result |
|---|---|---|
| API | Database job schema | Allowed with a restricted database user |
| Worker | Database jobs/events | Allowed with specific permissions |
| Worker | Model adapter and tool service | Allowed on declared ports |
| Tool service | Simulated orders service | Allowed |
| Tool service | Database approval/idempotency records | Allowed with restricted access |
| API | Simulated orders service | Blocked |
| Worker | Simulated orders service directly | Blocked |
| Unauthorized test pod | Database and tool service | Blocked |
| Applications | Telemetry collector | Allowed |
| Prometheus | Selected metrics endpoints | Allowed |
| Workloads | Cluster DNS | Allowed for required resolution |
| M1 workloads | Internet | Blocked |

Networking does not replace authorization. Each tool validates service credentials and request identity/scope. Generate development credentials locally; never commit or log them. Disable automatic Kubernetes service account token mounting for pods that do not use the Kubernetes API.

Use non-root containers where supported, no privileged workloads, dropped capabilities, resource requests/limits, and health probes. Base64 encoding alone does not protect Secrets.

Standard NetworkPolicy controls network connections, not commands, user identity, or HTTP content. A namespace alone is not sufficient isolation. An administrator who can change policies or labels can invalidate these restrictions; the lab assumes a trusted local administrator.

## 8. GitHub integration

Repository: [marcossabatino/agentic-devops](https://github.com/marcossabatino/agentic-devops), supplied by the owner and confirmed public during initial inspection.

Pull requests run formatting checks, `tofu validate`, `ansible-lint`, application/manifest linting, meaningful unit tests, and image builds. Jobs without Minikube access must not run cluster-dependent plans; run those plans locally against the dedicated lab context. Publish images only from a trusted main-branch workflow.

M1 deployment: pull the validated commit and run `make deploy`. Building/loading the image into Minikube avoids a registry dependency in the first increment. Record the commit SHA in the interface and logs.

A GitHub-hosted runner does not automatically have access to the local cluster. M3 may introduce a dedicated self-hosted runner with minimal access, restricted manual execution, and no untrusted pull-request execution. Do not expose the Kubernetes API publicly to enable CI/CD.

In M2, OIDC provides temporary AWS credentials, not Minikube connectivity. Restrict GITHUB_TOKEN permissions per job; pin actions by commit; exclude secrets from outputs/artifacts. Keep state, sensitive plans, kubeconfig, and credentials out of Git.

## 9. Observability and reliability

JSON logs: timestamp, level, service, run_id, trace_id, step, tool, duration, status, and error code. Redact credentials and sensitive content.

Traces: API entry, job publication/claim, execution, model call, tool call, and persistence. Propagate trace context across asynchronous operations.

Metrics: completed/failed runs, duration, pending jobs, tool failures/timeouts, retries, denied calls, and steps per run. M2 adds token usage and estimated model costs, clearly distinguished from actual billing.

Do not use run IDs, prompt text, or users as Prometheus labels. Keep high-cardinality identifiers in logs/traces.

Dashboards must distinguish technical availability from correct task completion. Evaluate correctness using scenarios and expected outcomes; HTTP 200 alone is insufficient.

Initial execution policy: configurable maximum of five steps, per-dependency timeout, total execution deadline, and bounded retries with backoff/jitter for transient failures. Human approval has a separate expiration window. State-changing operations require idempotency and approval bound to run ID, tool, and arguments.

## 10. Scenarios and acceptance criteria

| ID | Scenario | Passing evidence |
|---|---|---|
| A01 | Reproducible setup | Preflight passes; pods ready; interface accessible locally only |
| A02 | Idempotent bootstrap | Second Ansible run has no unexplained changes |
| A03 | Stable infrastructure | Post-apply plan has no unexpected changes |
| A04 | Healthy diagnosis | Run calls a tool and finishes with the expected outcome and run ID |
| A05 | Unavailable tool | Controlled failure/deadline; trace identifies dependency; no infinite retries |
| A06 | Forbidden connection | Negative test is blocked; equivalent positive test succeeds; tests have bounded timeouts |
| A07 | Unauthorized action | Service rejects the request even when network connectivity is allowed |
| A08 | Approval | Simulated restart cannot occur before approval; changed arguments invalidate approval |
| A09 | Idempotency | Two requests with the same key produce one simulated effect |
| A10 | Step limit | Simulator repeatedly requests tools; execution stops at the configured limit with a visible reason |
| A11 | Telemetry | Run ID locates logs and trace; dashboard records success, failure, and latency |
| A12 | GitHub | PR checks execute; intentional failure fails the relevant check; deployed commit is identifiable |
| A13 | Cleanup | Removes only lab profile/resources and preserves unrelated contexts/projects |
| A14 | Bedrock, M2 | Real execution identified; least-privilege IAM tested; token usage/cost estimate visible |

Simulated runs provide deterministic test outcomes. Real model tests use functional criteria rather than identical generated text.

## 11. Desired command interface

These commands are implementation contracts, not currently available functionality:

- `make doctor`: inspect prerequisites and context.
- `make bootstrap`: run Ansible setup and prepare the Minikube profile.
- `make infra-plan` / `make infra-apply`: review/apply OpenTofu infrastructure.
- `make deploy`: deploy the application image for the local commit.
- `make ui` / `make dashboards`: provide local access.
- `make verify`: execute acceptance scenarios and produce a PASS/FAIL report.
- `make scenario CASE=tool-timeout`: activate a reproducible failure.
- `make reset`: restore a healthy scenario.
- `make destroy`: remove lab resources after explicit profile/context validation.

## 12. Proposed repository layout

| Path | Contents |
|---|---|
| docs/ | PRD, architecture, decisions, and exercises |
| app/ | API/interface, worker, adapter, and tools |
| ansible/ | Playbooks, local inventory, and roles |
| infra/local/ | OpenTofu for the Minikube platform |
| infra/aws/ | Separate AWS increment |
| charts/app/ | Application Helm chart |
| observability/ | Dashboards and configuration |
| tests/ | Contracts, authorization, and integration scenarios |
| .github/workflows/ | CI and future AWS integration |

## 13. Implementation plan and learning checkpoints

1. Inspect OS, available CPU/RAM, installed Docker/Minikube, and GitHub remote; choose compatible pinned versions.
2. Implement one end-to-end simulated execution and a minimal interface.
3. Add Ansible/OpenTofu and validate repeatability.
4. Apply policies and test connectivity separately from authorization.
5. Instrument traces/metrics and exercise controlled failures.
6. Connect repository CI and document a ten-minute demonstration.
7. Add Bedrock/IAM/OIDC after account access and budget are defined.

Each checkpoint ends with completed work, evidence, an architectural decision, and one question for Marcos before the next step. Use 60–90-minute learning sessions.

Initial planning estimate: 8–12 hours of guided implementation for M1 and an additional 3–5 hours for M2, subject to environment and AWS access. These are rough planning estimates, not delivery guarantees. The first session targets bootstrap and a simple execution, not the full stack.

Initial sizing to validate: host with 16 GB RAM and 30 GB free disk; Minikube profile with four vCPUs and 8 GB RAM. Offer on-demand observability for smaller environments. Measure actual consumption before treating these estimates as sufficient.

## 14. Open questions and risks

- Local environment and repository are unknown; do not claim integration is complete.
- Proxy/network restrictions and local capacity may prevent image pulls or telemetry delivery.
- Windows may require WSL2 adaptation; Linux is the initial reference, not a confirmed host assumption.
- Minikube does not validate HA, EKS IAM, VPC Security Groups, or multi-AZ resilience.
- A simulated LLM does not test reasoning or real prompt-injection resistance; real scenarios need a separate evaluation.
- AWS requires an account, available region/model, and temporary credentials. Never request passwords in chat.
- This PRD enables implementation and evaluation; acceptance execution belongs to the build phase.

## 15. Technical references

- Minikube NetworkPolicy: https://minikube.sigs.k8s.io/docs/handbook/network_policy/
- Kubernetes NetworkPolicy: https://kubernetes.io/docs/concepts/services-networking/network-policies/
- GitHub runners: https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/add-runners
- GitHub OIDC/AWS: https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws
- OpenTofu providers: https://opentofu.org/docs/language/providers/
- OpenTofu S3: https://opentofu.org/docs/language/settings/backends/s3/
- Ansible check/diff: https://docs.ansible.com/projects/ansible/latest/playbook_guide/playbooks_checkmode.html
- AgentCore security: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-security-best-practices.html

## 16. Repository conventions and guided implementation

This English edition adds the following working conventions without changing the technical scope:

- Keep code, documentation, comments, commit messages, and pull-request descriptions in English. Learning discussions may be in Brazilian Portuguese.
- Do not add development-assistant credits, generated-by footers, promotional badges, or assistant co-author trailers to project artifacts or commits. Preserve required third-party licenses and attribution.
- Preserve the user's configured Git identity. Do not invent authors or rewrite existing authorship history.
- Treat this PRD as the scope baseline. Record intentional architecture changes and their rationale in short decision records.
- Implement one agreed learning increment at a time. Before an important architectural choice, ask one focused question, assess the user's answer, explain the trade-off, and continue with the agreed increment.
- Record completed steps, actual validation evidence, pending decisions, and the next task in `docs/PROGRESS.md` so a new session can resume accurately.
- Keep a task backlog in `docs/IMPLEMENTATION_PLAN.md`, mapping tasks to acceptance criteria. This local backlog can later be converted into GitHub issues.
- Never mark a check as passed unless it was executed successfully. Distinguish implemented, tested, and deferred work.
- Initial work is local. Remote repository creation/push and AWS provisioning are separate, explicit tasks when their destination and scope are known.
