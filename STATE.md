<!-- STATE.md — must stay under 80 lines -->

# Project State

## Current Phase

**Phase 4: Refinement** — Step 13

## Progress

| Step | Description                                      | Status      |
| ---- | ------------------------------------------------ | ----------- |
| 1-12 | Phases 1-3 (API, Frontend, Kubernetes)           | DONE        |
| 13   | Refactor infra charts to direct Helm repo sources | NOT STARTED |

## Up Next — Step 13: Infra Chart Refactor

- Refactor Redis/MinIO from wrapper charts to direct Helm repo sources in ApplicationSet
- Remove `deploy/infra/redis/` and `deploy/infra/minio/` wrapper charts
- Values specified inline via `valuesObject` in ApplicationSet generator

## Completed

- **Step 1-3**: FastAPI skeleton, ORM + migrations, auth with token rotation
- **Step 4**: Jobs CRUD, Celery task (generates 5-50MB files), MinIO, SSE
- **Step 5**: Rate limiting (slowapi), Dockerfile, .dockerignore, GitHub Actions CI
- **Step 6**: React SPA (`web/`), scoped SSE query-param auth, Tortoise 1.1.x global fallback fix
- **Step 7**: Frontend Dockerfile (multi-stage nginx), nginx.conf.template (envsubst + SSE proxy), CI jobs, `deploy/web/values-web.yaml`
- **Step 8**: Shared Helm chart + Kind config + infra charts → moved to `python-server-infra` repo. App-specific values remain in `deploy/app/` + `deploy/web/`. GHCR for images, CI updates tags in-repo.
- **Step 9**: ArgoCD in bootstrap, SealedSecrets (shared + individual), seal-secrets.sh, split CI (ci-backend.yml + ci-frontend.yml with GHCR push + tag update), imagePullSecrets for GHCR.
- **Step 10**: Single ApplicationSet with RollingSync strategy (progressive sync). Go template conditionals for single-source (infra) vs multi-source (apps). Per-component release names (removed hardcoded component suffix from templates). Bootstrap applies sealed secrets + ApplicationSet.
- **Step 11**: Fixed CI: `--extra dev` for ruff/mypy/pytest, sequential job deps (lint→type-check→test→build), lowercase GHCR image names, bumped action versions (checkout@v6, setup-uv@v7, setup-node@v6, buildx@v4, login@v4). Added exponential-backoff polling to JobsPage. Web NodePort for Kind access.
- **Step 12**: E2E validation on Kind. Bootstrap creates 3-node cluster, installs operators, seals secrets, deploys ApplicationSet. Validate script checks ArgoCD sync, pod health, full user flow (register→login→job→SSE→download→refresh). Fixed: multi-arch images, templatePatch for goTemplate, service name mismatches, MinIO memory, Redis chart v23, migration init container for PG readiness, web init container for API readiness, consolidated secrets, split WorkerSettings/Settings.

## Blocked

(nothing blocked)
