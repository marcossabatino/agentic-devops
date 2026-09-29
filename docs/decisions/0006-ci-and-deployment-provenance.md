# ADR 0006 — GitHub CI and validated local deployment

- Date: 2026-09-29
- Status: Accepted for local M1
- Scope: T07

## Decision

Run three read-only, SHA-pinned GitHub Actions jobs on pull requests and main
pushes: application/PostgreSQL contracts, cluster-free infrastructure/manifest
validation, and a Docker image build. Do not publish the image in M1. Pull
requests cannot access the private lab or its secrets. A GitHub-hosted runner
cannot plan against the localhost-only Kubernetes API.

Before `make deploy` mutates lab resources, require a clean local `main` checkout
whose full HEAD equals `origin/main`, and a completed successful CI push run for
that exact SHA. A successful pull-request run is insufficient. Build/load the
image locally with the existing content tag, and record full commit SHA, CI run,
image ID and cluster identity in private local metadata. Inject the full SHA into
all application workloads so it appears in the interface, run history and logs.

## Consequences

GitHub access and authenticated `gh` are needed at deploy time. The rule is
fail-closed: no CI proof means no validated cluster deployment. This avoids
accidentally presenting a dirty worktree or a locally rebuilt image as the
validated commit. It also means subsequent source changes require another push
and green run before redeployment. The local Minikube build still avoids any
container registry or new registry credential.

The intentional failing PR is limited to a temporary branch. Its failed check
proves the workflow rejects a real code error; a green follow-up run proves the
correction. T08 remains responsible for consolidated acceptance and cleanup.
