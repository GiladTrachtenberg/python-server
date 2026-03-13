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

ArgoCD uses multi-source Applications — chart from `python-server-infra` repo,
values from this repo (`deploy/app/values-*.yaml`, `deploy/web/values-web.yaml`).
ApplicationSet with sync waves deploys all components in order: CNPG(1) →
Redis(2) → MinIO(3) → API(4) → Worker(5) → Web(6). PreSync hooks handle DB
migrations. Cluster-level operators (CNPG, Sealed Secrets) and ArgoCD itself are
installed by the Kind bootstrap script — they are NOT managed by ArgoCD.

→ `demo-architecture.md:476-514`

### D16: `deploy/` Directory Structure (Two-Repo)

Split across two repos. **This repo** (`python-server-adge`): `deploy/app/values-api.yaml`,
`values-worker.yaml`, `deploy/web/values-web.yaml` — app-specific values only.
**Infra repo** (`python-server-infra`): `deploy/app/` (shared Helm chart + defaults),
`deploy/infra/` (CNPG/Redis/MinIO), `deploy/kind/` (cluster setup),
`deploy/argocd/`, `deploy/sealed-secrets/`.

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

### D23: Frontend Container (nginx + envsubst)

Multi-stage Dockerfile: `node:22-alpine` builds the Vite SPA, `nginx:alpine` serves
it. nginx proxies `/api/` to the backend with SSE buffering disabled (`proxy_buffering
off`, `proxy_cache off`, `X-Accel-Buffering no`). The upstream address is templated
via `envsubst` at container start (`API_UPSTREAM` env var) — works for both local
Docker Compose and K8s without maintaining two configs. Port 80 inside the container
(not 8080). Image tag is intentionally empty in `values-web.yaml` — must be set at
deploy time (git SHA from CI) to ensure ArgoCD detects drift.

→ `web/Dockerfile`, `web/nginx.conf.template`, `deploy/web/values-web.yaml`

### D24: Kind NodePort Pattern (No Ingress Controller)

Kind cluster maps `extraPortMappings` from host ports (8082/9443) to NodePort
range (30080/30443). Services use `type: NodePort` to expose directly — no nginx
ingress controller needed. Simplest networking pattern for a local demo. Port 8080
is reserved (user's client occupies it).

→ `python-server-infra/deploy/kind/kind-config.yaml`, `bootstrap.sh`

### D25: Wrapper Charts for Infrastructure Dependencies

Redis and MinIO are deployed as small "wrapper" Helm charts that declare the
upstream chart (bitnami/redis, minio/minio) as a dependency. This lets ArgoCD
manage them as Helm releases with pinned versions and custom values, without
vendoring the upstream charts. `helm dependency build` resolves them.

→ `python-server-infra/deploy/infra/redis/Chart.yaml`, `minio/Chart.yaml`

### D26: Two-Repo Split (App + Infra)

Helm chart, Kind config, bootstrap scripts, and infrastructure manifests live in
a separate `python-server-infra` repo. This repo keeps only app-specific values
files (`deploy/app/values-api.yaml`, `values-worker.yaml`, `deploy/web/values-web.yaml`).
ArgoCD uses multi-source Applications — chart from infra repo, values from app repo.
CI in this repo builds images, pushes to GHCR, and updates `image.tag` in the
values files (same-repo commit). Clean separation: app developers change values,
infra changes go through the infra repo.

→ `python-server-infra/deploy/`, `deploy/app/values-*.yaml`

### D27: ArgoCD Bootstrap (Not Self-Managed)

ArgoCD is installed via `bootstrap.sh` (Helm) alongside CNPG and Sealed Secrets
operators. It is NOT managed by an ArgoCD Application — avoids the self-management
bootstrap paradox. Accessible at `localhost:9090` via NodePort 30090 (insecure
mode for local Kind). Initial admin password retrieved from `argocd-initial-admin-secret`.

→ `python-server-infra/deploy/kind/bootstrap.sh`, `kind-config.yaml`

### D28: SealedSecrets Strategy

Three layers: infra secrets (cnpg-app-creds, redis-password, minio-creds) are
standalone SealedSecrets consumed by upstream Helm charts. `app-shared-secrets`
holds connection strings both API and Worker need (DATABASE_URL, REDIS_URL,
CELERY_BROKER_URL, MINIO_*). `app-api-secrets` holds JWT_SECRET_KEY (API only).
Helm chart uses `sharedSecrets` list — each component declares which secrets it
needs. Worker gets `[app-shared-secrets]`, API gets `[app-shared-secrets, app-api-secrets]`.
`seal-secrets.sh` generates all sealed YAML files and handles GHCR pull secret.
Must re-run after cluster recreation (cluster-bound encryption).

→ `python-server-infra/deploy/sealed-secrets/seal-secrets.sh`

### D29: Path-Filtered CI with GitOps Tag Update

Single `ci.yml` replaced by `ci-backend.yml` (src/, tests/, Dockerfile, pyproject.toml)
and `ci-frontend.yml` (web/). On main push: lint → test → build+push to GHCR →
update `image.tag` in values files → commit with `[skip ci]`. Path filters prevent
cross-triggering. `GITHUB_TOKEN` provides both GHCR push and repo write. Images
pulled from GHCR in Kind via `ghcr-pull-secret` imagePullSecret.

→ `.github/workflows/ci-backend.yml`, `.github/workflows/ci-frontend.yml`

### D7: Toolchain Selection

| Tool       | Why                                                        |
|------------|------------------------------------------------------------|
| ruff       | Replaces black + isort + flake8; Rust-based, sub-second    |
| mypy       | Strict mode — greenfield, no legacy untyped code           |
| pytest     | De facto standard; fixture-based; pytest-asyncio for async |
| uv         | Already in architecture; 10-100x faster than pip           |
| Python 3.14| Matches Dockerfile; latest stable                         |
