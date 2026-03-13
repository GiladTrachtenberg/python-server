# CLAUDE.md — Agent Instructions

## Role

Senior backend engineer. Communicate in explanatory style — surface tradeoffs,
explain *why* not just *what*. Ask before making irreversible changes.

## Project

Video processing demo: FastAPI + Celery + Redis + Postgres + MinIO, deployed on
Kind (K8s) with ArgoCD. Interview-grade showcase of async job processing.

## Pointer Index

| Domain              | File                          | Lines     |
|---------------------|-------------------------------|-----------|
| Download flow       | `docs/DOWNLOAD-FLOW.md`       | full file |
| Local dev setup     | `docs/LOCAL-DEV.md`           | full file |
| API overview        | `docs/API-OVERVIEW.md`        | full file |
| API endpoints       | `docs/demo-architecture.md`   | 84-103    |
| Status codes        | `docs/demo-architecture.md`   | 105-119   |
| Error/success envel | `docs/demo-architecture.md`   | 120-158   |
| Pagination          | `docs/demo-architecture.md`   | 160-165   |
| Rate limiting       | `docs/demo-architecture.md`   | 167-180   |
| Data models         | `docs/demo-architecture.md`   | 182-207   |
| Request/response    | `docs/demo-architecture.md`   | 209-246   |
| Auth flow           | `docs/demo-architecture.md`   | 248-262   |
| Dockerfile          | `docs/demo-architecture.md`   | 265-316   |
| Helm chart          | `docs/demo-architecture.md`   | 319-514   |
| CI/CD (ArgoCD)      | `docs/demo-architecture.md`   | 517-564   |
| Project structure   | `docs/demo-architecture.md`   | 568-617   |
| Implementation plan | `docs/demo-architecture.md`   | 620-649   |
| DB config           | `src/db.py`                   | full file |
| ORM models          | `src/models.py`               | full file |
| Auth implementation | `src/auth.py`                 | full file |
| Auth schemas        | `src/auth_schemas.py`         | full file |
| Rate limiting       | `src/rate_limit.py`           | full file |
| Frontend source     | `web/src/`                    | 8 files   |
| Frontend API client | `web/src/api.ts`              | full file |
| Vite config + proxy | `web/vite.config.ts`          | full file |
| SSE auth (scoped)   | `src/auth.py`                 | `CurrentUserSSE` |
| Tortoise fallback   | `src/main.py`                 | line 29   |
| Frontend plan       | `STATE.md`                    | Steps 9-10|
| Frontend decisions  | `docs/ARCHITECTURE.md`        | D18-D21   |
| Key decisions       | `docs/ARCHITECTURE.md`        | full file |
| Deploy structure    | `docs/ARCHITECTURE.md` D16    | —         |
| Current state       | `STATE.md`                    | full file |
| Context protocol    | `docs/CONTEXT-PROTOCOL.md`    | full file |

## Code Standards

| Tool            | Rationale                                                  |
|-----------------|------------------------------------------------------------|
| **ruff**        | Replaces black + isort + flake8; Rust-based, sub-second    |
| **mypy strict** | Greenfield = no legacy untyped code to fight               |
| **pytest**      | De facto standard; fixture-based; pytest-asyncio for async  |
| **uv**          | Already in architecture; 10-100x faster than pip           |
| Python 3.14     | Matches Dockerfile in demo-architecture.md                 |

## Conventions

- Type annotations on all functions and module-level variables
- `from __future__ import annotations` in every module (PEP 563)
- Pydantic models at API boundaries (request/response schemas)
- Configuration via environment variables (never hardcoded)
- Async by default — sync only when forced by a library
- Run uvicorn with `--factory`: `uvicorn src.main:create_app --factory`
- Immutable data patterns — return new objects, never mutate in place
- Files: 200-400 lines typical, 800 max

## CI/CD

- **CI**: GitHub Actions (lint, type-check, test, build image)
- **CD**: ArgoCD watching `deploy/` on main branch
- **Deploy layout**: `deploy/{app,infra,argocd,sealed-secrets,kind}/`

## Git Rule

**Never commit or push.** The user handles all git operations.

## Context Updates

See `docs/CONTEXT-PROTOCOL.md` for when and how to propose updates.
