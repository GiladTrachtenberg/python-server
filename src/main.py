from __future__ import annotations

from fastapi import APIRouter, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.config import Settings, get_settings
from src.schemas import ErrorBody, ErrorDetail, ErrorResponse, HealthResponse


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = get_settings()

    app = FastAPI(title=settings.app_name, debug=settings.debug)

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
    async def readyz() -> HealthResponse:
        return HealthResponse(status="ok")


def _register_api_router(app: FastAPI, settings: Settings) -> None:
    router = APIRouter(prefix=settings.api_v1_prefix)
    app.include_router(router)


app: FastAPI = create_app()
