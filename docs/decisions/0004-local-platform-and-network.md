# ADR 0004 — Dedicated platform, separate effect owner, and explicit network flows

Date: 2026-09-28. Status: implemented for T04/T05.

## Platform ownership

Ansible validates the pinned prerequisites and starts only the `agentic-devops`
QEMU profile with builtin networking, Kubernetes 1.34.12, containerd, and Calico.
Calico 3.30.3 is bundled by the pinned Minikube 1.37.0. An isolated mode-0600
kubeconfig lives in ignored `data/platform/`; global contexts are not selected or
rewritten. Commands also verify the recorded kube-system UID and dedicated node
before platform operations. Recreated clusters must be deliberately reviewed
before replacing the local identity record.

OpenTofu 1.10.6 with the locked Kubernetes provider 2.38.0 owns four namespaces,
quotas, limits, observer RBAC, and NetworkPolicies. Namespace destruction is
prevented in this increment. The observer role grants read access to workload
status/logs, not Secrets, and binds only the named observer group. Application
service accounts receive no Kubernetes API permissions or mounted API tokens.

Helm owns the API, worker, tools, orders, PostgreSQL, their Services/service
accounts, and the schema migration Job. PostgreSQL uses a 2 GiB persistent claim
on Minikube's `standard` storage class. A pod restart retains the volume; this is
not a backup or protection from deletion of the entire VM. No application
resource is simultaneously managed by OpenTofu.

The migration is a normal versioned Job, allowing PostgreSQL and the job to become
ready before Helm's combined workload/job wait finishes. Application containers
use restricted roles; only that job receives the owner credentials. The local
credential injector owns pre-existing Secrets, keeping secret values out of
Helm values/release configuration and OpenTofu state. Restore the private
credential file if persistent data already exists; do not generate new passwords
for an existing database.

All application containers are non-root, have dropped capabilities, read-only
root filesystems, resource bounds, and probes. Services are ClusterIP only.
The UI is reached using an explicit localhost port-forward. Python and PostgreSQL
base images are pinned by digest in `config/images.json`; the application image
has a source-content tag and is loaded directly into the dedicated Minikube VM.

## Effect ownership across service boundaries

The worker calls the tool gateway using a worker credential. The gateway calls
the separate orders service using a distinct service credential. The worker's
credential does not authenticate at the orders endpoint.

The gateway independently checks identity, scope, arguments, approval, and
idempotency binding using a read-only database role. Orders validates again and
owns the transaction that consumes approval, applies the simulated effect, and
records the idempotency result. Separating that transaction across two services
would lose the T03 guarantee after a lost response. The T03 backend is therefore
reused as the orders effect owner. The deterministic adapter remains an in-process
worker component; it does not require another network endpoint in M1.

The deployed orders role may access jobs, approvals, deduplication, and simulator
state. This adds an explicit orders-to-database network flow to the initial PRD
proposal. The tools role cannot modify simulator state or consume an approval in
cluster mode. The local T03 harness remains compatible with its original grants.

## Network policy contract

Four default-deny policies select all pods for both ingress and egress.
Four DNS policies permit only UDP/TCP 53 to the kube-system DNS pods. Seven
application paths each have a matching ingress and egress policy (14 policies).
Namespace and pod selectors occur in the same peer so both must match.

| Source | Destination | TCP port |
| --- | --- | --- |
| API | PostgreSQL | 5432 |
| Worker | PostgreSQL | 5432 |
| Worker | Tools | 8080 |
| Tools | PostgreSQL | 5432 |
| Tools | Orders | 8080 |
| Orders | PostgreSQL | 5432 |
| Migration Job | PostgreSQL | 5432 |

No general internet egress is allowed. API/worker cannot directly reach orders;
unauthorized pods cannot reach database/tools. Host access via port-forward and
node-origin probes are separate from pod-to-pod permission tests. A trusted
administrator who can edit policies/labels or use pod exec/port-forward can
bypass these workload restrictions; NetworkPolicy is not an administrator sandbox.

Telemetry workloads are not deployed yet. `lab-observability` is denied by
default with DNS allowed. T06 must add exact collector/metrics/dashboard flows
alongside their actual workloads; this checkpoint makes no telemetry connectivity
claim. Standard NetworkPolicy does not enforce HTTP identity or DNS-name-based
internet allowlists. Service authentication and approval remain independent.

## Evidence

`make verify-cluster` covers deployed behavior, readiness, persistence across
PostgreSQL pod replacement, localhost API access, and a stable post-apply plan.
`make verify-network` runs literal-IP TCP checks from real pods with two-second
connection timeouts, positive controls to the protected services, DNS validation,
an external host reachability control, and workload internet denials. HTTP 401,
403, and 200 checks run over the explicitly allowed worker-to-tools path.
The disposable unprivileged test pod is removed in a bounded cleanup step.

See [Progress](../PROGRESS.md) for executed results and the
[platform demonstration](../PLATFORM_DEMO.md) for reproduction.

References:

- [Minikube QEMU networking](https://minikube.sigs.k8s.io/docs/drivers/qemu/).
- [Minikube start options](https://minikube.sigs.k8s.io/docs/commands/start/).
- [Kubernetes NetworkPolicy semantics](https://kubernetes.io/docs/concepts/services-networking/network-policies/).
