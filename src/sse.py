from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse, StreamingResponse

from src.auth import CurrentUserSSE, SettingsDep
from src.models import Job, JobStatus
from src.rate_limit import GET_LIMIT, get_user_or_ip, limiter
from src.schemas import ErrorBody, ErrorResponse

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

logger: logging.Logger = logging.getLogger(__name__)

sse_router = APIRouter(prefix="/jobs", tags=["sse"])

_TERMINAL_STATUSES: frozenset[str] = frozenset(
    {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED},
)


def _error(code: str, message: str, status_code: int) -> JSONResponse:
    body = ErrorResponse(error=ErrorBody(code=code, message=message))
    return JSONResponse(status_code=status_code, content=body.model_dump())


def _sse_event(data: str, event: str | None = None, id: str | None = None) -> str:
    """Format a single SSE event."""
    lines: list[str] = []
    if id is not None:
        lines.append(f"id: {id}")
    if event is not None:
        lines.append(f"event: {event}")
    lines.append(f"data: {data}")
    lines.append("")
    lines.append("")
    return "\n".join(lines)


async def _stream_events(
    redis_url: str,
    job_id: str,
    last_event_id: str | None,
) -> AsyncGenerator[str]:
    """Subscribe to Redis pub/sub and yield SSE-formatted events."""
    if last_event_id is not None:
        job = await Job.get_or_none(id=job_id)
        if job and job.status in _TERMINAL_STATUSES:
            payload = json.dumps({"job_id": job_id, "status": job.status})
            yield _sse_event(payload, event="status", id=job.status)
            return

    yield _sse_event(json.dumps({"job_id": job_id}), event="connected")

    r = aioredis.from_url(redis_url)
    pubsub = r.pubsub()
    try:
        await pubsub.subscribe(f"jobs:{job_id}:status")
        while True:
            msg = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=30.0,
            )
            if msg is not None and msg["type"] == "message":
                data = msg["data"]
                if isinstance(data, bytes):
                    data = data.decode()
                parsed = json.loads(data)
                event_status = parsed.get("status", "unknown")
                yield _sse_event(data, event="status", id=event_status)

                if event_status in _TERMINAL_STATUSES:
                    break
            else:
                yield _sse_event("", event="ping")

    except asyncio.CancelledError:
        logger.debug("SSE client disconnected for job %s", job_id)
    finally:
        await pubsub.unsubscribe(f"jobs:{job_id}:status")
        await pubsub.aclose()
        await r.aclose()


@sse_router.get("/{job_id}/events", response_model=None)
@limiter.limit(GET_LIMIT, key_func=get_user_or_ip)  # type: ignore[union-attr]
async def job_events(
    job_id: UUID,
    user: CurrentUserSSE,
    settings: SettingsDep,
    request: Request,
) -> StreamingResponse | JSONResponse:
    job = await Job.get_or_none(id=job_id)
    if job is None:
        return _error("not_found", "Job not found", status.HTTP_404_NOT_FOUND)
    if job.user_id != user.id:  # type: ignore[attr-defined]
        return _error("forbidden", "Not your job", status.HTTP_403_FORBIDDEN)

    last_event_id = request.headers.get("Last-Event-ID")

    return StreamingResponse(
        _stream_events(settings.redis_url, str(job_id), last_event_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
