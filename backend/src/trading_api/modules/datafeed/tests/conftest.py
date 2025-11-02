"""Test fixtures for datafeed module tests.

Creates test app with only datafeed module enabled for isolation.
Other fixtures (app, ws_app, client, async_client) are inherited from shared/tests/conftest.py.
"""

import pytest
from fastapi import FastAPI

from trading_api.shared import FastWSAdapter


@pytest.fixture(scope="session")
def apps() -> tuple[FastAPI, list[FastWSAdapter]]:
    """Application with only datafeed module enabled (shared across session)."""
    from trading_api.app_factory import mount_modules

    return mount_modules(enabled_module_names=["datafeed"])
