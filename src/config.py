from __future__ import annotations

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings

_LOCAL_DEV_DB_URL: str = "postgres://postgres:postgres@localhost:5432/video_demo"


_LOCAL_DEV_JWT_SECRET: str = "dev-secret-do-not-use-in-production-32b"


class WorkerSettings(BaseSettings):
    app_name: str = "video-demo"
    debug: bool = False
    database_url: str = _LOCAL_DEV_DB_URL
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "video-demo"
    minio_secure: bool = False

    model_config = {"env_prefix": "", "case_sensitive": False}

    @model_validator(mode="after")
    def _reject_defaults_in_production(self) -> WorkerSettings:
        if not self.debug:
            if self.database_url == _LOCAL_DEV_DB_URL:
                msg = "DATABASE_URL must be set explicitly in production (debug=False)"
                raise ValueError(msg)
        return self


class Settings(WorkerSettings):
    api_v1_prefix: str = "/api/v1"
    jwt_secret_key: str = _LOCAL_DEV_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 1
    rate_limit_enabled: bool = True

    @model_validator(mode="after")
    def _reject_jwt_default_in_production(self) -> Settings:
        if not self.debug:
            if self.jwt_secret_key == _LOCAL_DEV_JWT_SECRET:
                msg = (
                    "JWT_SECRET_KEY must be set explicitly in production (debug=False)"
                )
                raise ValueError(msg)
        return self


@lru_cache
def get_worker_settings() -> WorkerSettings:
    return WorkerSettings()


@lru_cache
def get_settings() -> Settings:
    return Settings()
