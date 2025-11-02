"""Test fixtures for datafeed module tests.

Creates test app with only datafeed module enabled for isolation.
Other fixtures (app, ws_app, client, async_client) are inherited from shared/tests/conftest.py.
"""

import pytest

from trading_api.app_factory import AppFactory, ModularFastAPI
from trading_api.shared import FastWSAdapter


@pytest.fixture(scope="session")
def apps() -> tuple[ModularFastAPI, list[FastWSAdapter]]:
    """Application with only datafeed module enabled (shared across session)."""
    factory = AppFactory()
    modular_app = factory.create_apps(enabled_module_names=["datafeed"])
    return modular_app, modular_app.ws_apps
