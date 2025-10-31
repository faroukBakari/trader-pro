"""Test fixtures for broker module tests.

Creates test app with only broker module enabled for isolation.
"""

from typing import AsyncGenerator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient

from trading_api.shared import FastWSAdapter


@pytest.fixture
def apps() -> tuple[FastAPI, list[FastWSAdapter]]:
    """Application with only broker module enabled."""
    from trading_api.app_factory import create_app

    return create_app(enabled_modules=["broker"])


@pytest.fixture
def app(apps: tuple[FastAPI, list[FastWSAdapter]]) -> FastAPI:
    """FastAPI application instance."""
    api_app, _ = apps
    return api_app


@pytest.fixture
def ws_app(apps: tuple[FastAPI, list[FastWSAdapter]]) -> FastWSAdapter | None:
    """FastWSAdapter application instance (first module's ws_app)."""
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
