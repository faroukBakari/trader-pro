"""WebSocket authentication tests for broker module.

Tests WebSocket authentication rejection scenarios:
- Connection without token rejected
- Invalid token rejected
- Expired token rejected
"""

import time
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from trading_api.app_factory import AppFactory, ModularApp
from trading_api.shared.config import Settings


@pytest.fixture
def broker_app() -> ModularApp:
    """Create app with broker module enabled"""
    factory = AppFactory()
    return factory.create_app(enabled_module_names=["broker"])


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
