from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient

pytestmark = pytest.mark.usefixtures("db")

AUTH = "/api/v1/auth"


async def _register(client: AsyncClient, email: str = "u@test.com", password: str = "strongpass1") -> dict:
    resp = await client.post(f"{AUTH}/register", json={"email": email, "password": password})
    return {"response": resp, "data": resp.json()}


async def _login(client: AsyncClient, email: str = "u@test.com", password: str = "strongpass1") -> dict:
    resp = await client.post(f"{AUTH}/login", json={"email": email, "password": password})
    return {"response": resp, "data": resp.json()}


async def _refresh(client: AsyncClient, refresh_token: str) -> dict:
    resp = await client.post(f"{AUTH}/refresh", json={"refresh_token": refresh_token})
    return {"response": resp, "data": resp.json()}


class TestRegister:
    async def test_success(self, db_client: AsyncClient) -> None:
        result = await _register(db_client)
        assert result["response"].status_code == 201
        data = result["data"]["data"]
        UUID(data["id"])
        assert data["email"] == "u@test.com"
        assert "created_at" in data

    async def test_duplicate_email(self, db_client: AsyncClient) -> None:
        await _register(db_client)
        result = await _register(db_client)
        assert result["response"].status_code == 409
        assert result["data"]["error"]["code"] == "conflict"

    async def test_weak_password(self, db_client: AsyncClient) -> None:
        result = await _register(db_client, password="short")
        assert result["response"].status_code == 422

    async def test_invalid_email(self, db_client: AsyncClient) -> None:
        result = await _register(db_client, email="not-an-email")
        assert result["response"].status_code == 422


class TestLogin:
    async def test_success(self, db_client: AsyncClient) -> None:
        await _register(db_client)
        result = await _login(db_client)
        assert result["response"].status_code == 200
        data = result["data"]["data"]
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert isinstance(data["expires_in"], int)

    async def test_wrong_password(self, db_client: AsyncClient) -> None:
        await _register(db_client)
        result = await _login(db_client, password="wrongpass1")
        assert result["response"].status_code == 401
        assert result["data"]["error"]["code"] == "invalid_credentials"

    async def test_nonexistent_user(self, db_client: AsyncClient) -> None:
        result = await _login(db_client, email="nobody@test.com")
        assert result["response"].status_code == 401
        assert result["data"]["error"]["code"] == "invalid_credentials"


class TestRefresh:
    async def test_success(self, db_client: AsyncClient) -> None:
        await _register(db_client)
        login = await _login(db_client)
        refresh_token = login["data"]["data"]["refresh_token"]

        result = await _refresh(db_client, refresh_token)
        assert result["response"].status_code == 200
        data = result["data"]["data"]
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["refresh_token"] != refresh_token

    async def test_old_token_rejected_after_rotation(self, db_client: AsyncClient) -> None:
        await _register(db_client)
        login = await _login(db_client)
        old_token = login["data"]["data"]["refresh_token"]

        await _refresh(db_client, old_token)

        result = await _refresh(db_client, old_token)
        assert result["response"].status_code == 401

    async def test_reuse_revokes_family(self, db_client: AsyncClient) -> None:
        await _register(db_client)
        login = await _login(db_client)
        old_token = login["data"]["data"]["refresh_token"]

        rotated = await _refresh(db_client, old_token)
        new_token = rotated["data"]["data"]["refresh_token"]

        await _refresh(db_client, old_token)

        result = await _refresh(db_client, new_token)
        assert result["response"].status_code == 401

    async def test_invalid_token(self, db_client: AsyncClient) -> None:
        result = await _refresh(db_client, "garbage-token")
        assert result["response"].status_code == 401

    async def test_access_token_works_on_protected_route(self, db_client: AsyncClient) -> None:
        await _register(db_client)
        login = await _login(db_client)
        access_token = login["data"]["data"]["access_token"]

        resp = await db_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["email"] == "u@test.com"

    async def test_missing_auth_header(self, db_client: AsyncClient) -> None:
        resp = await db_client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    async def test_expired_access_token(self, db_client: AsyncClient) -> None:
        from src.auth import create_access_token
        from src.config import Settings

        settings = Settings(debug=True, access_token_expire_minutes=-1)
        token = create_access_token("fake-id", settings)

        resp = await db_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401
