"""Test fixtures for broker module tests.

Creates test app with only broker module enabled for isolation.
Other fixtures (app, ws_app, client, async_client) are inherited from shared/tests/conftest.py.
"""

import pytest

from trading_api.app_factory import AppFactory, ModularApp


@pytest.fixture(scope="session")
def apps() -> ModularApp:
    """Application with only broker module enabled (shared across session)."""
    factory = AppFactory()
    return factory.create_app(enabled_module_names=["broker"])
