# The Endpoints

There are 9 endpoints serving 3 domains: auth, jobs, and health.

## Health (1 endpoint)

- `GET /health — "Is the process alive and can it handle requests?"

Exists purely for infrastructure. Kubernetes hits this every few seconds to decide whether to route traffic to this pod or kill it. No auth, no business logic, no version prefix — it needs to be the
simplest, fastest thing the API does.

Auth (3 endpoints)

These are the minimum for stateless JWT auth with secure token lifecycle:

POST /auth/register — Creates an account. You need this before anything else works.

POST /auth/login — Exchanges credentials for a token pair (short-lived access token + long-lived refresh token). The access token is what every other endpoint checks. The reason it's short-lived (15
min) is damage limitation — a stolen access token is useless quickly.

POST /auth/refresh — Exchanges a refresh token for a new token pair without re-entering credentials. This is what makes the UX smooth — the client silently refreshes in the background so the user
never gets logged out mid-session. Without this, you'd either need long-lived access tokens (insecure) or force re-login every 15 minutes (hostile UX).

You could skip refresh tokens and just use long-lived access tokens — many demos do. But the rotation + family revocation pattern is a meaningful security feature worth demonstrating.

Jobs (5 endpoints)

These map to the full lifecycle of an async job: create, list, inspect, watch, cancel.

POST /jobs — Submit work. Returns 202 with a job ID. This is the entry point to the entire async flow. Without it, there's nothing to process.

GET /jobs — List your jobs (paginated). The "dashboard view." A user who's submitted multiple jobs needs to see all of them, not just the one they're currently watching. Without this, the client
would need to store every job ID locally.

GET /jobs/{id} — Single job status + download link. This is the polling fallback and the primary way to get results. If SSE disconnects, if the client refreshes the page, if they come back tomorrow —
this endpoint is always there. When the job is done, it includes the presigned download URL.

GET /jobs/{id}/events — SSE stream for real-time updates. This is the "nice UX" layer on top of polling. Instead of the client asking "is it done yet?" every 2 seconds, the server pushes "it's done"
the moment it happens. Strictly optional — the system works without it — but it's the difference between a progress spinner that updates live vs one that lags.

POST /jobs/{id}/cancel — Cancel a pending or in-progress job. Without this, a user who submits the wrong file or changes their mind has no recourse — they just have to wait for it to finish and waste
worker capacity. It's POST (not DELETE) because cancellation is an action with side effects (revoke the queued task, update status), not resource removal. The job record stays for audit.

Why Not More? Why Not Fewer?

You could cut SSE and cancel and still have a working system — that gets you down to 7 endpoints. But SSE is the whole reason Redis pub/sub is in the architecture (it's the demo's "wow factor"), and
cancel is a basic user expectation for any async system.

You could add things like DELETE /jobs/{id} (cleanup old jobs), PATCH /auth/profile (change email/password), GET /jobs/{id}/logs (processing output), POST /auth/logout (explicit token revocation).
But each one adds scope without demonstrating a new architectural concept. The 9 endpoints hit every pattern worth showing: CRUD, async processing, real-time streaming, auth lifecycle, file handling
— without any redundancy.
