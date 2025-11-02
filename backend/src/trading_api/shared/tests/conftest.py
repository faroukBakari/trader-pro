"""Shared test fixtures for all test suites.

This module provides a generic test app factory and the apps fixture for shared tests.
Other common fixtures (app, ws_app, client, async_client) are defined in the root
trading_api/conftest.py and are available to all tests via pytest discovery.

Each test suite can create an app with only the modules it needs for isolation.
"""

import pytest
from fastapi import FastAPI

from trading_api.shared import FastWSAdapter


def create_test_app(
    enabled_modules: list[str] | None = None,
) -> tuple[FastAPI, list[FastWSAdapter]]:
    """Create a test application with specified modules.

    Args:
        enabled_modules: List of module names to enable (e.g., ["broker", "datafeed"])
                        If None, all modules are enabled.

    Returns:
        tuple: (FastAPI application, list of FastWSAdapter applications)

    Example:
        # Test with all modules
        api_app, ws_apps = create_test_app()

        # Test with only broker module
        api_app, ws_apps = create_test_app(enabled_modules=["broker"])

        # Test with only shared infrastructure (no modules)
        api_app, ws_apps = create_test_app(enabled_modules=[])
    """
    from trading_api.app_factory import mount_modules

    return mount_modules(enabled_module_names=enabled_modules)


@pytest.fixture(scope="session")
def apps() -> tuple[FastAPI, list[FastWSAdapter]]:
    """Full application (API + WS) with all modules enabled (shared across session)."""
    return create_test_app(enabled_modules=None)
