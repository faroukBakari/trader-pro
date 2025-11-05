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

from trading_api.app_factory import ModularApp
from trading_api.shared import FastWSAdapter


@pytest.fixture(scope="session")
def app(apps: ModularApp) -> FastAPI:
    """FastAPI application instance (shared across session).

    ModularApp extends FastAPI, so we can use it directly.
    """
    return apps  # ModularApp IS a FastAPI


@pytest.fixture(scope="session")
def ws_apps(apps: ModularApp) -> list[FastWSAdapter]:
    """FastWSAdapter application instances (shared across session).

    Extracts WebSocket apps from all modules.
    """
    return [
        ws_app for module_app in apps.modules_apps for ws_app in module_app.ws_versions
    ]


@pytest.fixture(scope="session")
def ws_app(ws_apps: list[FastWSAdapter]) -> FastWSAdapter | None:
    """First FastWSAdapter application instance (shared across session)."""
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
