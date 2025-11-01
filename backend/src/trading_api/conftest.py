"""Root test fixtures for all trading_api test suites.

This conftest provides common fixtures that are shared across:
- Shared infrastructure tests (health, versioning)
- Module-specific tests (broker, datafeed)
- Integration tests

Fixtures defined here are automatically available to all test files
in trading_api and its subdirectories.
"""

from typing import AsyncGenerator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient

from trading_api.shared import FastWSAdapter


@pytest.fixture(scope="session")
def app(apps: tuple[FastAPI, list[FastWSAdapter]]) -> FastAPI:
    """FastAPI application instance (shared across session)."""
    api_app, _ = apps
    return api_app


@pytest.fixture(scope="session")
def ws_app(apps: tuple[FastAPI, list[FastWSAdapter]]) -> FastWSAdapter | None:
    """FastWSAdapter application instance (shared across session)."""
    _, ws_apps = apps
    return ws_apps[0] if ws_apps else None


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Sync test client for WebSocket tests."""
    return TestClient(app)


@pytest.fixture
async def async_client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Async test client for API tests."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
