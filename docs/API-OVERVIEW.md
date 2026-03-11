# API Endpoint Overview

Why each endpoint exists and what it does. Language-agnostic design rationale.

## Infrastructure (2 endpoints)

### `GET /healthz` — Liveness Probe

"Is the process alive and can it respond?" Kubernetes hits this every few
seconds. If it fails, k8s kills the pod and restarts it. No auth, no business
logic, no version prefix — the simplest, fastest thing the API does.

### `GET /readyz` — Readiness Probe

"Can this pod actually serve traffic?" Checks connectivity to Postgres
(`SELECT 1`) and Redis (`PING`). If it fails, k8s removes the pod from the
Service (stops routing traffic) but doesn't kill it. A pod can be live but not
ready — for example, during startup before the DB connection pool is
established, or if Redis goes down temporarily.

## Auth (3 endpoints)

The minimum for stateless JWT auth with secure token lifecycle.

### `POST /api/v1/auth/register`

Creates an account. You need this before anything else works.

### `POST /api/v1/auth/login`

Exchanges credentials for a token pair: short-lived access token (15 min) +
long-lived refresh token (7 days). The access token is what every other endpoint
checks. Short-lived for damage limitation — a stolen access token is useless
quickly.

### `POST /api/v1/auth/refresh`

Exchanges a refresh token for a new token pair without re-entering credentials.
This is what makes the UX smooth — the client silently refreshes in the
background so the user never gets logged out mid-session. Without this, you'd
either need long-lived access tokens (insecure) or force re-login every 15
minutes (hostile UX).

Tokens are grouped into families. If a previously-used token is presented
(indicating theft), the entire family is revoked, forcing re-login.

## Jobs (5 endpoints)

The full lifecycle of an async job: create, list, inspect, watch, cancel.

### `POST /api/v1/jobs`

Submit work. The API generates the job UUID, inserts a row into Postgres
(status: `pending`), dispatches a Celery task with the job ID, and returns
`202 Accepted` with the job ID immediately. The API owns the ID because:

- It must return the ID to the client in the 202 response before any worker
  picks it up
- The DB row must exist before the worker starts (workers update rows, they
  don't create them)
- No race condition between client receiving an ID and the row existing

Request body contains job parameters (no query params — those are for filtering
reads, not creating resources).

### `GET /api/v1/jobs`

List your jobs (paginated, offset-based). The "dashboard view." A user who's
submitted multiple jobs needs to see all of them, not just the one they're
currently watching. Without this, the client would need to store every job ID
locally.

### `GET /api/v1/jobs/{id}`

Single job status + download link. The polling fallback and the primary way to
get results. If SSE disconnects, if the client refreshes the page, if they come
back tomorrow — this endpoint is always there. When the job is done, it includes
a presigned download URL (time-limited, signed by object storage — the API never
streams files directly).

### `GET /api/v1/jobs/{id}/events`

SSE stream for real-time updates. Instead of the client asking "is it done yet?"
every 2 seconds, the server pushes "it's done" the moment it happens. Strictly
optional — the system works without it via polling — but it's the difference
between a progress spinner that updates live vs one that lags.

The API subscribes to a Redis pub/sub channel for the job ID. Workers publish
to that channel when status changes. Workers never call the API — they
fire-and-forget the pub/sub message and move on.

### `POST /api/v1/jobs/{id}/cancel`

Cancel a pending or in-progress job. Without this, a user who submits the wrong
file has no recourse — they just wait and waste worker capacity. Uses `POST`
(not `DELETE`) because cancellation is an action with side effects (revoke the
queued Celery task, update status to `cancelled`). The job record stays for
audit purposes.

## Why This Number?

**10 endpoints** across 3 domains. Each one demonstrates a distinct pattern:

| Pattern                        | Endpoint(s)                    |
|--------------------------------|--------------------------------|
| Resource creation (async)      | `POST /jobs`                   |
| Resource listing (paginated)   | `GET /jobs`                    |
| Resource detail + file access  | `GET /jobs/{id}`               |
| Real-time streaming (SSE)      | `GET /jobs/{id}/events`        |
| Action on resource             | `POST /jobs/{id}/cancel`       |
| Stateless auth (JWT)           | `/auth/login`, `/auth/refresh` |
| Account creation               | `/auth/register`               |
| Infrastructure probes          | `/healthz`, `/readyz`          |

Cutting SSE and cancel would still work (8 endpoints) but SSE is the demo's
real-time showcase, and cancel is a basic user expectation for any async system.

Adding more (delete jobs, update profile, processing logs) would increase scope
without demonstrating new architectural concepts.
