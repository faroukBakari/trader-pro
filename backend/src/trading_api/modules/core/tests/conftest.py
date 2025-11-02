"""Core module test fixtures."""

from collections.abc import AsyncGenerator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


def create_core_test_app() -> FastAPI:
    """Create a test application with only core module enabled.

    Returns:
        FastAPI: Application instance with core module
    """
    from trading_api.app_factory import mount_app_modules

    api_app, _ = mount_app_modules(enabled_module_names=["core"])
    return api_app


@pytest.fixture(scope="function")
def app() -> FastAPI:
    """FastAPI application with only core module enabled."""
    return create_core_test_app()


@pytest.fixture(scope="function")
async def async_client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client for testing core endpoints."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"  # type: ignore[arg-type]
    ) as client:
        yield client
