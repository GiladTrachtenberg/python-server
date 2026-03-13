<!-- STATE.md — must stay under 80 lines -->

# Project State

## Current Phase

**Phase 3: Kubernetes** — Step 11 of 12

## Progress

| Step | Description                                      | Status      |
| ---- | ------------------------------------------------ | ----------- |
| 1    | FastAPI skeleton with /healthz + /readyz         | DONE        |
| 2    | Tortoise ORM models + Aerich migrations setup    | DONE        |
| 3    | Auth (register, login, refresh with rotation)    | DONE        |
| 4    | Jobs API + Celery worker + MinIO + SSE           | DONE        |
| 5    | Rate limiting + Dockerfile + CI                  | DONE        |
| 6    | React frontend (auth, jobs, SSE, download)       | DONE        |
| 7    | Frontend Dockerfile + CI + Helm values           | DONE        |
| 8    | Helm chart + Kind cluster + K8s manifests        | DONE        |
| 9    | ArgoCD + Sealed Secrets setup on Kind            | DONE        |
| 10   | ApplicationSet + sync waves (full GitOps deploy) | DONE        |
| 11   | Fix CI workflows (dev deps, casing, versions)    | DONE        |
| 12   | End-to-end validation on Kind (full stack)       | NOT STARTED |

## Up Next — Step 12: End-to-End Validation on Kind

- Run bootstrap.sh on Kind cluster
- Full flow via frontend: register, login, create job, watch SSE, download
- Validate ArgoCD sync status for all Applications

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

## Blocked

(nothing blocked)
