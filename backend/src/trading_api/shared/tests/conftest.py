"""Shared test fixtures for all test suites.

This module provides a generic test app factory and the apps fixture for shared tests.
Other common fixtures (app, ws_apps, ws_app, client, async_client) are defined in the root
trading_api/conftest.py and are available to all tests via pytest discovery.

Each test suite can create an app with only the modules it needs for isolation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from trading_api.app_factory import AppFactory, ModularApp
from trading_api.models.common import DatastoreCapabilitySpec
from trading_api.shared import DatastoreInterface, TableInterface

if TYPE_CHECKING:
    from trading_api.shared.config import Settings


class NullDatastore(DatastoreInterface):
    """Zero-capability datastore stub for tests that verify 'no capability' scenarios.

    Not a real storage backend — all table operations raise NotImplementedError.
    Use this when testing service behavior with a datastore that lacks capabilities.
    """

    @classmethod
    def capabilities(cls) -> list[DatastoreCapabilitySpec]:
        return []

    @classmethod
    async def create(cls, config: Settings | None = None) -> NullDatastore:
        return cls()

    def table(self, model_class: type) -> TableInterface:
        raise NotImplementedError("NullDatastore does not support tables")

    async def list_tables(self, prefix: str | None = None) -> list[str]:
        return []

    async def drop_table(self, name: str) -> bool:
        return False


async def create_test_app(
    enabled_modules: list[str] | None = None,
    enabled_datastores: list[str] | None = None,
) -> ModularApp:
    """Create a test application with specified modules.

    Args:
        enabled_modules: List of module names to enable (e.g., ["broker", "datafeed"])
                        If None, all modules are enabled.
        enabled_datastores: List of datastore names (defaults to ["duckdb"] for tests)

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
        enabled_datastores = ["duckdb"]  # Default to DuckDB :memory: for tests
    factory = AppFactory()
    return await factory.create_app(
        enabled_module_names=enabled_modules,
        enabled_datastores=enabled_datastores,
    )


@pytest.fixture(scope="session")
async def apps() -> ModularApp:
    """Full application with all modules enabled (shared across session)."""
    return await create_test_app()
