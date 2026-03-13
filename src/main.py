from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import APIRouter, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from tortoise import Tortoise, connections

from src.config import Settings, get_settings
from src.db import get_tortoise_config
from src.rate_limit import init_limiter, rate_limit_exceeded_handler
from src.schemas import ErrorBody, ErrorDetail, ErrorResponse, HealthResponse

logger: logging.Logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None]:
    settings: Settings = app.state.settings
    config = get_tortoise_config(settings.database_url)
    await Tortoise.init(config=config, _enable_global_fallback=True)

    try:
        from src.storage import ensure_bucket, get_minio_client

        client = get_minio_client(settings)
        ensure_bucket(client, settings.minio_bucket)
    except Exception as exc:
        logger.warning("MinIO bucket init failed (worker will retry): %s", exc)

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

    rate_limiter = init_limiter(settings)
    app.state.limiter = rate_limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)  # type: ignore[arg-type]
    app.add_middleware(SlowAPIMiddleware)

    if settings.debug:
        from fastapi.middleware.cors import CORSMiddleware

        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:5173"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

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

        try:
            import redis.asyncio as aioredis

            settings: Settings = app.state.settings
            r = aioredis.from_url(settings.redis_url)
            await r.ping()
            await r.aclose()
        except Exception as exc:
            logger.warning("readyz Redis check failed: %s", exc)
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
    from src.jobs import jobs_router
    from src.sse import sse_router

    router.include_router(auth_router)
    router.include_router(jobs_router)
    router.include_router(sse_router)
    app.include_router(router)
