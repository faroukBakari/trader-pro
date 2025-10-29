"""Test fixtures for integration tests.

Creates full-stack application with ALL modules enabled.
"""

from collections.abc import AsyncGenerator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient

from trading_api.shared import FastWSAdapter


@pytest.fixture
def apps() -> tuple[FastAPI, FastWSAdapter]:
    """Full application with all modules enabled."""
    from trading_api.app_factory import create_app

    return create_app(enabled_modules=None)  # None = all modules


@pytest.fixture
def app(apps: tuple[FastAPI, FastWSAdapter]) -> FastAPI:
    """FastAPI application instance."""
    api_app, _ = apps
    return api_app


@pytest.fixture
def ws_app(apps: tuple[FastAPI, FastWSAdapter]) -> FastWSAdapter:
    """FastWSAdapter application instance."""
    _, ws_app = apps
    return ws_app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Sync test client for WebSocket tests."""
    return TestClient(app)


@pytest.fixture
async def async_client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Async test client for API tests."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
