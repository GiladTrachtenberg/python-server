from __future__ import annotations

import asyncio
import json
import logging
import os
import random
from io import BytesIO

import redis.asyncio as aioredis
from celery import Celery
from tortoise import Tortoise, connections

from src.config import WorkerSettings
from src.db import get_tortoise_config
from src.models import JobStatus
from src.storage import ensure_bucket, get_minio_client, upload_stream

logger: logging.Logger = logging.getLogger(__name__)

_CHUNK_SIZE: int = 1_048_576

celery_app: Celery = Celery(
    "video-demo",
    broker=os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/1"),
)


def _generate_file(size: int) -> BytesIO:
    """Generate a BytesIO of random bytes, written in 1MB chunks."""
    buf = BytesIO()
    remaining = size
    while remaining > 0:
        chunk = min(_CHUNK_SIZE, remaining)
        buf.write(os.urandom(chunk))
        remaining -= chunk
    buf.seek(0)
    return buf


async def _publish(redis_url: str, job_id: str, status: str) -> None:
    """Publish a job status event to Redis pub/sub."""
    r = aioredis.from_url(redis_url)
    try:
        payload = json.dumps({"job_id": job_id, "status": status})
        await r.publish(f"jobs:{job_id}:status", payload)
    finally:
        await r.aclose()


async def _process(job_id: str, settings: WorkerSettings) -> None:
    """Async core of the process_job task."""
    from src.models import Job

    config = get_tortoise_config(settings.database_url)
    await Tortoise.init(config=config)
    try:
        job = await Job.get(id=job_id)

        job.status = JobStatus.PROCESSING
        await job.save(update_fields=["status", "updated_at"])
        await _publish(settings.redis_url, job_id, "processing")

        await asyncio.sleep(random.uniform(2, 4))

        file_size = random.randint(5_000_000, 50_000_000)
        data = _generate_file(file_size)

        minio = get_minio_client(settings)
        ensure_bucket(minio, settings.minio_bucket)
        key = f"jobs/{job_id}/output.bin"
        upload_stream(
            minio,
            settings.minio_bucket,
            key,
            data,
            file_size,
        )

        job.status = JobStatus.COMPLETED
        job.minio_object_key = key
        await job.save(update_fields=["status", "minio_object_key", "updated_at"])
        await _publish(settings.redis_url, job_id, "completed")

    except Exception:
        logger.exception("Job %s failed", job_id)
        try:
            job = await Job.get(id=job_id)
            job.status = JobStatus.FAILED
            job.error_message = "Processing failed"
            await job.save(update_fields=["status", "error_message", "updated_at"])
            await _publish(settings.redis_url, job_id, "failed")
        except Exception:
            logger.exception("Failed to mark job %s as failed", job_id)
    finally:
        await connections.close_all()


@celery_app.task(name="process_job")
def process_job(job_id: str) -> None:
    """Celery entry point — bridges sync Celery with async internals."""
    from src.config import get_worker_settings

    settings = get_worker_settings()
    asyncio.run(_process(job_id, settings))
