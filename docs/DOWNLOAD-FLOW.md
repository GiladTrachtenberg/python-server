# Download Flow

End-to-end lifecycle of a job file from generation to browser download.

## Architecture

The API is a **control plane** (auth, job state, URL signing) while MinIO is the
**data plane** (file storage and delivery). The API never touches file bytes.

```
┌─────────┐     POST /jobs      ┌─────────┐    task.delay()    ┌──────────┐
│Frontend │ ──────────────────► │   API   │ ─────────────────► │  Celery  │
│(React)  │                     │(FastAPI)│                     │ (Worker) │
└────┬────┘                     └─────────┘                     └────┬─────┘
     │                                                               │
     │  EventSource(/events?token=)                                  │
     │ ◄─── SSE: connected ────                                     │
     │ ◄─── SSE: processing ──── Redis pub/sub ◄────────────────────┤
     │                                                               │
     │                                          generate file ───────┤
     │                                          upload to MinIO ─────┤
     │                                          save object key ─────┤
     │                                                               │
     │ ◄─── SSE: completed ───── Redis pub/sub ◄────────────────────┘
     │
     │  GET /jobs/{id}
     │ ─────────────────────────► API generates presigned URL
     │ ◄──── {download_url: "https://minio:9000/...?X-Amz-Signature=..."} ──
     │
     │  Click "Download"
     │ ─────────────────────────────────────────────────► MinIO (direct)
     │ ◄──────────────── file bytes (50MB) ◄──────────── MinIO (direct)
```

## 1. Worker Generates and Uploads the File

**File**: `src/tasks.py` — `_process()`

When a job is picked up by Celery:

1. The worker generates 5-50MB of random binary data in 1MB chunks via
   `os.urandom`. Chunked generation avoids holding the entire file in memory.
2. The file is uploaded directly to MinIO under `jobs/{job_id}/output.bin`.
3. The worker saves the `minio_object_key` to the database.
4. A `"completed"` status event is published to Redis pub/sub.

The API server never touches file bytes — only the worker and MinIO handle them.

## 2. API Generates a Presigned URL

**File**: `src/jobs.py:80-87`, `src/storage.py:48-55`

When the frontend requests `GET /api/v1/jobs/{id}`, the API checks:

```
job.status == COMPLETED and job.minio_object_key is set
```

If true, it calls `presigned_get_object()` on the MinIO client. This is a pure
computation (HMAC-SHA256 signing) — no network call to MinIO. The result is a
time-limited URL (1 hour default) containing the signature, expiration, and
access credentials as query parameters.

The presigned URL is returned in the response envelope:

```json
{
  "data": {
    "id": "...",
    "status": "completed",
    "download_url": "http://minio:9000/video-demo/jobs/.../output.bin?X-Amz-Algorithm=..."
  }
}
```

## 3. SSE Notifies the Frontend

**Files**: `src/sse.py`, `web/src/JobDetailPage.tsx`

Real-time notification uses Redis pub/sub piped through Server-Sent Events:

1. On mount, `JobDetailPage` fetches the job via `GET /jobs/{id}` and opens an
   `EventSource` to `/api/v1/jobs/{id}/events?token=...` (query-param auth
   because `EventSource` cannot set custom headers — see D19).
2. The SSE stream sends `event: status` messages as the worker progresses.
3. When `"completed"` arrives:
   - The `EventSource` is closed (terminal state).
   - The component **re-fetches** the job via `GET /jobs/{id}`.
4. The re-fetch now returns `download_url` because the job is completed.
5. React renders: `<a href={downloadUrl} target="_blank">Download File</a>`.

The SSE event itself does not contain the download URL — only the status. The
URL is generated on-demand when the client re-fetches. This is intentional:
presigned URLs are time-limited, so generating them eagerly in the worker would
waste expiry time.

## 4. Browser Downloads from MinIO Directly

When the user clicks "Download":

- The browser opens the presigned MinIO URL in a new tab.
- MinIO validates the signature and expiration.
- MinIO serves the file with `Content-Type: application/octet-stream`.
- The browser triggers a native file download dialog.

The download goes directly from the browser to MinIO. The API is completely out
of the data path. For a 50MB file, this means zero load on the API server.

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Presigned URLs (D4) | Avoids streaming through the API — no memory pressure, no tied-up workers |
| Lazy URL generation | URLs are minted when requested, not when the job completes — maximizes expiry window |
| 1-hour expiry | Balances usability (user has time to click) and security (limits leaked URL exposure) |
| SSE for notification | Push-based — no polling. Client learns about completion instantly |
| Re-fetch after SSE | Separates the notification channel (SSE) from the data channel (REST API) |

## Related Files

| File | Role |
|------|------|
| `src/tasks.py` | File generation, MinIO upload, Redis pub/sub publish |
| `src/storage.py` | MinIO client, `presigned_get_object` wrapper |
| `src/jobs.py` | `GET /jobs/{id}` — generates presigned URL for completed jobs |
| `src/sse.py` | SSE endpoint — subscribes to Redis, streams events to client |
| `web/src/JobDetailPage.tsx` | EventSource listener, re-fetch on completion, download link |
| `web/src/api.ts` | `getJob()`, `sseUrl()` — typed API client functions |
