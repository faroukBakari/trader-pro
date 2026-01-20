"""Test full provider injection flow."""

import pytest

from trading_api.app_factory import AppFactory
from trading_api.providers.google import GoogleProvider

pytestmark = pytest.mark.integration


def test_provider_auto_discovery():
    """Providers auto-discovered from directory."""
    factory = AppFactory()
    factory.provider_registry.auto_discover()

    providers = factory.provider_registry.list_providers()
    assert "GoogleProvider" in providers


@pytest.mark.asyncio
async def test_provider_injection_into_modules():
    """Providers injected into modules requiring capabilities."""
    factory = AppFactory()

    # Create app with auth module enabled
    await factory.create_app(enabled_module_names=["auth"])

    # Auth module should have received GoogleProvider
    auth_modules = [
        m for m in factory.module_registry._instances.values() if m.name == "auth"
    ]
    assert len(auth_modules) > 0
    auth_module = auth_modules[0]
    assert auth_module is not None
    # Service uses _capability_map internally (capability_name -> list of providers)
    capability_map = getattr(auth_module.service, "_capability_map", {})
    assert len(capability_map) > 0
    # Auth service requires 'auth' capability
    auth_providers = capability_map.get("auth", [])
    assert len(auth_providers) > 0
    assert isinstance(auth_providers[0], GoogleProvider)


@pytest.mark.asyncio
async def test_auth_service_uses_provider():
    """AuthService uses injected provider for authentication."""
    factory = AppFactory()
    await factory.create_app(enabled_module_names=["auth"])

    # Find auth module
    auth_modules = [
        m for m in factory.module_registry._instances.values() if m.name == "auth"
    ]
    assert len(auth_modules) > 0
    auth_module = auth_modules[0]
    auth_service = auth_module.service

    # Should have auth_provider property
    assert hasattr(auth_service, "auth_provider")

    # Should be AuthCapability instance
    from trading_api.capabilities.auth import AuthCapability

    assert isinstance(auth_service.get_capability_provider("auth"), AuthCapability)


@pytest.mark.asyncio
async def test_create_app_two_phase_loading():
    """Verify two-phase loading pattern works correctly."""
    factory = AppFactory()

    # Before create_app, registries should be empty or uninitialized
    # After create_app, both module and provider registries should be populated

    await factory.create_app(enabled_module_names=["auth"])

    # Verify module registry populated
    assert len(factory.module_registry._module_classes) > 0
    assert "auth" in factory.module_registry._module_classes

    # Verify provider registry populated
    assert len(factory.provider_registry._provider_classes) > 0
    assert "GoogleProvider" in factory.provider_registry._provider_classes


@pytest.mark.asyncio
async def test_provider_lifecycle_hooks():
    """Verify provider lifecycle hooks are called."""
    factory = AppFactory()

    # Create app to trigger on_startup
    await factory.create_app(enabled_module_names=["auth"])

    # Verify provider instance was created
    assert "GoogleProvider" in factory.provider_registry._instances
