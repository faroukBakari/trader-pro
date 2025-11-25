"""Test TWS provider injection into DatafeedService."""

from unittest.mock import MagicMock, patch

import pytest

from trading_api.app_factory import AppFactory
from trading_api.providers.capabilities.datafeed import DatafeedCapability
from trading_api.providers.tws import TWSProvider


@pytest.fixture
def mock_tws_connection():
    """Mock TWSConnection to avoid real broker connection in tests."""
    with patch("trading_api.providers.tws.TWSConnection") as mock_conn_class:
        # Create mock instance
        mock_instance = MagicMock()
        mock_instance.is_ready.wait.return_value = (
            True  # Simulate successful connection
        )
        mock_instance.is_ready.is_set.return_value = True
        mock_instance.get_req_id.return_value = 1
        mock_instance.disconnect = MagicMock()

        # Make the class return our mock instance
        mock_conn_class.return_value = mock_instance

        yield mock_instance


@pytest.mark.asyncio
async def test_tws_provider_injection(mock_tws_connection):
    """Test TWSProvider is injected into DatafeedService."""
    factory = AppFactory()

    # Create app with datafeed module enabled
    await factory.create_app(enabled_module_names=["datafeed"])

    # Verify provider was discovered and registered
    assert "tws" in factory.provider_registry.list_providers()

    # Find datafeed module
    datafeed_modules = [
        m for m in factory.module_registry._instances.values() if m.name == "datafeed"
    ]
    assert len(datafeed_modules) > 0

    datafeed_module = datafeed_modules[0]
    service = datafeed_module.service

    # Verify provider was injected
    assert len(service._providers) > 0

    # Verify it's a TWSProvider instance
    provider = service.get_capability_provider("datafeed")
    assert isinstance(provider, TWSProvider)
    assert provider.name == "tws"


@pytest.mark.asyncio
async def test_datafeed_service_has_provider_property(mock_tws_connection):
    """Test DatafeedService has datafeed_provider property."""
    factory = AppFactory()
    await factory.create_app(enabled_module_names=["datafeed"])

    # Find datafeed module
    datafeed_modules = [
        m for m in factory.module_registry._instances.values() if m.name == "datafeed"
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
    """Test TWSProvider implements DatafeedCapability."""
    factory = AppFactory()
    await factory.create_app(enabled_module_names=["datafeed"])

    # Get TWSProvider instance
    tws_provider = factory.provider_registry._instances.get("tws")
    assert tws_provider is not None
    assert isinstance(tws_provider, TWSProvider)

    # Verify it implements DatafeedCapability
    assert isinstance(tws_provider, DatafeedCapability)

    # Verify capabilities declared
    capabilities = TWSProvider.capabilities()
    assert len(capabilities) == 1
    assert capabilities[0].name == "datafeed"
