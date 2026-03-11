# Video Processing Demo — Architecture Plan

## Interview Talking Points: Tool Choices

Keep these ready — interviewers will ask "why did you choose X over Y" for every major component.

**FastAPI over Django:**
"Django is a full-stack MVC framework — ORM, admin panel, template engine, session management. I'm building a lightweight async API, not rendering HTML. FastAPI gives me native async support (critical for SSE), automatic OpenAPI/Swagger docs for demo purposes, and Pydantic validation with minimal boilerplate. Django's async support exists but isn't first-class."

**Tortoise ORM over SQLAlchemy:**
"SQLAlchemy is the most mature Python ORM, but its power comes with complexity I don't need here. My queries are simple CRUD — create users, create jobs, update job status, look up refresh tokens. Tortoise ORM is async-native from the ground up, which pairs naturally with FastAPI. Its Django-inspired syntax made me productive quickly. For a project with complex queries or joins, I'd reach for SQLAlchemy, but for this scope Tortoise was the right tradeoff — less learning curve, same result."

**Aerich (migrations) over Alembic:**
"Aerich is Tortoise ORM's migration tool. It handles schema diffing and autogeneration similarly to Alembic, but integrates directly with Tortoise models. The tradeoff is a smaller community and less battle-testing than Alembic, which I accepted because this project's schema is simple and stable. If I were on a team maintaining a complex schema long-term, I'd lean toward SQLAlchemy + Alembic for the ecosystem support."

**Celery over threads/asyncio:**
"The key requirement is durability — if the API process crashes, in-flight work must survive. Threads and asyncio tasks die with the process. Celery tasks are backed by a message broker (Redis), so they survive independently. It's not about concurrency models, it's about decoupling the request from the work."

**Presigned URLs over API-served downloads:**
"The API server shouldn't stream large files — it ties up a worker, increases memory pressure, and adds a bottleneck. MinIO (S3-compatible) supports presigned URLs: a time-limited, cryptographically signed URL that lets the client download directly from object storage. The API generates a fresh one on each request; if it expires, the client just asks for another. The object persists regardless."

**Sealed Secrets over Vault:**
"Both solve secret management, but Vault requires deploying and managing a full server — creation, unsealing, policies, auth backends. For a demo on Kind, Sealed Secrets is a Helm install and you're done. You encrypt secrets client-side with kubeseal, commit the SealedSecret CRD safely to git, and the controller decrypts them in-cluster. Every secret in this demo is sealed — including CNPG, Redis, and MinIO credentials."

**Kind over Minikube/k3s:**
"Kind runs K8s inside Docker containers, so it's lightweight and disposable. It supports local registries natively, which I need for the CI/CD pipeline. It's closer to real K8s than k3s (which strips features), and lighter than Minikube."

**Kaniko over BuildKit (for CI):**
"Both build container images, but Kaniko runs as an unprivileged container — no Docker daemon, no root access. In an Argo Workflow step, it's a single container image that builds and pushes. BuildKit can be faster (better caching, parallelism), but needs a daemon or privileged mode. For a demo where I'm already juggling many components, Kaniko's simplicity wins."

---

## System Architecture

### Infrastructure Components

```
                    ┌─────────────┐
                    │   Ingress    │
                    │ (Nginx/Caddy)│
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │                         │
      ┌───────▼───────┐        ┌───────▼───────┐
      │  API Replica 1│        │  API Replica 2│
      │  (FastAPI)    │        │  (FastAPI)    │
      └───────┬───────┘        └───────┬───────┘
              │                         │
              └────────────┬────────────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
   ┌──────▼──────┐ ┌──────▼──────┐ ┌───────▼──────┐
   │    Redis     │ │  Postgres   │ │    MinIO      │
   │   (broker)   │ │  (CNPG)     │ │ (object store)│
   └──────┬──────┘ └─────────────┘ └───────▲──────┘
          │                                 │
          │ (task queue)                    │ (upload result)
          │                                 │
   ┌──────▼──────────────────────────────────┐
   │         Celery Workers (x4)             │
   │  (same image, entrypoint: celery)       │
   └─────────────────────────────────────────┘
```

### Component Inventory

| Component         | K8s Resource         | Replicas | Source                                    |
|-------------------|----------------------|----------|-------------------------------------------|
| Ingress           | Ingress + controller | 1        | ingress-nginx Helm chart                  |
| API               | Deployment           | 2        | Custom image                              |
| Celery Worker     | Deployment           | 4        | Same custom image, different command       |
| PostgreSQL        | CNPG Cluster CRD     | 2 (1+1)  | CloudNativePG operator                    |
| Redis             | StatefulSet          | 1        | Bitnami Redis Helm chart                  |
| MinIO             | StatefulSet          | 1        | MinIO Helm chart                          |
| Sealed Secrets    | Controller           | 1        | Bitnami Sealed Secrets Helm chart         |
| ArgoCD (optional) | Full stack           | 1        | ArgoCD Helm chart                         |

---

## Application Design

### API Endpoints

All endpoints are prefixed with `/api/v1/`. Versioning via URL path — explicit,
easy to route, cacheable. No need to implement version negotiation; just the
prefix for future-proofing and avoiding path collisions with any frontend routes.

```
POST   /api/v1/auth/register      — Create user account
POST   /api/v1/auth/login          — Returns access + refresh token pair
POST   /api/v1/auth/refresh        — Rotate refresh token, issue new access token

POST   /api/v1/jobs                — Submit a new job (returns 202 + job ID)
GET    /api/v1/jobs                — List authenticated user's jobs (paginated)
GET    /api/v1/jobs/{id}           — Job status; presigned MinIO URL when complete
GET    /api/v1/jobs/{id}/events    — SSE stream for real-time job status updates
POST   /api/v1/jobs/{id}/cancel    — Cancel a pending/processing job

GET    /healthz                    — K8s liveness probe (no auth, no prefix)
GET    /readyz                     — K8s readiness probe (checks Postgres + Redis)
```

### Status Codes

| Endpoint                  | Success           | Common Errors                        |
|---------------------------|-------------------|--------------------------------------|
| `POST /auth/register`     | `201 Created`     | `409 Conflict`, `422 Validation`     |
| `POST /auth/login`        | `200 OK`          | `401 Bad credentials`, `429`         |
| `POST /auth/refresh`      | `200 OK`          | `401 Revoked/expired`                |
| `POST /jobs`              | `202 Accepted`    | `401`, `429`                         |
| `GET  /jobs`              | `200 OK`          | `401`                                |
| `GET  /jobs/{id}`         | `200 OK`          | `401`, `403 Not owner`, `404`        |
| `GET  /jobs/{id}/events`  | `200 OK` (SSE)    | `401`, `403`, `404`                  |
| `POST /jobs/{id}/cancel`  | `200 OK`          | `401`, `403`, `404`, `409 Not cancellable` |
| `GET  /healthz`           | `200 OK`          | (none — always responds if alive)    |
| `GET  /readyz`            | `200 OK`          | `503 Service Unavailable`            |

### Error Response Envelope

All errors use a single standardized format (one Pydantic `ErrorResponse` model).
Override FastAPI's default `RequestValidationError` handler to match.

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed",
    "details": [
      {
        "field": "email",
        "message": "Must be a valid email address",
        "code": "invalid_format"
      }
    ]
  }
}
```

Machine-readable `code` for client logic, human-readable `message` for display,
optional `details` array for field-level validation errors.

### Success Response Envelope

```json
// Single resource
{"data": {"id": "...", "status": "pending", ...}}

// Collection (paginated)
{
  "data": [...],
  "meta": {"total": 42, "page": 1, "per_page": 20, "total_pages": 3}
}
```

Wrapping in `data` allows adding `meta`, `links`, or `warnings` later without
breaking clients.

### Pagination (GET /jobs)

Offset-based pagination. Jobs are user-scoped (typical user has < 100 jobs),
so offset performance is fine. Cursor-based would be overkill here.

Query params: `?page=1&per_page=20` (defaults: page=1, per_page=20, max=100).

### Rate Limiting

Using `slowapi` (wraps `limits` library) with Redis backend for distributed
counting across API replicas.

| Endpoint              | Limit        | Why                    |
|-----------------------|-------------|------------------------|
| `POST /auth/login`    | 5/min/IP    | Brute-force protection |
| `POST /auth/register` | 3/min/IP    | Abuse prevention       |
| `POST /jobs`          | 10/min/user | Resource protection    |
| GET endpoints         | 60/min/user | General throttle       |

Rate limit headers included in all responses:
`X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`.

### Data Models (Postgres, via Tortoise ORM)

**users**
- id (UUID, PK)
- email (unique)
- password_hash
- created_at

**refresh_tokens**
- id (UUID, PK)
- user_id (FK → users)
- token_hash (the refresh token is stored hashed, never plain)
- family_id (UUID — for refresh token rotation; revoking a family kills the chain)
- revoked (boolean)
- expires_at
- created_at

**jobs**
- id (UUID, PK)
- user_id (FK → users)
- status (enum: pending, processing, completed, failed, cancelled)
- celery_task_id (for correlation)
- minio_object_key (nullable, populated on completion)
- error_message (nullable, populated on failure)
- created_at
- updated_at

### Request/Response Flow

**Job submission:**
1. Client sends `POST /api/v1/jobs` with JWT access token
2. API validates JWT, creates job record in Postgres (status: pending)
3. API publishes Celery task with job ID
4. API returns `202 Accepted` with `{ "job_id": "..." }`

**Job processing (Celery worker):**
1. Worker picks up task, updates job status to `processing`
2. Worker does the heavy work (video generation, file processing, etc.)
3. Worker uploads result to MinIO under a deterministic key (e.g., `jobs/{job_id}/output.mp4`)
4. Worker updates job status to `completed`, stores `minio_object_key`
5. Worker publishes a notification to Redis pub/sub (for SSE)

**Job status / download:**
1. Client sends `GET /api/v1/jobs/{id}` with JWT
2. API verifies the job belongs to the authenticated user
3. If status is `completed`: generate presigned MinIO URL, return it in the response
4. If status is `pending`/`processing`: return current status

**SSE (real-time push):**
1. Client opens `GET /api/v1/jobs/{id}/events` (SSE connection)
2. API subscribes to Redis pub/sub channel for that job ID (e.g., `jobs:{id}:status`)
3. When worker publishes completion event, API pushes it down the SSE stream
4. Client receives event, can immediately call `GET /api/v1/jobs/{id}` for the presigned URL
5. If the client disconnects, no harm done — polling and/or email covers it

**Important: Workers never call the API.** The communication path is:
```
Celery Worker → Redis pub/sub → API (SSE handler) → Client browser
```
Workers publish status updates directly to a Redis pub/sub channel and move on.
The API's SSE handler subscribes to that channel and forwards events to the client.
This avoids coupling workers to the API (no need for workers to know the API address,
handle auth, or deal with API downtime). If no client is listening when the worker
publishes, the message is simply lost — which is fine, because the client falls back
to polling `GET /api/v1/jobs/{id}` anyway.

### Auth Flow

**Login:**
1. Client sends credentials to `POST /api/v1/auth/login`
2. Server validates, generates access token (15 min expiry) + refresh token (7 day expiry)
3. Refresh token is hashed and stored in Postgres with a `family_id`
4. Both tokens returned to client

**Refresh (with rotation):**
1. Client sends refresh token to `POST /api/v1/auth/refresh`
2. Server looks up the token hash in Postgres
3. If found, not revoked, and not expired: issue new access + refresh token pair
4. Old refresh token is marked revoked; new one gets the same `family_id`
5. If a revoked token is presented: revoke ALL tokens in that family (compromise detected), force re-login

---

## Docker

### Image Strategy

Single image for both API and worker. The entrypoint determines the role.

### Dockerfile

```dockerfile
# ---- Build stage ----
FROM python:3.14-slim AS builder

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    pip install uv && \
    uv sync --frozen --no-dev

COPY src/ ./src/

# ---- Runtime stage ----
FROM python:3.14-slim AS runtime

RUN groupadd --system app && useradd --system --gid app app

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src ./src/

ENV PATH="/app/.venv/bin:$PATH"

USER app

# Default entrypoint is the API; override for workers
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Worker override in K8s:
```yaml
command: ["celery"]
args: ["-A", "src.tasks", "worker", "--loglevel=info", "--concurrency=2"]
```

**Notes on the Dockerfile:**
- `RUN --mount=type=cache` caches the uv/pip download cache across builds
- Multi-stage keeps the final image free of build tooling
- Non-root user for runtime security
- Using `uv` for dependency management (fast, lockfile-based)

---

## Kubernetes / Helm

### Chart Structure

Single Helm chart, parameterized per component:

```
helm/video-demo/
├── Chart.yaml
├── templates/
│   ├── _helpers.tpl
│   ├── deployment.yaml          # Shared template, driven by values
│   ├── service.yaml
│   ├── ingress.yaml
│   ├── configmap.yaml           # Shared app config (non-secret)
│   ├── sealedsecret.yaml        # App secrets (DB URL, Redis URL, MinIO creds, JWT secret)
│   ├── hpa.yaml                 # Optional, for showing autoscaling
│   ├── migration-job.yaml       # PreSync hook for Aerich migrations
│   └── serviceaccount.yaml
├── values.yaml                  # Defaults
├── values-api.yaml              # API-specific overrides
└── values-worker.yaml           # Worker-specific overrides
```

### Migration Job (PreSync Hook)

```yaml
# templates/migration-job.yaml
{{- if .Values.migrations.enabled }}
apiVersion: batch/v1
kind: Job
metadata:
  name: {{ include "video-demo.fullname" . }}-migrate-{{ .Release.Revision }}
  annotations:
    argocd.argoproj.io/hook: PreSync
    argocd.argoproj.io/hook-delete-policy: BeforeHookCreation
spec:
  backoffLimit: 3
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: migrate
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          command: ["aerich"]
          args: ["upgrade"]
          envFrom:
            - configMapRef:
                name: {{ include "video-demo.fullname" . }}-config
            - secretRef:
                name: {{ include "video-demo.fullname" . }}-secrets
{{- end }}
```

Enabled only in the API values file (runs once per rollout, not per component):
```yaml
# values-api.yaml
migrations:
  enabled: true

# values-worker.yaml
migrations:
  enabled: false
```

### Deployment Template (shared)

The single `deployment.yaml` template handles both API and worker via values:

```yaml
# templates/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "video-demo.fullname" . }}-{{ .Values.component }}
spec:
  replicas: {{ .Values.replicas }}
  selector:
    matchLabels:
      app: {{ include "video-demo.name" . }}
      component: {{ .Values.component }}
  template:
    spec:
      containers:
        - name: {{ .Values.component }}
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          {{- if .Values.commandOverride }}
          command: {{ .Values.commandOverride.command | toJson }}
          args: {{ .Values.commandOverride.args | toJson }}
          {{- end }}
          envFrom:
            - configMapRef:
                name: {{ include "video-demo.fullname" . }}-config
            - secretRef:
                name: {{ include "video-demo.fullname" . }}-secrets
          {{- if .Values.health }}
          livenessProbe:
            httpGet:
              path: {{ .Values.health.liveness }}
              port: {{ .Values.health.port }}
          readinessProbe:
            httpGet:
              path: {{ .Values.health.readiness }}
              port: {{ .Values.health.port }}
          {{- end }}
```

### Per-Component Values

```yaml
# values-api.yaml
component: api
replicas: 2
migrations:
  enabled: true
health:
  liveness: /healthz
  readiness: /readyz
  port: 8000

# values-worker.yaml
component: worker
replicas: 4
migrations:
  enabled: false
commandOverride:
  command: ["celery"]
  args: ["-A", "src.tasks", "worker", "--loglevel=info", "--concurrency=2"]
# No health probe — use Celery's built-in inspect ping or a custom health check
```

### CNPG Credentials (Option B — Fully Sealed)

```yaml
# k8s/cnpg-cluster.yaml
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: demo-pg
spec:
  instances: 2
  superuserSecret:
    name: cnpg-superuser-creds    # Created by Sealed Secrets controller
  bootstrap:
    initdb:
      database: demo
      owner: app
      secret:
        name: cnpg-app-creds      # Created by Sealed Secrets controller
  storage:
    size: 1Gi
```

Ordering (ArgoCD sync waves or manual apply order):
1. SealedSecrets (controller decrypts → regular Secrets)
2. CNPG Cluster CRD (references the now-existing Secrets)

### Installation

```bash
# Infrastructure (operators + dependencies)
helm install cnpg cloudnative-pg/cloudnative-pg -n cnpg-system --create-namespace
helm install sealed-secrets bitnami/sealed-secrets -n kube-system
helm install redis bitnami/redis -n demo --set auth.existingSecret=redis-sealed-creds
helm install minio minio/minio -n demo --set existingSecret=minio-sealed-creds

# Apply CNPG Cluster CRD (referencing sealed credentials)
kubectl apply -f k8s/cnpg-cluster.yaml -n demo

# Application
helm install api helm/video-demo -n demo -f helm/video-demo/values-api.yaml
helm install worker helm/video-demo -n demo -f helm/video-demo/values-worker.yaml
```

### Sealed Secrets Workflow

```bash
# 1. Create a regular secret manifest (never commit this)
kubectl create secret generic app-secrets \
  --from-literal=DATABASE_URL=postgresql://app:pass@demo-pg-rw:5432/demo \
  --from-literal=REDIS_URL=redis://:pass@redis-master:6379/0 \
  --from-literal=MINIO_ACCESS_KEY=minioadmin \
  --from-literal=MINIO_SECRET_KEY=minioadmin \
  --from-literal=JWT_SECRET=your-secret-key \
  --dry-run=client -o yaml > /tmp/secret.yaml

# 2. Seal it (this output is safe to commit)
kubeseal --format yaml < /tmp/secret.yaml > k8s/sealedsecret.yaml

# 3. Clean up the plaintext
rm /tmp/secret.yaml

# 4. Apply
kubectl apply -f k8s/sealedsecret.yaml -n demo
```

---

## Optional: CI/CD with ArgoCD + Argo Events/Workflows

### What This Demonstrates

This is the "DevOps expertise showcase" layer. It turns the project from "I can build and deploy an app" into "I can build a self-contained platform with automated build and deploy pipelines — running entirely in a local Kind cluster."

### Components

| Component      | Role                                                        |
|----------------|-------------------------------------------------------------|
| ArgoCD         | GitOps-based continuous delivery — watches a repo, syncs K8s state |
| Argo Events    | Event source (webhook) that triggers Workflows on git push  |
| Argo Workflows | Runs the CI pipeline (build, test, push image, update manifests) |

### Flow

```
git push → Argo Events (webhook EventSource)
         → Argo Events Sensor (triggers Workflow)
         → Argo Workflow:
             Step 1: Clone repo
             Step 2: Run tests
             Step 3: Build image (kaniko — no Docker daemon needed)
             Step 4: Push to local registry (Kind has one)
             Step 5: Update image tag in Helm values (or kustomize overlay)
             Step 6: Commit updated manifests back to repo
         → ArgoCD detects manifest change
         → ArgoCD syncs to cluster (PreSync migration Job runs first)
         → New API + worker pods roll out
```

### Setup Order

1. Install ArgoCD (Helm chart, seal its admin secret)
2. Install Argo Workflows + Argo Events
3. Create EventSource (webhook listening on a NodePort or Ingress path)
4. Create Sensor (maps webhook event → WorkflowTemplate trigger)
5. Create WorkflowTemplate (the CI pipeline steps)
6. Create ArgoCD Application CRD pointing at your Helm chart in the repo
7. Configure a local git hook (`post-commit` or `post-push`) to curl the webhook

### Notes

- **Kaniko** for image builds avoids needing Docker-in-Docker or privileged containers
- A local Kind registry (`kind-registry:5000`) avoids needing Docker Hub credentials
- ArgoCD's admin password should be a SealedSecret
- Argo Workflows needs a ServiceAccount with permissions to push to the registry and commit to the repo
- This is genuinely impressive for a demo but adds significant setup time — build the core app first, add this layer only if you have time

---

## Project Structure

```
video-demo/
├── src/
│   ├── main.py              # FastAPI app, route definitions, Tortoise init
│   ├── auth.py              # JWT logic, login/refresh endpoints
│   ├── jobs.py              # Job endpoints (POST, GET, GET/{id})
│   ├── sse.py               # SSE endpoint, Redis pub/sub subscription
│   ├── tasks.py             # Celery task definitions
│   ├── models.py            # Tortoise ORM models (User, Job, RefreshToken)
│   ├── schemas.py           # Pydantic request/response schemas
│   ├── storage.py           # MinIO client, presigned URL generation
│   ├── config.py            # Settings from env vars
│   └── db.py                # Tortoise ORM config (DB URL, models list)
├── migrations/              # Aerich migration files
│   └── models/
├── tests/
├── Dockerfile
├── pyproject.toml
├── uv.lock
├── aerich.ini               # Aerich configuration
├── helm/
│   └── video-demo/
│       ├── Chart.yaml
│       ├── templates/
│       │   ├── _helpers.tpl
│       │   ├── deployment.yaml
│       │   ├── service.yaml
│       │   ├── ingress.yaml
│       │   ├── configmap.yaml
│       │   ├── sealedsecret.yaml
│       │   ├── migration-job.yaml
│       │   ├── hpa.yaml
│       │   └── serviceaccount.yaml
│       ├── values.yaml
│       ├── values-api.yaml
│       └── values-worker.yaml
├── k8s/
│   ├── cnpg-cluster.yaml
│   ├── sealedsecret.yaml
│   └── namespace.yaml
├── argo/                     # Optional CI/CD
│   ├── argocd-app.yaml
│   ├── event-source.yaml
│   ├── sensor.yaml
│   └── workflow-template.yaml
└── docker-compose.yaml       # For local dev without Kind
```

---

## Implementation Order

### Phase 1: Core Application
1. FastAPI skeleton with health endpoint
2. Tortoise ORM models + Aerich migrations setup
3. Auth (register, login, refresh with rotation)
4. Job creation endpoint + Celery task (stub — just sleep + write a dummy file)
5. MinIO integration (upload from worker, presigned URL from API)
6. SSE endpoint with Redis pub/sub
7. GET /jobs (list) and GET /jobs/{id} (status + download)

### Phase 2: Containerization
1. Dockerfile (multi-stage, cache mounts)
2. docker-compose.yaml for local dev (API, worker, Redis, Postgres, MinIO)
3. Verify full flow locally

### Phase 3: Kubernetes
1. Kind cluster setup script
2. Install operators (CNPG, Sealed Secrets)
3. Seal all credentials (CNPG, Redis, MinIO, app secrets)
4. Install dependencies (Redis, MinIO) with sealed credentials
5. Helm chart for API + worker (with migration Job)
6. Ingress configuration
7. End-to-end test on Kind

### Phase 4 (Optional): CI/CD
1. ArgoCD installation + Application CRD
2. Argo Workflows + Events
3. Kaniko build pipeline
4. Local registry + webhook integration
