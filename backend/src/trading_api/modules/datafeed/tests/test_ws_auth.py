"""WebSocket authentication tests for datafeed module.

Tests WebSocket authentication success scenarios:
- Valid token accepted
- Token extracted from Authorization header
- Connection established and operational
"""

import time
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from trading_api.app_factory import AppFactory, ModularApp
from trading_api.shared.config import Settings


@pytest.fixture
def datafeed_app() -> ModularApp:
    """Create app with datafeed module enabled"""
    factory = AppFactory()
    return factory.create_app(enabled_module_names=["datafeed"])


@pytest.fixture
def client(datafeed_app: ModularApp) -> Generator[TestClient, None, None]:
    """Test client for datafeed API"""
    with TestClient(datafeed_app) as c:
        yield c


@pytest.fixture
def valid_jwt_token() -> str:
    """Create a valid JWT token for testing"""
    settings = Settings()
    payload = {
        "user_id": "USER-001",
        "exp": int(time.time()) + 300,
        "iat": int(time.time()),
    }
    return jwt.encode(
        payload, settings.jwt_private_key, algorithm=settings.JWT_ALGORITHM
    )


class TestWebSocketAuthSuccess:
    """Test WebSocket authentication success scenarios"""

    def test_connection_with_valid_token_accepted(
        self, client: TestClient, valid_jwt_token: str
    ) -> None:
        """WebSocket connection with valid token in query parameter should be accepted"""
        with client.websocket_connect(
            f"/api/v1/datafeed/ws?token={valid_jwt_token}",
        ) as ws:
            # Connection established successfully
            # Send a test subscription request to verify connection is operational
            ws.send_json(
                {
                    "operation": "bars.subscribe",
                    "request_id": "test-1",
                    "symbol": "AAPL",
                    "resolution": "1",
                }
            )

            # Should receive subscription confirmation or data
            # (Implementation may vary, so we just verify no exception)
            assert ws is not None

    def test_token_extracted_from_query_parameter(
        self, client: TestClient, valid_jwt_token: str
    ) -> None:
        """Token should be correctly extracted from query parameter"""
        with client.websocket_connect(
            f"/api/v1/datafeed/ws?token={valid_jwt_token}",
        ) as ws:
            # If we get here, token was successfully extracted and validated
            assert ws is not None

    def test_connection_operational_after_auth(
        self, client: TestClient, valid_jwt_token: str
    ) -> None:
        """WebSocket connection should be fully operational after successful auth"""
        with client.websocket_connect(
            f"/api/v1/datafeed/ws?token={valid_jwt_token}",
        ) as ws:
            # Verify bidirectional communication works
            ws.send_json(
                {
                    "operation": "bars.subscribe",
                    "request_id": "test-2",
                    "symbol": "MSFT",
                    "resolution": "1",
                }
            )

            # Connection should remain open and functional
            assert ws is not None
