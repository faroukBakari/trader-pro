"""Shared test fixtures for all test suites.

This module provides a generic test app factory that can be used by:
- Shared infrastructure tests (health, versioning)
- Module-specific tests (broker, datafeed)
- Integration tests

Each test suite can create an app with only the modules it needs for isolation.
"""

from typing import AsyncGenerator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient

from trading_api.shared import FastWSAdapter


def create_test_app(
    enabled_modules: list[str] | None = None,
) -> tuple[FastAPI, list[FastWSAdapter]]:
    """Create a test application with specified modules.

    Args:
        enabled_modules: List of module names to enable (e.g., ["broker", "datafeed"])
                        If None, all modules are enabled.

    Returns:
        tuple: (FastAPI application, list of FastWSAdapter applications)

    Example:
        # Test with all modules
        api_app, ws_apps = create_test_app()

        # Test with only broker module
        api_app, ws_apps = create_test_app(enabled_modules=["broker"])

        # Test with only shared infrastructure (no modules)
        api_app, ws_apps = create_test_app(enabled_modules=[])
    """
    from trading_api.app_factory import create_app

    return create_app(enabled_modules=enabled_modules)


@pytest.fixture
def apps() -> tuple[FastAPI, list[FastWSAdapter]]:
    """Full application (API + WS) with all modules enabled."""
    return create_test_app(enabled_modules=None)


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
