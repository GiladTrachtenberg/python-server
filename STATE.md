<!-- STATE.md — must stay under 80 lines -->
# Project State

## Current Phase

**Phase 1: Core Application** — Step 4 of 5

## Phase 1 Progress

| Step | Description                                      | Status      |
|------|--------------------------------------------------|-------------|
| 1    | FastAPI skeleton with /healthz + /readyz          | DONE        |
| 2    | Tortoise ORM models + Aerich migrations setup    | DONE        |
| 3    | Auth (register, login, refresh with rotation)    | DONE        |
| 4    | Jobs API + Celery worker + MinIO + SSE           | NOT STARTED |
| 5    | DevOps (Dockerfile, Helm, CI/CD, Kind)           | NOT STARTED |

## Up Next — Step 4: Jobs (all features, keep it simple)

- `POST /api/v1/jobs` — create job, dispatch Celery task
- `GET /api/v1/jobs` — list user's jobs (paginated)
- `GET /api/v1/jobs/{id}` — single job status + presigned MinIO URL
- `GET /api/v1/jobs/{id}/events` — SSE via Redis pub/sub
- `POST /api/v1/jobs/{id}/cancel` — cancel pending/processing job
- Celery + Redis: worker sleeps, uploads dummy file to MinIO, marks complete
- MinIO: presigned download URL on completed jobs
- SSE: worker publishes to Redis, API streams to client
- ~5-6 integration tests, no unit tests

## Completed

- **Step 1**: FastAPI skeleton — app factory, health routes, error envelope
- **Step 2**: Tortoise ORM — models, Aerich migration, testcontainers fixtures
- **Step 3**: Auth — register/login/refresh, argon2 + PyJWT, token rotation

## Blocked

(nothing blocked)

## Key Files Created

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Agent instructions + pointer index |
| `docs/demo-architecture.md` | Full architecture plan |
| `docs/ARCHITECTURE.md` | Key decisions with rationale |
| `pyproject.toml` | Project config, deps, tool settings, aerich config |
| `src/main.py` | App factory, health routes, error handler, lifespan |
| `src/config.py` | Settings from env vars + production guards |
| `src/schemas.py` | ErrorResponse + HealthResponse envelopes |
| `src/db.py` | Tortoise ORM config |
| `src/models.py` | User, Job, RefreshToken models |
| `src/auth.py` | Auth router, JWT, password hashing, token rotation |
| `src/auth_schemas.py` | Auth request/response schemas |
| `tests/conftest.py` | Testcontainers Postgres + AsyncClient fixtures |
| `tests/test_auth.py` | Auth integration tests (14 tests) |

## Known Issues

(none)
