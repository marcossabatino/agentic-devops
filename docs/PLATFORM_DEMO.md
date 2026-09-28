# Deployed local platform — T04/T05

This mode deploys the simulated diagnosis application into the dedicated
`agentic-devops` QEMU Minikube profile. It preserves other profiles and the global
kubectl context. Prerequisites remain the pinned tools in `config/lab.json` plus
a working Docker daemon for image builds. Ansible checks these prerequisites;
it does not silently upgrade host tools.

## Reproduce the platform

```sh
make doctor
make bootstrap
make infra-plan
# Inspect the plan: only this lab's namespaces and platform resources.
make infra-apply
make deploy
make verify-cluster
make verify-network
make ui
```

Open <http://127.0.0.1:8080>. Read `user_token` from the private local
`data/platform/credentials.json` and enter it in the interface. This is a
separate credential from the T03 standalone demo. Keep the file local: it also
contains service and database credentials. Never paste it into chat or Git.

Use `make ui PORT=8081` if port 8080 is occupied. Ctrl+C stops that port-forward;
it does not remove the deployed services or stop the VM.

All platform commands use `data/platform/kubeconfig`, the explicit
`agentic-devops` context, and a recorded cluster UID. They reject a changed
cluster identity. The shared/default kubeconfig is not required for lab access.

## What is deployed

| Namespace | Resources |
| --- | --- |
| `lab-app` | Interface/API and worker Deployments |
| `lab-tools` | Tool gateway and separate orders simulator Deployments |
| `lab-data` | PostgreSQL StatefulSet, persistent claim, migration Job |
| `lab-observability` | Reserved namespace and baseline controls; telemetry workloads are T06 |

OpenTofu owns namespaces, quota/limit controls, observer RBAC, and NetworkPolicies.
Helm owns application resources. A local credential injector owns Secret values;
they are not passed to Helm or stored in OpenTofu state. Runtime services use
separate database permissions and credentials. The worker's credential is not
valid at the orders service.

Twenty-two NetworkPolicies provide default deny, required DNS, and explicit
application ingress/egress. Orders owns the atomic simulated effect and needs
its own database path. There are no NodePort or LoadBalancer services. The
application image is loaded locally; the base images are pinned by digest.

## Exercise the application

Select healthy, orders-errors, restart-required, tool-timeout, or step-limit.
The [durable demo](DURABLE_DEMO.md) explains the expected outcomes. The deployed
mode now uses real service-to-service HTTP and persistent Kubernetes storage.
A simulated restart still requires explicit user approval and affects only
per-run synthetic state. No LLM or AWS calls occur.

Use these scoped inspection commands:

```sh
kubectl --kubeconfig=data/platform/kubeconfig --context=agentic-devops -n lab-app get pods
kubectl --kubeconfig=data/platform/kubeconfig --context=agentic-devops -n lab-tools get pods
kubectl --kubeconfig=data/platform/kubeconfig --context=agentic-devops -n lab-data get pods,pvc
kubectl --kubeconfig=data/platform/kubeconfig --context=agentic-devops -n lab-tools get networkpolicy
helm --kubeconfig=data/platform/kubeconfig --kube-context=agentic-devops -n lab-app status agentic-devops
```

## Verification boundaries

`make verify-cluster` exercises all five scenarios through a temporary localhost
port-forward, checks workload/Calico readiness, checks internal-only Services,
restarts **only the lab PostgreSQL pod** to verify stored history, and requires
OpenTofu's detailed plan exit code to be zero. It writes the sanitized
`artifacts/t04-cluster.json` and `artifacts/t04-post-apply-plan.log` reports.

`make verify-network` performs positive and negative TCP tests from deployed
workloads and a temporary unprivileged pod. Negative checks use literal Service
IPs and require timeouts, so DNS errors and a closed port do not count as a
passing denial. The internet check uses a host connection to `1.1.1.1:443` as a
positive control; if that endpoint is unreachable from the host, the check fails
instead of claiming the policy blocked it. Missing/invalid credentials and
missing approval are then tested separately on the reachable worker/tools path.
The report is `artifacts/t05-network.json`; the temporary test pod is removed.

`make test` runs the standard-library regression/guard tests. `make setup` and
`make verify-durable` run the real PostgreSQL integration contracts locally,
including the separate gateway/effect-owner contract. These are additional to,
not replacements for, cluster and network verification.

Run `make bootstrap` a second time: an already running matching profile and
unchanged private files should produce `changed=0`. A stopped VM legitimately
requires a changed startup step. After platform apply, the verification plan
must show no unexpected changes. Deployment annotations or Helm history do not
belong to OpenTofu's resource ownership.

## Local state and operation

- Preserve `data/platform/credentials.json` with mode 0600 alongside your lab
  backup; it is required to reconnect to retained database data.
- `data/platform/kubeconfig` and the identity/build records are local. OpenTofu
  state and saved plans live under `infra/local/` and are excluded from Git.
- PostgreSQL uses Minikube hostpath storage. Pod replacement preserves history;
  destroying the VM can destroy it. This lab does not claim HA or backup recovery.
- To stop compute without deleting data, use `minikube stop -p agentic-devops`.
  `make bootstrap` starts the same profile again. Full scoped deletion remains T08.
- If a migration fails, inspect only its Job logs in `lab-data`. Do not rotate
  credentials or delete the database to hide a failed migration.
- The source revision may include `-dirty` until the code is committed. T07 will
  add GitHub CI provenance; a local image build is not evidence of passing CI.

The next implementation task is T06: instrument the existing execution with
correlated logs, metrics and traces, deploy the observability releases, and add
only their necessary network flows.
