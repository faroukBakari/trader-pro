"""Test fixtures for broker module tests.

Creates test app with only broker module enabled for isolation.
Other fixtures (app, ws_app, client, async_client) are inherited from shared/tests/conftest.py.
"""

import pytest

from trading_api.app_factory import AppFactory, ModularFastAPI
from trading_api.shared import FastWSAdapter


@pytest.fixture(scope="session")
def apps() -> tuple[ModularFastAPI, list[FastWSAdapter]]:
    """Application with only broker module enabled (shared across session)."""
    factory = AppFactory()
    modular_app = factory.create_app(enabled_module_names=["broker"])
    return modular_app, modular_app.ws_apps
