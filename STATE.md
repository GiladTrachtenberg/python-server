<!-- STATE.md — must stay under 80 lines -->
# Project State

## Current Phase

**Phase 1: Core Application** — Step 2 of 7

## Phase 1 Progress

| Step | Description                                      | Status      |
|------|--------------------------------------------------|-------------|
| 1    | FastAPI skeleton with /healthz + /readyz          | DONE        |
| 2    | Tortoise ORM models + Aerich migrations setup    | NOT STARTED |
| 3    | Auth (register, login, refresh with rotation)    | NOT STARTED |
| 4    | Job creation endpoint + Celery task (stub)       | NOT STARTED |
| 5    | MinIO integration (upload + presigned URL)       | NOT STARTED |
| 6    | SSE endpoint with Redis pub/sub                  | NOT STARTED |
| 7    | GET /jobs (list) and GET /jobs/{id} (status)     | NOT STARTED |

## Up Next — Step 2: Tortoise ORM + Aerich

- `src/db.py` — Tortoise ORM config (DB URL, models list)
- `src/models.py` — User, Job, RefreshToken models
- `aerich.ini` — Aerich configuration
- `migrations/` — initial migration
- `tests/` — model tests with testcontainers (Postgres)

## Completed

- **Step 1**: FastAPI skeleton — app factory, `/healthz`, `/readyz`, `/api/v1/` router, error envelope, ruff + mypy strict + 4 tests passing

## Blocked

(nothing blocked)

## Key Files Created

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Agent instructions |
| `STATE.md` | Project state tracking |
| `docs/demo-architecture.md` | Full architecture plan |
| `docs/ARCHITECTURE.md` | Key decisions with rationale |
| `docs/API-OVERVIEW.md` | High-level API endpoint rationale |
| `docs/CONTEXT-PROTOCOL.md` | Context update protocol |
| `pyproject.toml` | Project config, deps, tool settings |
| `src/main.py` | FastAPI app factory, health routes, error handler |
| `src/config.py` | Settings from env vars (pydantic-settings) |
| `src/schemas.py` | ErrorResponse + HealthResponse envelopes |
| `tests/conftest.py` | AsyncClient fixture for testing |
| `tests/test_health.py` | Health endpoint tests (4 tests) |

## Known Issues

(none)
