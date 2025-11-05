"""Shared test fixtures for all test suites.

This module provides a generic test app factory and the apps fixture for shared tests.
Other common fixtures (app, ws_apps, ws_app, client, async_client) are defined in the root
trading_api/conftest.py and are available to all tests via pytest discovery.

Each test suite can create an app with only the modules it needs for isolation.
"""

import asyncio
from typing import Generator

import pytest

from trading_api.app_factory import AppFactory, ModularApp


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for the entire test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


def create_test_app(
    enabled_modules: list[str] | None = None,
) -> ModularApp:
    """Create a test application with specified modules.

    Args:
        enabled_modules: List of module names to enable (e.g., ["broker", "datafeed"])
                        If None, all modules are enabled.

    Returns:
        ModularApp: Modular application (extends FastAPI)

    Example:
        # Test with all modules
        app = create_test_app()

        # Test with only broker module
        app = create_test_app(enabled_modules=["broker"])

        # Test with only shared infrastructure (no modules)
        app = create_test_app(enabled_modules=[])
    """
    factory = AppFactory()
    return factory.create_app(enabled_module_names=enabled_modules)


@pytest.fixture(scope="session")
def apps() -> ModularApp:
    """Full application with all modules enabled (shared across session)."""
    return create_test_app()
