from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from httpx import AsyncClient


async def test_healthz_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readyz_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_healthz_method_not_allowed(client: AsyncClient) -> None:
    response = await client.post("/healthz")

    assert response.status_code == 405


async def test_nonexistent_route_returns_404(client: AsyncClient) -> None:
    response = await client.get("/nonexistent")

    assert response.status_code == 404
