"""Tests to verify module isolation and independence.

Tests that modules can be loaded independently and don't interfere with each other.
All tests use session-scoped fixtures for performance.
"""

import pytest

from trading_api.app_factory import registry


@pytest.mark.integration
def test_datafeed_only_isolation(datafeed_only_app) -> None:
    """Verify datafeed-only app doesn't load broker."""
    api_app, _ = datafeed_only_app
    openapi_spec = api_app.openapi()
    paths = openapi_spec.get("paths", {})

    # Datafeed endpoints should exist
    assert any("/datafeed/" in path for path in paths)
    assert "/api/v1/datafeed/config" in paths

    # Broker endpoints should NOT exist
    assert not any("/broker/" in path for path in paths)

    # Shared endpoints should still exist
    assert "/api/v1/core/health" in paths
    assert "/api/v1/core/versions" in paths


@pytest.mark.integration
def test_broker_only_isolation(broker_only_app) -> None:
    """Verify broker-only app doesn't load datafeed."""
    api_app, _ = broker_only_app
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
    assert "/api/v1/core/health" in paths
    assert "/api/v1/core/versions" in paths


@pytest.mark.integration
def test_module_registry_state(all_modules_app, datafeed_only_app) -> None:
    """Verify registry state matches the app configuration.

    This test verifies that all modules are discovered but only enabled
    modules are reflected in the app's routes.
    """
    # Check all_modules_app has both broker and datafeed routes
    all_api_app, _ = all_modules_app
    all_paths = all_api_app.openapi().get("paths", {})
    assert any("/broker/" in p for p in all_paths)
    assert any("/datafeed/" in p for p in all_paths)

    # Check datafeed_only_app has only datafeed routes
    datafeed_api_app, _ = datafeed_only_app
    datafeed_paths = datafeed_api_app.openapi().get("paths", {})
    assert any("/datafeed/" in p for p in datafeed_paths)
    assert not any("/broker/" in p for p in datafeed_paths)

    # Registry should have discovered all available modules
    all_modules = registry.get_all_modules()
    assert len(all_modules) >= 2  # Should have broker + datafeed at minimum


@pytest.mark.integration
def test_shared_infrastructure_always_loaded(no_modules_app) -> None:
    """Verify shared infrastructure is always available regardless of modules."""
    api_app, _ = no_modules_app
    openapi_spec = api_app.openapi()
    paths = openapi_spec.get("paths", {})

    # Shared endpoints should always exist
    assert "/api/v1/core/health" in paths
    assert "/api/v1/core/versions" in paths

    # No module endpoints should exist
    assert not any("/broker/" in path for path in paths)
    assert not any("/datafeed/" in path for path in paths)


@pytest.mark.integration
def test_module_service_independence(broker_only_app, datafeed_only_app) -> None:
    """Verify each app configuration creates independent module instances.

    This validates that different app fixtures have independent FastAPI apps.
    """
    broker_api_app, _ = broker_only_app
    datafeed_api_app, _ = datafeed_only_app

    # The two apps should be different instances
    assert broker_api_app is not datafeed_api_app

    # Each should have their own routes
    broker_paths = set(broker_api_app.openapi().get("paths", {}).keys())
    datafeed_paths = set(datafeed_api_app.openapi().get("paths", {}).keys())

    # Broker should have broker-specific paths
    assert any("/broker/" in p for p in broker_paths)

    # Datafeed should have datafeed-specific paths
    assert any("/datafeed/" in p for p in datafeed_paths)


@pytest.mark.integration
def test_module_prefix_consistency(all_modules_app) -> None:
    """Verify module API prefixes match module names."""
    api_app, _ = all_modules_app
    openapi_spec = api_app.openapi()
    paths = openapi_spec.get("paths", {})

    # Datafeed module: prefix should be /datafeed
    datafeed_paths = [p for p in paths if "/datafeed/" in p]
    assert all(p.startswith("/api/v1/datafeed/") for p in datafeed_paths)

    # Broker module: prefix should be /broker
    broker_paths = [p for p in paths if "/broker/" in p]
    assert all(p.startswith("/api/v1/broker/") for p in broker_paths)


@pytest.mark.integration
def test_websocket_routers_module_specific(datafeed_only_app, broker_only_app) -> None:
    """Verify WebSocket routers are only loaded with their modules."""
    # Create datafeed-only app
    _, ws_apps_datafeed = datafeed_only_app
    assert len(ws_apps_datafeed) == 1, "Should have one WebSocket app for datafeed"
    datafeed_routes = [route.operation for route in ws_apps_datafeed[0].router.routes]

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
    _, ws_apps_broker = broker_only_app
    assert len(ws_apps_broker) == 1, "Should have one WebSocket app for broker"
    broker_routes = [route.operation for route in ws_apps_broker[0].router.routes]

    # Should have broker routes
    assert any("orders" in route for route in broker_routes)
    assert any("positions" in route for route in broker_routes)
    assert any("executions" in route for route in broker_routes)

    # Should NOT have datafeed routes
    assert not any("bars" in route for route in broker_routes)
    assert not any("quotes" in route for route in broker_routes)


@pytest.mark.integration
def test_module_disabled_not_instantiated(datafeed_only_app, broker_only_app) -> None:
    """Verify disabled modules don't load their routes in the app."""
    datafeed_api_app, _ = datafeed_only_app
    broker_api_app, _ = broker_only_app

    # Datafeed app should NOT have broker routes
    datafeed_paths = datafeed_api_app.openapi().get("paths", {})
    assert not any("/broker/" in p for p in datafeed_paths)
    assert any("/datafeed/" in p for p in datafeed_paths)

    # Broker app should NOT have datafeed routes
    broker_paths = broker_api_app.openapi().get("paths", {})
    assert not any("/datafeed/" in p for p in broker_paths)
    assert any("/broker/" in p for p in broker_paths)
