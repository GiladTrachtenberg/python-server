from __future__ import annotations

import atexit
import os
from typing import TYPE_CHECKING

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


@pytest.fixture(scope="session")
def database_url() -> str:
    """Postgres URL backed by testcontainers (session-scoped, one container)."""
    return _start_postgres()


@pytest.fixture
def settings(database_url: str) -> Settings:
    return Settings(debug=True, database_url=database_url)


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
async def db_client(database_url: str) -> AsyncGenerator[AsyncClient]:
    """AsyncClient backed by a real Postgres — app lifespan owns the connection."""
    settings = Settings(debug=True, database_url=database_url)
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


def pytest_sessionfinish() -> None:
    _stop_postgres()
