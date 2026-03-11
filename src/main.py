from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import APIRouter, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from tortoise import Tortoise, connections

from src.config import Settings, get_settings
from src.db import get_tortoise_config
from src.schemas import ErrorBody, ErrorDetail, ErrorResponse, HealthResponse

logger: logging.Logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None]:
    settings: Settings = app.state.settings
    config = get_tortoise_config(settings.database_url)
    await Tortoise.init(config=config)
    try:
        yield
    finally:
        await connections.close_all()


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        lifespan=_lifespan,
    )
    app.state.settings = settings

    _register_error_handlers(app)
    _register_health_routes(app)
    _register_api_router(app, settings)

    return app


def _register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = [
            ErrorDetail(
                field=".".join(str(loc) for loc in err["loc"]),
                message=err["msg"],
                code=err["type"],
            )
            for err in exc.errors()
        ]
        body = ErrorResponse(
            error=ErrorBody(
                code="validation_error",
                message="Request validation failed",
                details=details,
            )
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=body.model_dump(),
        )


def _register_health_routes(app: FastAPI) -> None:
    @app.get("/healthz", response_model=HealthResponse)
    async def healthz() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.get("/readyz", response_model=HealthResponse)
    async def readyz() -> JSONResponse:
        try:
            conn = connections.get("default")
            await conn.execute_query("SELECT 1")
        except Exception as exc:
            logger.warning("readyz DB check failed: %s", exc)
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content=HealthResponse(status="unavailable").model_dump(),
            )
        return JSONResponse(
            content=HealthResponse(status="ok").model_dump(),
        )


def _register_api_router(app: FastAPI, settings: Settings) -> None:
    router = APIRouter(prefix=settings.api_v1_prefix)

    from src.auth import auth_router

    router.include_router(auth_router)
    app.include_router(router)


