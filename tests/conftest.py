from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient

from src.config import Settings
from src.main import create_app

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@pytest.fixture
def settings() -> Settings:
    return Settings(debug=True)


@pytest.fixture
async def client(settings: Settings) -> AsyncGenerator[AsyncClient]:
    app = create_app(settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
