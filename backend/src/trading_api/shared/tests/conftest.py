"""Shared test fixtures for all test suites.

This module provides a generic test app factory and the apps fixture for shared tests.
Other common fixtures (app, ws_apps, ws_app, client, async_client) are defined in the root
trading_api/conftest.py and are available to all tests via pytest discovery.

Each test suite can create an app with only the modules it needs for isolation.
"""

import pytest

from trading_api.app_factory import AppFactory, ModularApp


async def create_test_app(
    enabled_modules: list[str] | None = None,
    enabled_datastores: list[str] | None = None,
) -> ModularApp:
    """Create a test application with specified modules.

    Args:
        enabled_modules: List of module names to enable (e.g., ["broker", "datafeed"])
                        If None, all modules are enabled.
        enabled_datastores: List of datastore names (defaults to ["inmemory"] for tests)

    Returns:
        ModularApp: Modular application (extends FastAPI)

    Example:
        # Test with all modules
        app = await create_test_app()

        # Test with only broker module
        app = await create_test_app(enabled_modules=["broker"])

        # Test with only shared infrastructure (no modules)
        app = await create_test_app(enabled_modules=[])
    """
    if enabled_datastores is None:
        enabled_datastores = ["inmemory"]  # Default to inmemory for tests
    factory = AppFactory()
    return await factory.create_app(
        enabled_module_names=enabled_modules,
        enabled_datastores=enabled_datastores,
    )


@pytest.fixture(scope="session")
async def apps() -> ModularApp:
    """Full application with all modules enabled (shared across session)."""
    return await create_test_app()
