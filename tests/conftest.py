from __future__ import annotations

import atexit
import os
from typing import TYPE_CHECKING, Any

os.environ.setdefault("TESTCONTAINERS_RYUK_PORT", "8082")

import pytest
from httpx import ASGITransport, AsyncClient
from tortoise import Tortoise, connections

from src.config import Settings
from src.db import get_tortoise_config
from src.main import create_app

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


_pg_container: object | None = None
_pg_url: str = ""


def _start_postgres() -> str:
    """Start a Postgres container and return the connection URL."""
    global _pg_container, _pg_url
    if _pg_container is not None:
        return _pg_url

    from testcontainers.postgres import PostgresContainer

    container = PostgresContainer("postgres:16-alpine")
    container.start()
    host = container.get_container_host_ip()
    port = container.get_exposed_port(5432)
    _pg_url = f"postgres://test:test@{host}:{port}/test"
    _pg_container = container
    return _pg_url


def _stop_postgres() -> None:
    global _pg_container, _pg_url
    if _pg_container is not None:
        from testcontainers.postgres import PostgresContainer

        assert isinstance(_pg_container, PostgresContainer)
        _pg_container.stop()
        _pg_container = None
        _pg_url = ""


atexit.register(_stop_postgres)


_redis_container: object | None = None
_redis_url: str = ""


def _start_redis() -> str:
    """Start a Redis container and return the connection URL."""
    global _redis_container, _redis_url
    if _redis_container is not None:
        return _redis_url

    from testcontainers.core.container import DockerContainer

    container = DockerContainer("redis:7-alpine")
    container.with_exposed_ports(6379)
    container.start()
    host = container.get_container_host_ip()
    port = container.get_exposed_port(6379)
    _redis_url = f"redis://{host}:{port}/0"
    _redis_container = container
    return _redis_url


def _stop_redis() -> None:
    global _redis_container, _redis_url
    if _redis_container is not None:
        from testcontainers.core.container import DockerContainer

        assert isinstance(_redis_container, DockerContainer)
        _redis_container.stop()
        _redis_container = None
        _redis_url = ""


atexit.register(_stop_redis)


_minio_container: object | None = None
_minio_config: dict[str, Any] = {}


def _start_minio() -> dict[str, Any]:
    """Start a MinIO container and return connection config."""
    global _minio_container, _minio_config
    if _minio_container is not None:
        return _minio_config

    from testcontainers.minio import MinioContainer

    container = MinioContainer("minio/minio:latest")
    container.start()
    _minio_config = container.get_config()
    _minio_container = container
    return _minio_config


def _stop_minio() -> None:
    global _minio_container, _minio_config
    if _minio_container is not None:
        from testcontainers.minio import MinioContainer

        assert isinstance(_minio_container, MinioContainer)
        _minio_container.stop()
        _minio_container = None
        _minio_config = {}


atexit.register(_stop_minio)


@pytest.fixture(scope="session")
def database_url() -> str:
    """Postgres URL backed by testcontainers (session-scoped, one container)."""
    return _start_postgres()


@pytest.fixture(scope="session")
def redis_url() -> str:
    """Redis URL backed by testcontainers (session-scoped)."""
    return _start_redis()


@pytest.fixture(scope="session")
def minio_config() -> dict[str, Any]:
    """MinIO config backed by testcontainers (session-scoped)."""
    return _start_minio()


@pytest.fixture
def settings(
    database_url: str,
    redis_url: str,
    minio_config: dict[str, Any],
) -> Settings:
    return Settings(
        debug=True,
        database_url=database_url,
        redis_url=redis_url,
        celery_broker_url=redis_url,
        minio_endpoint=minio_config["endpoint"],
        minio_access_key=minio_config["access_key"],
        minio_secret_key=minio_config["secret_key"],
        minio_bucket="test-bucket",
        rate_limit_enabled=False,
    )


@pytest.fixture
async def client(settings: Settings) -> AsyncGenerator[AsyncClient]:
    app = create_app(settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def db(database_url: str) -> AsyncGenerator[None]:
    """Init Tortoise, generate schemas once, truncate between tests."""
    config = get_tortoise_config(database_url)
    await Tortoise.init(config=config)
    await Tortoise.generate_schemas(safe=True)
    try:
        yield
    finally:
        conn = connections.get("default")
        for table in ("jobs", "refresh_tokens", "users"):
            await conn.execute_query(f"TRUNCATE {table} CASCADE")
        await connections.close_all()


@pytest.fixture
async def db_client(
    database_url: str,
    redis_url: str,
    minio_config: dict[str, Any],
) -> AsyncGenerator[AsyncClient]:
    """AsyncClient backed by real Postgres + Redis + MinIO."""
    settings = Settings(
        debug=True,
        database_url=database_url,
        redis_url=redis_url,
        celery_broker_url=redis_url,
        minio_endpoint=minio_config["endpoint"],
        minio_access_key=minio_config["access_key"],
        minio_secret_key=minio_config["secret_key"],
        minio_bucket="test-bucket",
        rate_limit_enabled=False,
    )
    config = get_tortoise_config(database_url)
    await Tortoise.init(config=config)
    await Tortoise.generate_schemas(safe=True)
    await connections.close_all()

    app = create_app(settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
        conn = connections.get("default")
        for table in ("jobs", "refresh_tokens", "users"):
            await conn.execute_query(f"TRUNCATE {table} CASCADE")


AUTH = "/api/v1/auth"

_login_counter: int = 0


async def register_and_login(client: AsyncClient) -> dict[str, str]:
    """Register a unique test user, log in, return auth headers."""
    global _login_counter
    _login_counter += 1
    email = f"jobs{_login_counter}@test.com"
    await client.post(
        f"{AUTH}/register",
        json={"email": email, "password": "strongpass1"},
    )
    resp = await client.post(
        f"{AUTH}/login",
        json={"email": email, "password": "strongpass1"},
    )
    token = resp.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def pytest_sessionfinish() -> None:
    _stop_postgres()
    _stop_redis()
    _stop_minio()
