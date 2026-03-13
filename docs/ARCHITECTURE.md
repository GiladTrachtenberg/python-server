# Architecture Decisions

Key decisions with rationale. References point to `demo-architecture.md` to
avoid duplication.

## Decisions

### D1: Single Docker Image for API + Worker

One image, entrypoint determines role (uvicorn vs celery). Simplifies CI — one
build, one push, one tag. Workers and API always run the same code version.

→ `demo-architecture.md:265-316`

### D2: GitHub Actions for CI

User preference over Argo Workflows. GitHub Actions is simpler to set up, runs
outside the cluster, and avoids the operational overhead of Argo Workflows +
Events + Kaniko inside Kind. Argo Workflows remains documented in the
architecture as an optional Phase 4 addition.

### D3: ArgoCD for CD (GitOps)

ArgoCD watches `deploy/` on main branch. ApplicationSet with sync waves deploys
all components in order: CNPG(1) → Redis(2) → MinIO(3) → API(4) → Worker(5) →
Web(6). PreSync hooks handle DB migrations. Cluster-level operators (CNPG,
Sealed Secrets) and ArgoCD itself are installed by the Kind bootstrap script
(`deploy/kind/bootstrap.sh`) — they are NOT managed by ArgoCD.

→ `demo-architecture.md:476-514`

### D16: `deploy/` Directory Structure

All infrastructure and deployment config lives under `deploy/`, the single path
ArgoCD tracks. Subdirectories: `app/` (Helm chart), `infra/` (CNPG/Redis/MinIO
values), `argocd/` (ApplicationSet), `sealed-secrets/`, `kind/` (cluster setup).
Keeps infra concerns out of the source tree.

### D4: Presigned URLs for File Downloads

API generates time-limited, signed MinIO URLs instead of streaming files through
the API server. Avoids tying up workers and memory pressure.

→ `demo-architecture.md:224-229`

### D5: Redis Pub/Sub for SSE

Workers publish status events to Redis channels. API SSE handler subscribes and
forwards to clients. Workers never call the API — decoupled, no auth needed
between services, message loss is acceptable (client falls back to polling).

→ `demo-architecture.md:230-246`

### D6: Celery for Durable Task Processing

Tasks survive API process crashes because they're backed by Redis broker.
Not about concurrency — about decoupling requests from work.

→ `demo-architecture.md:16-18`

### D8: API Version Prefix (`/api/v1/`)

URL path versioning — explicit, cacheable, easy to route. Costs nothing on a
greenfield project and prevents path collisions with any future frontend routes.
No version negotiation needed; just the prefix. `/health` stays outside the
prefix (no auth, easy k8s probing).

→ `demo-architecture.md:84-103`

### D9: Standardized Response Envelopes

All responses wrapped in `{"data": ...}` (success) or `{"error": {...}}` (failure).
Machine-readable `code` + human-readable `message` + optional field-level `details`.
Override FastAPI's default validation handler to match. Single `ErrorResponse`
Pydantic model used everywhere.

→ `demo-architecture.md:120-158`

### D10: Offset-Based Pagination for `GET /jobs`

Jobs are user-scoped (typical user < 100 jobs). Offset is simpler and supports
page jumps. Cursor-based would be overkill for this dataset size. `?page=1&per_page=20`.

→ `demo-architecture.md:160-165`

### D11: Rate Limiting with slowapi

Redis-backed distributed rate limiting across API replicas. Tighter limits on
auth endpoints (brute-force protection), generous limits on reads. Shows
interview awareness of API hardening.

→ `demo-architecture.md:167-180`

### D12: Split Liveness/Readiness Probes (`/healthz` + `/readyz`)

K8s convention: `/healthz` for liveness (is the process alive? — trivial check),
`/readyz` for readiness (can it serve traffic? — checks Postgres `SELECT 1` +
Redis `PING`). A pod can be live but not ready (e.g., DB unreachable). Without
separate probes, k8s either kills healthy pods or routes to broken ones.

→ `demo-architecture.md:84-103` (endpoint list), `demo-architecture.md:105-119` (status codes)

### D13: Production DB Guard

`model_validator` on `Settings` rejects the local-dev default `database_url` when
`debug=False`. Prevents accidental use of hardcoded credentials in production.
The app refuses to start unless `DATABASE_URL` is explicitly set.

→ `src/config.py`

### D14: Lazy `TORTOISE_ORM` Module Attribute

`src.db.TORTOISE_ORM` is resolved via `__getattr__` instead of a module-level
constant. Avoids triggering `Settings` validation at import time — only evaluated
when Aerich CLI actually reads it.

→ `src/db.py`

### D15: No Module-Level `app` Object

Removed `app: FastAPI = create_app()` from `src/main.py`. Import-time app creation
triggered settings validation and Tortoise config in every module that imported
`src.main`. Use `uvicorn src.main:create_app --factory` instead.

→ `src/main.py`

### D17: Real File Generation in Worker

Celery worker generates 5-50MB random binary files (not videos — content doesn't
matter). Demonstrates realistic object storage usage with presigned URL downloads.
Written in 1MB chunks via `os.urandom` to avoid holding entire file in memory.

→ `src/tasks.py`

### D18: Separate React Frontend (not served from MinIO)

Frontend is a standalone React SPA (Vite + TS) served by its own nginx container.
MinIO is only for backend-generated job output files. Frontend communicates with
the API via nginx reverse proxy (`/api` → FastAPI). Multi-stage Dockerfile:
`node:22-alpine` builds → `nginx:alpine` serves.

### D19: SSE Query-Param Auth Fallback

Browser `EventSource` API cannot set custom headers. The SSE endpoint accepts an
optional `?token=` query parameter as auth fallback alongside the standard
`Authorization: Bearer` header. Token in URL appears in logs — acceptable for demo.
Scoped to SSE only via `CurrentUserSSE` dependency — normal endpoints reject
query-param tokens.

→ `src/auth.py` (`get_current_user_sse`), `src/sse.py`

### D20: Tortoise ORM 1.1.x Global Fallback

Tortoise 1.1+ uses context-based connection management. The FastAPI lifespan
requires `_enable_global_fallback=True` on `Tortoise.init()` so connections
persist across requests. Test fixtures must NOT use this flag — each test creates
a scoped context that's cleaned up by `connections.close_all()`.

→ `src/main.py:29`

### D21: Scoped SSE Auth Dependency

`get_current_user` (header-only) and `get_current_user_sse` (header + query param)
are separate dependencies. Only the SSE endpoint uses the query-param variant,
limiting token-in-URL log exposure to a single endpoint.

→ `src/auth.py`

### D22: Celery Broker URL at App Construction

`Celery()` defaults to `amqp://localhost:5672` (RabbitMQ) when no broker is
specified. The broker URL must be set at app construction time — not inside a
task body — because the worker needs it to connect and receive tasks. Read
`CELERY_BROKER_URL` from env at module level with the same default as
`Settings.celery_broker_url`. Cannot use `Settings()` directly because Pydantic
validation (D13) would reject imports in non-debug environments.

→ `src/tasks.py:23-26`

### D7: Toolchain Selection

| Tool       | Why                                                        |
|------------|------------------------------------------------------------|
| ruff       | Replaces black + isort + flake8; Rust-based, sub-second    |
| mypy       | Strict mode — greenfield, no legacy untyped code           |
| pytest     | De facto standard; fixture-based; pytest-asyncio for async |
| uv         | Already in architecture; 10-100x faster than pip           |
| Python 3.14| Matches Dockerfile; latest stable                         |
