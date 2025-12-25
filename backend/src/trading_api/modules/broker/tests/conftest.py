"""Test fixtures for broker module tests.

Overrides the root apps fixture to load only broker-related modules and providers.
Uses FakeBrokerProvider instead of TWS for predictable test behavior.

Provides direct access to BrokerService and BrokerProvider for tests that need
to manipulate broker state directly (e.g., reset, execute_all_working_orders).
"""

import pytest

from trading_api.app_factory import AppFactory, ModularApp
from trading_api.capabilities.broker import BrokerCapability
from trading_api.modules.broker.service import BrokerService


@pytest.fixture(scope="module")
async def apps() -> ModularApp:
    """Broker-specific app with only broker and auth modules.

    Uses FakeBrokerProvider instead of TWS to avoid external dependencies
    and ensure tests work with simple symbol formats (e.g., "AAPL").
    """
    factory = AppFactory()
    return await factory.create_app(
        enabled_module_names=["broker", "auth"],
        enabled_provider_names=["fakebroker", "google"],
    )


@pytest.fixture(scope="module")
def broker_service(apps: ModularApp) -> BrokerService:
    """Extract BrokerService from the modular app.

    Args:
        apps: The full modular application with all modules

    Returns:
        BrokerService: The broker service instance
    """
    # Find the broker module app
    for module_app in apps.modules_apps:
        if isinstance(module_app.module.service, BrokerService):
            return module_app.module.service

    raise RuntimeError("BrokerService not found in apps.modules_apps")


@pytest.fixture(scope="module")
def broker_provider(broker_service: BrokerService) -> BrokerCapability:
    """Get the broker provider from the service.

    Args:
        broker_service: The broker service instance

    Returns:
        BrokerCapability: The broker provider (e.g., FakeBrokerProvider)
    """
    return broker_service.broker_provider


@pytest.fixture
def reset_broker(broker_provider: BrokerCapability) -> None:
    """Reset broker state before test.

    Should be used by tests that need a clean broker state.

    Args:
        broker_provider: The broker provider instance
    """
    reset_fn = getattr(broker_provider, "reset", None)
    if reset_fn is not None:
        reset_fn()
