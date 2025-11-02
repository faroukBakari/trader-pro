"""Test fixtures for integration tests.

Creates full-stack application with ALL modules enabled.
Provides session-scoped multi-process service fixtures for client testing.
Provides session-scoped module isolation fixtures for fast test execution.
"""

import multiprocessing
import os
import time
from collections.abc import AsyncGenerator

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient
from httpx import AsyncClient

from trading_api.app_factory import ModularFastAPI
from trading_api.shared import FastWSAdapter

# ============================================================================
# Module Isolation Fixtures (Session-Scoped for Performance)
# ============================================================================


@pytest.fixture(scope="session")
def datafeed_only_app() -> tuple[ModularFastAPI, list[FastWSAdapter]]:
    """Session-scoped datafeed-only app for isolation tests."""
    from trading_api.app_factory import AppFactory

    factory = AppFactory()
    modular_app = factory.create_app(enabled_module_names=["datafeed"])
    return modular_app, modular_app.ws_apps


@pytest.fixture(scope="session")
def broker_only_app() -> tuple[ModularFastAPI, list[FastWSAdapter]]:
    """Session-scoped broker-only app for isolation tests."""
    from trading_api.app_factory import AppFactory

    factory = AppFactory()
    modular_app = factory.create_app(enabled_module_names=["broker"])
    return modular_app, modular_app.ws_apps


@pytest.fixture(scope="session")
def all_modules_app() -> tuple[ModularFastAPI, list[FastWSAdapter]]:
    """Session-scoped app with all modules for isolation tests."""
    from trading_api.app_factory import AppFactory

    factory = AppFactory()
    modular_app = factory.create_app(enabled_module_names=None)
    return modular_app, modular_app.ws_apps


@pytest.fixture(scope="session")
def no_modules_app() -> tuple[ModularFastAPI, list[FastWSAdapter]]:
    """Session-scoped app with no modules (shared infrastructure only)."""
    from trading_api.app_factory import AppFactory

    factory = AppFactory()
    modular_app = factory.create_app(enabled_module_names=[])
    return modular_app, modular_app.ws_apps


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
            response = httpx.get(f"{base_url}/api/v1/core/health", timeout=0.2)
            if response.status_code == 200:
                return True
        except (httpx.ConnectError, httpx.RemoteProtocolError, httpx.ReadTimeout):
            time.sleep(0.2)
    return False


@pytest.fixture(scope="module")
def apps() -> tuple[ModularFastAPI, list[FastWSAdapter]]:
    """Full application with all modules enabled (shared per test module)."""
    from trading_api.app_factory import AppFactory

    factory = AppFactory()
    modular_app = factory.create_app(enabled_module_names=None)  # None = all modules
    return modular_app, modular_app.ws_apps


@pytest.fixture(scope="module")
def app(apps: tuple[ModularFastAPI, list[FastWSAdapter]]) -> ModularFastAPI:
    """ModularFastAPI application instance (shared per test module)."""
    api_app, _ = apps
    return api_app


@pytest.fixture(scope="module")
def ws_app(apps: tuple[ModularFastAPI, list[FastWSAdapter]]) -> FastWSAdapter | None:
    """FastWSAdapter application instance (shared per test module)."""
    _, ws_apps = apps
    return ws_apps[0] if ws_apps else None


@pytest.fixture
def client(app: ModularFastAPI) -> TestClient:
    """Sync test client for WebSocket tests."""
    return TestClient(app)


@pytest.fixture
async def async_client(app: ModularFastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Async test client for API tests."""
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
