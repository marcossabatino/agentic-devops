# CI and validated local deployment

T07 uses GitHub Actions for pull requests and pushes to `main`. Every job runs on
GitHub-hosted `ubuntu-24.04` with read-only repository permission. Third-party
actions are pinned by full commit SHA. There is no self-hosted runner, registry
publication, or cluster credential in CI.

The [CI workflow](../.github/workflows/ci.yml) has three required jobs:

| Job | Checks |
| --- | --- |
| Python and PostgreSQL contracts | Standard-library tests plus disposable native PostgreSQL and HTTP integration tests |
| Ansible, OpenTofu and Helm | Ruff, JavaScript syntax, Ansible lint, OpenTofu format/init/validate, Helm lint/template |
| Build application image | Docker build from the digest-pinned Python base and image inspection |

`make verify-static` runs the infrastructure and chart checks locally. These
checks require no Minikube or Kubernetes API. GitHub CI does not attempt an
OpenTofu plan against the operator's private lab, and does not receive the
kubeconfig, Terraform state, database passwords or tool credentials. The image
job builds but does not publish the image.

## Demonstrate a rejected change

A pull request with invalid Python syntax or failing tests must show a failed
Python check. Fix the change and push again; the same pull request must turn
green. T07 validation used a temporary pull request with one deliberate syntax
error. The failure and successful follow-up run are recorded in
[PROGRESS.md](PROGRESS.md). No deliberate failure is included in `main`.

## Deploy the validated commit

From a clean `main` checkout after its push workflow succeeds:

```sh
git fetch origin
make bootstrap
make infra-plan
make infra-apply
make deploy
make verify-cluster
make ui
```

Inspect the saved OpenTofu plan before applying. `make deploy` requires the full
local `HEAD` to equal `origin/main` and a completed, successful **push** run of
this repository's `ci.yml` for that exact SHA. It checks these before writing
secrets, building an image or changing the cluster. A pull-request run alone
cannot authorize a deploy. `gh` must be authenticated to read the workflow run;
if GitHub is unavailable, validated deployment stops without claiming CI proof.

The local build uses the pinned Python image digest and loads its content-tagged
image into the dedicated Minikube profile. The full commit SHA appears in the
interface, API info, new run records and application startup logs. The private
`data/platform/build.json` also records the CI run ID and URL, image ID, image
tag, PostgreSQL image and guarded cluster identity. Compare its
`source_revision` with `git rev-parse HEAD` and the GitHub run link; use
`make verify-cluster` to check the deployed revision and image.

A clean source tree is part of this contract. Commit a further documentation or
code change, wait for its own successful push run, and deploy that new SHA; an
older green run does not validate new contents. Routine unvalidated local
experiments can still use the standalone simulation (`make run` or
`make run-durable`) without labeling a cluster deployment as CI-validated.
