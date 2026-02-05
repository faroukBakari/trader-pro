"""Test TWS provider injection into DatafeedService."""

from unittest.mock import MagicMock, patch

import pytest

from trading_api.app_factory import AppFactory
from trading_api.capabilities.datafeed import DatafeedCapability
from trading_api.providers.tws import TWSDatafeedProvider

pytestmark = pytest.mark.integration


@pytest.fixture
def mock_tws_connection():
    """Mock TWSClient to avoid real broker connection in tests."""
    with patch(
        "trading_api.providers.tws.tws_connection.TWSClient"
    ) as mock_client_class:
        # Create mock instance
        mock_instance = MagicMock()
        mock_instance._cb_wrapper._ready_event.is_set.return_value = True
        mock_instance._cb_wrapper._ready_event.wait.return_value = True
        mock_instance.next_req_id = 1
        mock_instance.shutdown = MagicMock()

        # Make the class return our mock instance
        mock_client_class.return_value = mock_instance

        yield mock_instance


@pytest.mark.asyncio
async def test_tws_provider_injection(mock_tws_connection):
    """Test TWSDatafeedProvider is injected into DatafeedService."""
    # Create app with datafeed module enabled
    factory = AppFactory()
    app = await factory.create_app(
        enabled_module_names=["datafeed"], enabled_datastores=["inmemory"]
    )

    # Call build_modules() to populate runtime state (normally done in lifespan)
    await app.build_modules()

    # Verify provider was discovered and registered (uses class name)
    assert "TWSDatafeedProvider" in app.provider_registry.list_providers()

    # Find datafeed module
    datafeed_modules = [
        m for m in app.module_registry._instances.values() if m.name == "datafeed"
    ]
    assert len(datafeed_modules) > 0

    datafeed_module = datafeed_modules[0]
    service = datafeed_module.service

    # Verify provider was injected (service uses _capability_map)
    assert len(service._capability_map) > 0

    # Verify it's a TWSDatafeedProvider instance
    provider = service.get_capability_provider("datafeed")
    assert isinstance(provider, TWSDatafeedProvider)
    assert provider.name == "tws"


@pytest.mark.asyncio
async def test_datafeed_service_has_provider_property(mock_tws_connection):
    """Test DatafeedService has datafeed_provider property."""
    factory = AppFactory()
    app = await factory.create_app(
        enabled_module_names=["datafeed"], enabled_datastores=["inmemory"]
    )

    # Call build_modules() to populate runtime state (normally done in lifespan)
    await app.build_modules()

    # Find datafeed module
    datafeed_modules = [
        m for m in app.module_registry._instances.values() if m.name == "datafeed"
    ]
    assert len(datafeed_modules) > 0

    datafeed_module = datafeed_modules[0]
    service = datafeed_module.service

    # Should have datafeed_provider property
    assert hasattr(service, "datafeed_provider")

    # Should be DatafeedCapability instance
    assert isinstance(service.get_capability_provider("datafeed"), DatafeedCapability)


@pytest.mark.asyncio
async def test_tws_provider_has_datafeed_capability(mock_tws_connection):
    """Test TWSDatafeedProvider implements DatafeedCapability."""
    factory = AppFactory()
    app = await factory.create_app(
        enabled_module_names=["datafeed"], enabled_datastores=["inmemory"]
    )

    # Call build_modules() to populate runtime state (normally done in lifespan)
    await app.build_modules()

    # Get TWSDatafeedProvider from module service
    datafeed_modules = [
        m for m in app.module_registry._instances.values() if m.name == "datafeed"
    ]
    assert len(datafeed_modules) > 0
    datafeed_module = datafeed_modules[0]
    datafeed_providers = datafeed_module.service._capability_map.get("datafeed", [])
    tws_providers = [p for p in datafeed_providers if p.name == "tws"]
    assert len(tws_providers) > 0
    tws_provider = tws_providers[0]
    assert isinstance(tws_provider, TWSDatafeedProvider)

    # Verify it implements DatafeedCapability
    assert isinstance(tws_provider, DatafeedCapability)

    # Verify capabilities declared
    capabilities = TWSDatafeedProvider.capabilities()
    assert len(capabilities) == 1
    assert capabilities[0].name == "datafeed"
