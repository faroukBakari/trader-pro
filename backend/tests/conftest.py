"""
Test fixtures for trading API.

Phase 0: Wrap current globals to enable gradual migration.
Phase 6: Update _get_current_app() to use factory pattern.
"""

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient


def _get_current_app():
    """
    Get application instance.

    Phase 0 (Current): Returns app from main.py globals
    Phase 6 (Future): Will use app_factory.create_app()
    """
    from trading_api.main import apiApp

    return apiApp


@pytest.fixture
def app():
    """Full application with all modules."""
    return _get_current_app()


@pytest.fixture
def client(app):
    """Sync test client for WebSocket tests."""
    return TestClient(app)


@pytest.fixture
async def async_client(app):
    """Async test client for API tests."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


# Module-specific fixtures (placeholders for Phase 6)
@pytest.fixture
def datafeed_only_app():
    """
    Datafeed module only.

    Phase 0: Returns full app (same as app fixture)
    Phase 6: Will use create_app(enabled_modules=['datafeed'])
    """
    return _get_current_app()


@pytest.fixture
def broker_only_app():
    """
    Broker module only.

    Phase 0: Returns full app (same as app fixture)
    Phase 6: Will use create_app(enabled_modules=['broker'])
    """
    return _get_current_app()
