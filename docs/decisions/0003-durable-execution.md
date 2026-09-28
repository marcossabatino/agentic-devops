# ADR 0003 — PostgreSQL jobs and approval-bound simulated effects

Date: 2026-09-28. Status: implemented and locally verified for T03.

## Context and decision

T02 retains the lightweight synchronous, in-memory demo. T03 adds an asynchronous
PostgreSQL mode: the API returns HTTP 202 with a run ID, a worker claims work, and
the interface polls until completion, failure, or a pending approval. PostgreSQL
is both the durable job queue and the history store; no message broker is added.

The user requested delivery of the next task. The claim/lease proposal was
presented in the session; implementation continued with that stated default.
PostgreSQL 16.13 was already installed on the host. The local harness starts its
own private cluster, rather than modifying an existing database or Minikube.
Psycopg and its binary distribution are pinned to 3.2.10.

## Claim and execution contract

- An atomic `UPDATE` with a `FOR UPDATE SKIP LOCKED` candidate claims one job.
  Every claim gets a new random lease token. Database time determines expiration.
- A lease lasts three seconds by default and renews when reserving a step.
  Every worker write checks the current token, status, deadline, and lease while
  holding the row lock. A former owner cannot overwrite a recovered execution.
- Step reservations are committed **before** calling a tool. A crash can consume
  a step without a result, but cannot reset the five-step budget. Events preserve
  the started call, including calls abandoned before their result was recorded.
- Jobs have a 30-second execution deadline (including queue wait), three total
  claims, a 0.5-second tool timeout, and up to two transient retries with bounded
  exponential backoff and jitter. Tool retries also consume steps.
- Claim processing reaps expired jobs and exhausted attempts into visible failed
  states. A stopped worker delays this cleanup until a worker resumes.
- Approval waiting releases the lease and uses a separate 300-second window.
  Approval grants a new execution deadline; it does not reset steps or claims.
- Limits are configurable in `scripts.durable_demo`; run it with `--help`.

The adapter remains deterministic and local. `step-limit` intentionally keeps
asking for the health tool. `tool-timeout` uses a bounded delayed HTTP response.
A completed diagnosis with a degraded outcome is successful diagnosis execution,
not a healthy orders service.

## Authorization, approval, and idempotency

Credentials are generated locally and stored in a mode-0600 file under a
mode-0700 ignored directory. Tokens are not printed or included in reports.
The browser uses a lab-user bearer token, held only in the current page. Worker
credentials have tool scopes and cannot approve actions. Identity and scopes
come from the service's configured credential registry, not request fields.

Only the authenticated lab user can approve the exact pending run/tool/arguments.
The tool service independently validates bearer credentials, scopes, allowed
arguments, approval binding, expiration, and an idempotency key. API, worker,
and tools use distinct restricted PostgreSQL roles. The worker cannot create
approvals or change simulator state; the API cannot access simulator state; the
tools cannot change jobs or the approval identity.

The restart effect is a per-run counter in PostgreSQL. Approval consumption,
effect, and idempotency result commit in **one transaction**. A key lock serializes
concurrent duplicate keys; an approval row lock prevents two different keys from
reusing one approval. Reusing a key with a different run/tool/arguments fails.
An authenticated exact replay returns the stored result, including after a lost
response, approval expiration, or restart, without another effect. New effects
also require an active run within its execution deadline.

This proves one simulated database effect, not exactly-once external execution.
A future separate orders service must provide its own durable idempotency
contract. Retrying an external restart alone would not provide this guarantee.

## Local boundaries and consequences

`make run-durable` runs API, tool HTTP service, and worker in separate threads
within a local harness, using separate DB credentials. The services expose
reusable constructors; container/process packaging is T04. The simulator's
state-changing effect intentionally remains in the tool transaction. The harness
knows all local credentials and is a trusted operator, not a process isolation
boundary. PostgreSQL listens on a private Unix socket; HTTP binds to loopback.

The owner account performs repeatable schema creation/grants during harness
startup. Application accounts never apply migrations. This is a local lab setup,
not a general migration framework or production identity system.

A05 timeout/retry behavior is verified locally; distributed tracing is T06.
Kubernetes isolation, service deployment, health probes, NetworkPolicies, and
observability remain T04–T06. No cluster was created by T03.

## Validation and references

`make verify-durable` exercises real PostgreSQL, HTTP authorization, concurrent
claims and duplicate effects, process termination/recovery, stale owners,
approval changes/expiry, execution limits, restricted roles, and database restart.
See [Progress](../PROGRESS.md) and [durable demo](../DURABLE_DEMO.md).

- [PostgreSQL 16 SELECT / locking](https://www.postgresql.org/docs/16/sql-select.html):
  `SKIP LOCKED` is suitable for multiple consumers of a queue-like table.
- [Psycopg transaction management](https://www.psycopg.org/psycopg3/docs/basic/transactions.html):
  connection contexts commit on success and roll back on exceptions.
