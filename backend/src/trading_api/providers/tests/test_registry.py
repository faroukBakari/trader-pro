"""Test ProviderRegistry auto-discovery and lazy-loading."""

from pathlib import Path

import pytest

from trading_api.models.common import CapabilitySpec, ProviderConfig
from trading_api.models.exceptions import CommonException
from trading_api.shared import Provider
from trading_api.shared.provider_registry import ProviderRegistry


class MockProviderConfig(ProviderConfig):
    """Mock provider configuration."""

    test_value: str = "default"


class MockProvider(Provider):
    """Mock provider for testing."""

    _startup_called = False
    _shutdown_called = False

    @classmethod
    def provider_dir(cls) -> Path:
        return Path(__file__).parent

    @property
    def name(self) -> str:
        return "mock"

    @classmethod
    def capabilities(cls) -> list[CapabilitySpec]:
        return [CapabilitySpec(name="auth")]

    @property
    def config(self) -> ProviderConfig:
        return MockProviderConfig()


@pytest.fixture
def registry() -> ProviderRegistry:
    """Create fresh registry for testing."""
    return ProviderRegistry()


def test_register_provider(registry: ProviderRegistry) -> None:
    """Test manual provider registration."""
    registry.register(MockProvider, "mock")

    assert "mock" in registry.list_providers()
    assert len(registry.list_providers()) == 1


def test_register_duplicate_provider_raises_error(registry: ProviderRegistry) -> None:
    """Cannot register same provider twice."""
    registry.register(MockProvider, "mock")

    with pytest.raises(ValueError, match="already registered"):
        registry.register(MockProvider, "mock")


@pytest.mark.asyncio
async def test_get_providers_by_capability(registry: ProviderRegistry) -> None:
    """Get providers matching capability requirements."""
    registry.register(MockProvider, "mock")

    providers = await registry.get_providers([CapabilitySpec(name="auth")])

    assert len(providers) == 1
    assert isinstance(providers[0], MockProvider)


@pytest.mark.asyncio
async def test_get_providers_capability_not_found(registry: ProviderRegistry) -> None:
    """Raise error when no provider satisfies capability."""
    registry.register(MockProvider, "mock")

    # MockProvider only provides "auth", not "broker"
    with pytest.raises(CommonException, match="No provider found"):
        await registry.get_providers([CapabilitySpec(name="broker")])


@pytest.mark.asyncio
async def test_lazy_loading(registry: ProviderRegistry) -> None:
    """Providers are lazy-loaded on first request."""
    registry.register(MockProvider, "mock")

    # No instances yet
    assert len(registry._instances) == 0

    # First request creates instance
    providers = await registry.get_providers([CapabilitySpec(name="auth")])
    assert len(providers) == 1
    assert len(registry._instances) == 1

    # Second request reuses instance
    providers2 = await registry.get_providers([CapabilitySpec(name="auth")])
    assert providers[0] is providers2[0]  # Same instance


def test_clear_registry(registry: ProviderRegistry) -> None:
    """Clear all registered providers."""
    registry.register(MockProvider, "mock")
    assert len(registry.list_providers()) == 1

    registry.clear()
    assert len(registry.list_providers()) == 0


@pytest.mark.asyncio
async def test_deduplication(registry: ProviderRegistry) -> None:
    """Same provider not instantiated multiple times for different capabilities."""
    registry.register(MockProvider, "mock")

    # Request same provider via same capability multiple times
    providers = await registry.get_providers(
        [CapabilitySpec(name="auth"), CapabilitySpec(name="auth")]
    )

    # Should only have one instance (deduplicated)
    assert len(providers) == 1
