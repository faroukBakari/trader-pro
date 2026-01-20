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
# Application Fixtures (Module-Scoped for Compatibility)
# ============================================================================
# Note: Module scope avoids event_loop scope conflicts with pytest-asyncio
# and matches the pattern used in tests/integration/conftest.py


@pytest.fixture(scope="module")
def apps() -> ModularApp:
    """Full application with all modules enabled (shared per test module).

    This fixture is the source for all other app-related fixtures.
    It creates a ModularApp with all discovered modules enabled.

    Note: Module-specific test suites should override this fixture to:
    - Load only required modules (enabled_module_names)
    - Use mock/fake providers (enabled_provider_names)

    Note: Uses sync wrapper to avoid pytest-asyncio event_loop scope conflicts.
    The session-scoped event_loop from tests/conftest.py is used.
    """
    factory = AppFactory()
    return asyncio.get_event_loop().run_until_complete(factory.create_app())


@pytest.fixture(scope="module")
def app(apps: ModularApp) -> FastAPI:
    """FastAPI application instance (shared per test module).

    ModularApp extends FastAPI, so we can use it directly.
    """
    return apps  # ModularApp IS a FastAPI


@pytest.fixture(scope="module")
def ws_apps(apps: ModularApp) -> list[FastWSAdapter]:
    """FastWSAdapter application instances (shared per test module).

    Extracts WebSocket apps from all modules.
    """
    return [
        ws_app for module_app in apps.modules_apps for ws_app in module_app.ws_versions
    ]


@pytest.fixture(scope="module")
def ws_app(ws_apps: list[FastWSAdapter]) -> FastWSAdapter | None:
    """First FastWSAdapter application instance (shared per test module)."""
    return ws_apps[0] if ws_apps else None


@pytest.fixture
def client(app: FastAPI) -> Generator[TestClient, None]:
    """Sync test client for WebSocket tests.

    Uses raise_server_exceptions=False so that exceptions are handled by
    FastAPI's exception handlers and return proper HTTP responses instead
    of bubbling up to the test.
    """
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
async def async_client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Async test client for API tests.

    Uses ASGITransport with raise_app_exceptions=False so that exceptions
    are handled by FastAPI's exception handlers and return proper HTTP responses
    instead of bubbling up to the test.
    """

    from httpx import ASGITransport

    transport = ASGITransport(
        app=app,  # type: ignore[arg-type]  # FastAPI is ASGI-compatible
        raise_app_exceptions=False,
    )
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
