"""Tests to verify module isolation and independence.

Tests that modules can be loaded independently and don't interfere with each other.
"""

import pytest


@pytest.mark.integration
def test_datafeed_only_isolation() -> None:
    """Verify datafeed-only app doesn't load broker."""
    from trading_api.app_factory import create_app

    api_app, _ = create_app(enabled_modules=["datafeed"])
    openapi_spec = api_app.openapi()
    paths = openapi_spec.get("paths", {})

    # Datafeed endpoints should exist
    assert any("/datafeed/" in path for path in paths)
    assert "/api/v1/datafeed/config" in paths

    # Broker endpoints should NOT exist
    assert not any("/broker/" in path for path in paths)

    # Shared endpoints should still exist
    assert "/api/v1/health" in paths
    assert "/api/v1/versions" in paths


@pytest.mark.integration
def test_broker_only_isolation() -> None:
    """Verify broker-only app doesn't load datafeed."""
    from trading_api.app_factory import create_app

    api_app, _ = create_app(enabled_modules=["broker"])
    openapi_spec = api_app.openapi()
    paths = openapi_spec.get("paths", {})

    # Broker endpoints should exist
    assert any("/broker/" in path for path in paths)
    assert "/api/v1/broker/orders" in paths
    assert "/api/v1/broker/positions" in paths
    assert "/api/v1/broker/executions/{symbol}" in paths

    # Datafeed endpoints should NOT exist
    assert not any("/datafeed/" in path for path in paths)

    # Shared endpoints should still exist
    assert "/api/v1/health" in paths
    assert "/api/v1/versions" in paths


@pytest.mark.integration
def test_module_registry_cleanup() -> None:
    """Verify registry is cleared between app creations."""
    from trading_api.app_factory import create_app, registry

    # Create app with all modules
    create_app(enabled_modules=None)
    all_modules_count = len(registry.get_all_modules())

    # Clear and create app with one module
    create_app(enabled_modules=["datafeed"])
    enabled_modules = registry.get_enabled_modules()
    one_module_count = len(enabled_modules)

    # Registry should have been cleared and only datafeed loaded
    assert all_modules_count >= 2  # Should have broker + datafeed at minimum
    assert one_module_count == 1
    assert enabled_modules[0].name == "datafeed"


@pytest.mark.integration
def test_shared_infrastructure_always_loaded() -> None:
    """Verify shared infrastructure is always available regardless of modules."""
    from trading_api.app_factory import create_app

    # Test with no modules
    api_app, _ = create_app(enabled_modules=[])
    openapi_spec = api_app.openapi()
    paths = openapi_spec.get("paths", {})

    # Shared endpoints should always exist
    assert "/api/v1/health" in paths
    assert "/api/v1/versions" in paths

    # No module endpoints should exist
    assert not any("/broker/" in path for path in paths)
    assert not any("/datafeed/" in path for path in paths)


@pytest.mark.integration
def test_module_service_independence() -> None:
    """Verify module services are independent and don't share state."""
    from trading_api.app_factory import create_app, registry

    # Create first app with broker module
    app1, _ = create_app(enabled_modules=["broker"])
    broker_module_1 = registry.get_module("broker")
    assert broker_module_1 is not None

    # Create second app with broker module
    app2, _ = create_app(enabled_modules=["broker"])
    broker_module_2 = registry.get_module("broker")
    assert broker_module_2 is not None

    # Modules should be different instances (due to registry clear)
    # Note: This test validates that create_app clears the registry
    # and creates fresh module instances each time
    assert broker_module_1 is not broker_module_2


@pytest.mark.integration
def test_module_prefix_consistency() -> None:
    """Verify module API prefixes match module names."""
    from trading_api.app_factory import create_app

    api_app, _ = create_app(enabled_modules=None)
    openapi_spec = api_app.openapi()
    paths = openapi_spec.get("paths", {})

    # Datafeed module: prefix should be /datafeed
    datafeed_paths = [p for p in paths if "/datafeed/" in p]
    assert all(p.startswith("/api/v1/datafeed/") for p in datafeed_paths)

    # Broker module: prefix should be /broker
    broker_paths = [p for p in paths if "/broker/" in p]
    assert all(p.startswith("/api/v1/broker/") for p in broker_paths)


@pytest.mark.integration
def test_websocket_routers_module_specific() -> None:
    """Verify WebSocket routers are only loaded with their modules."""
    from trading_api.app_factory import create_app

    # Create datafeed-only app
    _, ws_app_datafeed = create_app(enabled_modules=["datafeed"])
    datafeed_routes = [route.operation for route in ws_app_datafeed.router.routes]

    # Should have datafeed routes
    assert "bars.subscribe" in datafeed_routes or "bars.unsubscribe" in datafeed_routes
    assert (
        "quotes.subscribe" in datafeed_routes or "quotes.unsubscribe" in datafeed_routes
    )

    # Should NOT have broker routes
    assert not any("orders" in route for route in datafeed_routes)
    assert not any("positions" in route for route in datafeed_routes)
    assert not any("executions" in route for route in datafeed_routes)

    # Create broker-only app
    _, ws_app_broker = create_app(enabled_modules=["broker"])
    broker_routes = [route.operation for route in ws_app_broker.router.routes]

    # Should have broker routes
    assert any("orders" in route for route in broker_routes)
    assert any("positions" in route for route in broker_routes)
    assert any("executions" in route for route in broker_routes)

    # Should NOT have datafeed routes
    assert not any("bars" in route for route in broker_routes)
    assert not any("quotes" in route for route in broker_routes)


@pytest.mark.integration
def test_module_disabled_not_instantiated() -> None:
    """Verify disabled modules don't instantiate their services."""
    from trading_api.app_factory import create_app, registry

    # Create app with only datafeed
    create_app(enabled_modules=["datafeed"])

    # Get all modules from registry
    all_modules = registry.get_all_modules()
    enabled_modules = registry.get_enabled_modules()

    # Should have modules registered
    assert len(all_modules) >= 2

    # Only datafeed should be enabled
    assert len(enabled_modules) == 1
    assert enabled_modules[0].name == "datafeed"

    # Broker module should exist but be disabled
    broker_module = registry.get_module("broker")
    assert broker_module is not None
    assert not broker_module.enabled
