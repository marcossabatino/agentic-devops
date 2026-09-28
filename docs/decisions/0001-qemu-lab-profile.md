# ADR 0001 — Dedicated QEMU Minikube profile

Date: 2026-09-27
Status: accepted by the user

## Context and decision

The host already has a stopped QEMU-based `minikube` profile. The user chose QEMU for this lab. Use a separate `agentic-devops` profile with the explicit `qemu2` driver, four CPUs, 8192 MiB RAM, and Calico. Keep the existing profile intact. Future cluster commands must name the lab profile/context explicitly and bootstrap must preserve the current context.

QEMU gives the lab a VM with its own kernel. KVM device access and QEMU/qemu-img 9.2.4 were verified on this Linux x86_64 host. This is prerequisite evidence, not proof that a new VM or cluster starts successfully.

## Networking and boundaries

Use `builtin` networking on this Linux host. The [Minikube QEMU documentation](https://minikube.sigs.k8s.io/docs/drivers/qemu/) states that `minikube service` and `minikube tunnel` are unavailable with this network. The planned UI/dashboard access remains `kubectl --context=agentic-devops port-forward --address=127.0.0.1`; validate it after deployment.

A VM separates the lab from the host at the kernel boundary. Calico NetworkPolicies still need to restrict pod connections, and the tool service still needs to authorize requests. Neither VM isolation nor a passing prerequisite check proves these controls work.

## Initial version baseline

Machine-readable settings and exact CLI pins are in [config/lab.json](../../config/lab.json). Retain the installed Minikube, kubectl, QEMU, Ansible, and Helm versions to avoid unrelated upgrades during this increment. Select Kubernetes 1.34.12 to match the installed kubectl patch rather than copying the older 1.34.0 version of the unrelated profile.

- [Minikube v1.37.0 release notes](https://github.com/kubernetes/minikube/releases/tag/v1.37.0) add Kubernetes 1.34 support.
- The [Kubernetes version skew policy](https://kubernetes.io/releases/version-skew-policy/#kubectl) permits kubectl within one minor version of the API server; the selected client and server use the same minor.
- [OpenTofu v1.10.6](https://github.com/opentofu/opentofu/releases/tag/v1.10.6) is the initial reproducible CLI target, not a claim about the latest release. It was installed in T01. T04 pins the Kubernetes provider to 2.38.0 in the committed lock file.

These references establish the initial selection, not an end-to-end compatibility result. Cluster startup, the exact Calico release, provider/chart pins, and integration behavior must be validated in the bootstrap/infrastructure increment. No Calico or observability chart version has been selected yet.

T04 validation update: the dedicated cluster is running Kubernetes 1.34.12,
containerd 1.7.23, and bundled Calico 3.30.3. Loopback port-forward, workload
readiness, bootstrap repetition, and network isolation passed; see
[ADR 0004](0004-local-platform-and-network.md). Observability chart pins remain T06.
