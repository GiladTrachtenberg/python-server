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

ArgoCD watches the repo and syncs K8s state. User-configured — the agent does
not manage ArgoCD resources. PreSync hooks handle DB migrations.

→ `demo-architecture.md:517-564`

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

### D7: Toolchain Selection

| Tool       | Why                                                        |
|------------|------------------------------------------------------------|
| ruff       | Replaces black + isort + flake8; Rust-based, sub-second    |
| mypy       | Strict mode — greenfield, no legacy untyped code           |
| pytest     | De facto standard; fixture-based; pytest-asyncio for async |
| uv         | Already in architecture; 10-100x faster than pip           |
| Python 3.14| Matches Dockerfile; latest stable                         |
