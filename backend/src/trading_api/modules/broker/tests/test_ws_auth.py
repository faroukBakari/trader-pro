"""WebSocket authentication tests for broker module.

Tests WebSocket authentication rejection scenarios:
- Connection without token rejected
- Invalid token rejected
- Expired token rejected
"""

import time
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from trading_api.app_factory import ModularApp
from trading_api.shared import (
    DatastoreRegistry,
    ModuleApp,
    ModuleRegistry,
    ProviderRegistry,
    settings,
)
from trading_api.shared.config import Settings


@pytest.fixture
async def broker_app() -> ModularApp:
    """Create app with broker module enabled"""
    # Create registries directly for test isolation
    modules_dir = Path(__file__).parents[2]
    providers_dir = Path(__file__).parents[3] / "providers"
    datastores_dir = Path(__file__).parents[3] / "datastores"

    module_registry = ModuleRegistry(modules_dir)
    provider_registry = ProviderRegistry(providers_dir)
    datastore_registry = DatastoreRegistry(datastores_dir)

    # Auto-discover only broker module with fakebroker provider
    module_registry.auto_discover(enabled_modules=["broker"])
    provider_registry.auto_discover(enabled_names=["fakebroker"])
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
        enabled_modules=["broker"],
        enabled_providers=["fakebroker"],
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


@pytest.fixture
def client(broker_app: ModularApp) -> Generator[TestClient, None, None]:
    """Test client for broker API"""
    with TestClient(broker_app) as c:
        yield c


@pytest.fixture
def expired_jwt_token() -> str:
    """Create an expired JWT token for testing"""
    settings = Settings()
    payload = {
        "user_id": "USER-001",
        "exp": int(time.time()) - 300,
        "iat": int(time.time()) - 600,
    }
    return jwt.encode(
        payload, settings.jwt_private_key, algorithm=settings.JWT_ALGORITHM
    )


class TestWebSocketAuthRejection:
    """Test WebSocket connection rejection scenarios"""

    def test_connection_without_token_rejected(self, client: TestClient) -> None:
        """WebSocket connection without Authorization header should be rejected"""
        with pytest.raises(Exception) as exc_info:
            with client.websocket_connect("/api/v1/broker/ws"):
                pass

        # Should raise WebSocketDisconnect or similar exception
        assert exc_info.value is not None

    def test_connection_with_invalid_token_rejected(self, client: TestClient) -> None:
        """WebSocket connection with malformed token should be rejected"""
        with pytest.raises(Exception) as exc_info:
            with client.websocket_connect(
                "/api/v1/broker/ws", headers={"Authorization": "Bearer invalid-token"}
            ):
                pass

        assert exc_info.value is not None

    def test_connection_with_expired_token_rejected(
        self, client: TestClient, expired_jwt_token: str
    ) -> None:
        """WebSocket connection with expired token should be rejected"""
        with pytest.raises(Exception) as exc_info:
            with client.websocket_connect(
                "/api/v1/broker/ws",
                headers={"Authorization": f"Bearer {expired_jwt_token}"},
            ):
                pass

        assert exc_info.value is not None
