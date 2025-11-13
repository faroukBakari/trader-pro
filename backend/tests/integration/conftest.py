"""Test fixtures for integration tests.

Creates full-stack application with ALL modules enabled.
Provides session-scoped multi-process service fixtures for client testing.
Provides session-scoped module isolation fixtures for fast test execution.
"""

import multiprocessing
import os
import sys
import time
from collections.abc import AsyncGenerator
from pathlib import Path

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient
from httpx import AsyncClient
from jose import jwt

from trading_api.app_factory import ModularApp
from trading_api.shared import FastWSAdapter
from trading_api.shared.config import Settings

# Add backend scripts to path for backend_manager imports
backend_scripts_dir = Path(__file__).parent.parent.parent / "scripts"
if str(backend_scripts_dir) not in sys.path:
    sys.path.insert(0, str(backend_scripts_dir))


# ============================================================================
# Authentication Fixtures
# ============================================================================


@pytest.fixture
def valid_jwt_token() -> str:
    """Generate a valid JWT token for authentication."""
    settings = Settings()
    payload = {
        "user_id": "TEST-USER-001",
        "email": "test@example.com",
        "full_name": "Test User",
        "picture": "https://example.com/avatar.jpg",
        "exp": int(time.time()) + 300,
        "iat": int(time.time()),
    }
    return jwt.encode(
        payload, settings.jwt_private_key, algorithm=settings.JWT_ALGORITHM
    )


@pytest.fixture
def auth_cookies(valid_jwt_token: str) -> dict[str, str]:
    """Generate authentication cookies for testing."""
    return {"access_token": valid_jwt_token}


# ============================================================================
# Module Isolation Fixtures (Session-Scoped for Performance)
# ============================================================================


@pytest.fixture(scope="session")
def datafeed_only_app() -> ModularApp:
    """Session-scoped datafeed-only app for isolation tests."""
    from trading_api.app_factory import AppFactory

    factory = AppFactory()
    return factory.create_app(enabled_module_names=["datafeed"])


@pytest.fixture(scope="session")
def broker_only_app() -> ModularApp:
    """Session-scoped broker-only app for isolation tests."""
    from trading_api.app_factory import AppFactory

    factory = AppFactory()
    return factory.create_app(enabled_module_names=["broker"])


@pytest.fixture(scope="session")
def all_modules_app() -> ModularApp:
    """Session-scoped app with all modules for isolation tests."""
    from trading_api.app_factory import AppFactory

    factory = AppFactory()
    return factory.create_app(enabled_module_names=None)


@pytest.fixture(scope="session")
def no_modules_app() -> ModularApp:
    """Session-scoped app with no modules (shared infrastructure only)."""
    from trading_api.app_factory import AppFactory

    factory = AppFactory()
    return factory.create_app(enabled_module_names=[])


# ============================================================================
# Multi-Process Service Fixtures
# ============================================================================


def run_service(module_name: str, port: int) -> None:
    """Run a single module as a separate service.

    Args:
        module_name: Name of the module to run (broker or datafeed)
        port: Port to bind the service to
    """
    # Set environment variable to enable only this module
    os.environ["ENABLED_MODULES"] = module_name

    # Run uvicorn server
    uvicorn.run(
        "trading_api.main:app",
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False,
    )


def wait_for_service_sync(base_url: str, max_attempts: int = 30) -> bool:
    """Wait for a service to become available (synchronous version).

    Args:
        base_url: Base URL of the service
        max_attempts: Maximum number of connection attempts

    Returns:
        True if service is available, False otherwise
    """
    for _ in range(max_attempts):
        try:
            # Try broker first, then datafeed if broker fails
            response = httpx.get(f"{base_url}/api/v1/broker/health", timeout=0.2)
            if response.status_code == 200:
                return True
            response = httpx.get(f"{base_url}/api/v1/datafeed/health", timeout=0.2)
            if response.status_code == 200:
                return True
        except (httpx.ConnectError, httpx.RemoteProtocolError, httpx.ReadTimeout):
            time.sleep(0.2)
    return False


@pytest.fixture(scope="module")
def apps() -> ModularApp:
    """Full application with all modules enabled (shared per test module)."""
    from trading_api.app_factory import AppFactory

    factory = AppFactory()
    return factory.create_app(enabled_module_names=None)  # None = all modules


@pytest.fixture(scope="module")
def app(apps: ModularApp) -> ModularApp:
    """ModularApp application instance (shared per test module).

    ModularApp extends FastAPI, so we can use it directly.
    """
    return apps  # ModularApp IS a FastAPI


@pytest.fixture(scope="module")
def ws_apps(apps: ModularApp) -> list[FastWSAdapter]:
    """FastWSAdapter application instances (shared per test module)."""
    return [
        ws_app for module_app in apps.modules_apps for ws_app in module_app.ws_versions
    ]


@pytest.fixture(scope="module")
def ws_app(ws_apps: list[FastWSAdapter]) -> FastWSAdapter | None:
    """First FastWSAdapter application instance (shared per test module)."""
    return ws_apps[0] if ws_apps else None


@pytest.fixture
def client(app: ModularApp, valid_jwt_token: str):
    """Sync test client for WebSocket tests with authentication cookies.

    Uses context manager to ensure proper cleanup of TestClient's internal event loop.
    """
    with TestClient(app) as c:
        c.cookies.set("access_token", valid_jwt_token)
        yield c


@pytest.fixture
def client_no_auth(app: ModularApp):
    """Sync test client WITHOUT authentication (for testing auth rejection).

    Uses context manager to ensure proper cleanup of TestClient's internal event loop.
    """
    with TestClient(app) as c:
        yield c


@pytest.fixture
async def async_client(
    app: ModularApp, auth_cookies: dict[str, str]
) -> AsyncGenerator[AsyncClient, None]:
    """Async test client for API tests with authentication cookies."""
    async with AsyncClient(app=app, base_url="http://test", cookies=auth_cookies) as ac:
        yield ac


@pytest.fixture
async def async_client_no_auth(app: ModularApp) -> AsyncGenerator[AsyncClient, None]:
    """Async test client for API tests WITHOUT authentication (for testing auth flows)."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture(scope="session")
def broker_service():
    """Start broker service once per session.

    Returns:
        Base URL of the broker service (http://127.0.0.1:8001)
    """
    port = 8001
    process = multiprocessing.Process(target=run_service, args=("broker", port))
    process.start()

    # Wait for service to become available
    base_url = f"http://127.0.0.1:{port}"
    if not wait_for_service_sync(base_url):
        process.terminate()
        pytest.fail("Broker service failed to start")

    yield base_url

    # Cleanup after ALL tests in session
    process.terminate()
    process.join(timeout=5)
    if process.is_alive():
        process.kill()
        process.join()


@pytest.fixture(scope="session")
def datafeed_service():
    """Start datafeed service once per session.

    Returns:
        Base URL of the datafeed service (http://127.0.0.1:8002)
    """
    port = 8002
    process = multiprocessing.Process(target=run_service, args=("datafeed", port))
    process.start()

    # Wait for service to become available
    base_url = f"http://127.0.0.1:{port}"
    if not wait_for_service_sync(base_url):
        process.terminate()
        pytest.fail("Datafeed service failed to start")

    yield base_url

    # Cleanup after ALL tests in session
    process.terminate()
    process.join(timeout=1)
    if process.is_alive():
        process.kill()
        process.join()
