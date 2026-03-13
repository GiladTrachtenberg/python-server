from __future__ import annotations

from datetime import timedelta
from io import BytesIO
from typing import TYPE_CHECKING

from minio import Minio

if TYPE_CHECKING:
    from src.config import WorkerSettings


def get_minio_client(settings: WorkerSettings) -> Minio:
    """Create a MinIO client from app settings."""
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


def ensure_bucket(client: Minio, bucket: str) -> None:
    """Create the bucket if it doesn't already exist."""
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)


def upload_bytes(client: Minio, bucket: str, key: str, data: bytes) -> None:
    """Upload raw bytes to MinIO."""
    client.put_object(bucket, key, BytesIO(data), length=len(data))


def upload_stream(
    client: Minio,
    bucket: str,
    key: str,
    stream: BytesIO,
    length: int,
    content_type: str = "application/octet-stream",
) -> None:
    """Upload a stream to MinIO with known length."""
    client.put_object(
        bucket,
        key,
        stream,
        length=length,
        content_type=content_type,
    )


def presigned_url(
    client: Minio,
    bucket: str,
    key: str,
    expires: timedelta = timedelta(hours=1),
) -> str:
    """Generate a presigned GET URL for an object."""
    return client.presigned_get_object(bucket, key, expires=expires)
