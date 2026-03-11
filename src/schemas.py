from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    """Single field-level validation error."""

    field: str
    message: str
    code: str


class ErrorBody(BaseModel):
    """Structured error payload."""

    code: str
    message: str
    details: list[ErrorDetail] | None = None


class ErrorResponse(BaseModel):
    """Standardized error envelope — used by all error responses."""

    error: ErrorBody


class HealthResponse(BaseModel):
    """Response for /healthz and /readyz."""

    status: Literal["ok", "degraded", "unavailable"]
