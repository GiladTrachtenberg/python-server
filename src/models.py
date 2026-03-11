from __future__ import annotations

from enum import StrEnum
from uuid import uuid4

from tortoise import fields
from tortoise.models import Model


class JobStatus(StrEnum):
    """Job lifecycle states stored as strings in Postgres."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class User(Model):
    """Registered user account."""

    id = fields.UUIDField(primary_key=True, default=uuid4)
    email = fields.CharField(max_length=255, unique=True)
    password_hash = fields.CharField(max_length=255)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "users"

    def __str__(self) -> str:
        return f"User(id={self.id}, email={self.email})"


class RefreshToken(Model):
    """Hashed refresh token with family-based rotation tracking."""

    id = fields.UUIDField(primary_key=True, default=uuid4)
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="refresh_tokens", on_delete=fields.CASCADE
    )
    token_hash = fields.CharField(max_length=255, unique=True)
    family_id = fields.UUIDField(default=uuid4)
    revoked = fields.BooleanField(default=False)
    expires_at = fields.DatetimeField()
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "refresh_tokens"

    def __str__(self) -> str:
        return f"RefreshToken(id={self.id}, family={self.family_id})"


class Job(Model):
    """Async processing job linked to a user."""

    id = fields.UUIDField(primary_key=True, default=uuid4)
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="jobs", on_delete=fields.CASCADE
    )
    status = fields.CharEnumField(JobStatus, default=JobStatus.PENDING, max_length=20)
    celery_task_id = fields.CharField(max_length=255, null=True)
    minio_object_key = fields.CharField(max_length=512, null=True)
    error_message = fields.TextField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "jobs"

    def __str__(self) -> str:
        return f"Job(id={self.id}, status={self.status})"
