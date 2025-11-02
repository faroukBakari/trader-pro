"""Core module test fixtures."""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from trading_api.app_factory import AppFactory, ModularFastAPI


def create_core_test_app() -> ModularFastAPI:
    """Create a test application with only core module enabled.

    Returns:
        ModularFastAPI: Application instance with core module
    """
    factory = AppFactory()
    return factory.create_apps(enabled_module_names=["core"])


@pytest.fixture(scope="function")
def app() -> ModularFastAPI:
    """ModularFastAPI application with only core module enabled."""
    return create_core_test_app()


@pytest.fixture(scope="function")
async def async_client(app: ModularFastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client for testing core endpoints."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"  # type: ignore[arg-type]
    ) as client:
        yield client
