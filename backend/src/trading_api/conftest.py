"""Root test fixtures for all trading_api test suites.

This conftest provides common fixtures that are shared across:
- Shared infrastructure tests (health, versioning)
- Module-specific tests (broker, datafeed)
- Integration tests

Fixtures defined here are automatically available to all test files
in trading_api and its subdirectories.
"""

import asyncio
from collections.abc import AsyncGenerator, Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient

from trading_api.app_factory import AppFactory, ModularApp
from trading_api.shared import FastWSAdapter

# ============================================================================
# Event Loop Override for Session-Scoped Async Fixtures
# ============================================================================


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for session-scoped async fixtures.

    Required for pytest-asyncio 0.21.x with session-scoped async fixtures.
    Without this, you'll get: "ScopeMismatch: You tried to access the
    function scoped fixture event_loop with a session scoped request object"

    Also prevents: "RuntimeWarning: coroutine 'async_finalizer' was never awaited"
    during test teardown.
    """
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop


# ============================================================================
# Application Fixtures (Session-Scoped for Performance)
# ============================================================================


@pytest.fixture(scope="session")
def apps() -> ModularApp:
    """Full application with all modules enabled (shared across session).

    This fixture is the source for all other app-related fixtures.
    It creates a ModularApp with all discovered modules enabled.
    """
    factory = AppFactory()
    return factory.create_app()


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
