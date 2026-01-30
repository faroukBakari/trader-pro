"""Test fixtures for broker module tests.

Overrides the root apps fixture to load only broker-related modules and providers.
Uses FakeBrokerProvider instead of TWS for predictable test behavior.

Provides direct access to BrokerService and BrokerProvider for tests that need
to manipulate broker state directly (e.g., reset, execute_all_working_orders).
"""

from pathlib import Path

import pytest

from trading_api.app_factory import ModularApp
from trading_api.capabilities.broker import BrokerCapability
from trading_api.modules.broker.service import BrokerService
from trading_api.shared import (
    DatastoreRegistry,
    ModuleApp,
    ModuleRegistry,
    ProviderRegistry,
    settings,
)


@pytest.fixture(scope="module")
async def apps() -> ModularApp:
    """Broker-specific app with only broker and auth modules.

    Uses FakeBrokerProvider instead of TWS to avoid external dependencies
    and ensure tests work with simple symbol formats (e.g., "AAPL").
    """
    # Create registries directly for test isolation
    modules_dir = Path(__file__).parents[2]
    providers_dir = Path(__file__).parents[3] / "providers"
    datastores_dir = Path(__file__).parents[3] / "datastores"

    module_registry = ModuleRegistry(modules_dir)
    provider_registry = ProviderRegistry(providers_dir)
    datastore_registry = DatastoreRegistry(datastores_dir)

    # Auto-discover broker and auth modules with fakebroker and google providers
    module_registry.auto_discover(enabled_modules=["broker", "auth"])
    provider_registry.auto_discover(enabled_names=["fakebroker", "google"])
    datastore_registry.auto_discover(enabled_names=["inmemory"])

    # Create datastore using async/await (avoid asyncio.get_event_loop() for Python 3.10+)
    datastores = await datastore_registry.get_datastores()

    # Get providers
    required_capabilities = module_registry.required_capabilities()
    providers = await provider_registry.get_providers(required_capabilities)

    # Get modules with providers and datastores
    enabled_modules = module_registry.get_modules(
        providers=providers,
        datastores=datastores,
    )

    # Create ModularApp without lifespan (simpler for tests)
    app = ModularApp(
        base_url=settings.API_PREFIX,
        enabled_modules=["broker", "auth"],
        enabled_providers=["fakebroker", "google"],
        enabled_datastores=["inmemory"],
        title="Trading API (Test)",
        version="1.0.0",
    )

    # Manually set runtime state (normally done in build_modules)
    app._modules = enabled_modules
    app._modules_apps = [ModuleApp(module) for module in enabled_modules]

    # Mount module routes (normally done in _start)
    for module_app in app._modules_apps:
        for api_app in module_app.api_versions:
            mount_path = f"{app.base_url}/{api_app.version}/{module_app.module.name}"
            app.mount(mount_path, api_app)

        # Start module
        module_app.start()

    return app


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
