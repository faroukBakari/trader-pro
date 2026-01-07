"""WebSocket integration tests for datafeed module.

Tests WebSocket functionality:
- Authentication (cookie-based JWT)
- Bars subscription/unsubscription
- Quote subscription/unsubscription (TODO: Step 6)

Uses fixtures from conftest.py which provide mock provider.
"""

import json
import time
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from trading_api.app_factory import ModularApp
from trading_api.shared.config import Settings

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def valid_jwt_token() -> str:
    """Create a valid JWT token for WebSocket authentication."""
    settings = Settings()
    payload = {
        "user_id": "TEST-USER-001",
        "email": "test@example.com",
        "full_name": "Test User",
        "picture": "https://example.com/avatar.jpg",
        "exp": int(time.time()) + 300,
        "iat": int(time.time()),
    }
    return jwt.encode(
        payload, settings.jwt_private_key, algorithm=settings.JWT_ALGORITHM
    )


@pytest.fixture
def ws_client(apps: ModularApp) -> Generator[TestClient, None, None]:
    """Test client for WebSocket tests using mock provider from conftest."""
    with TestClient(apps) as c:
        yield c


def build_topic(topic_type: str, params: dict) -> str:
    """Build standardized topic string matching backend format."""
    serialized = json.dumps(params, sort_keys=True, separators=(",", ":"))
    return f"{topic_type}:{serialized}"


# ============================================================================
# WebSocket Authentication Tests
# ============================================================================


class TestWebSocketAuth:
    """Test WebSocket authentication scenarios."""

    def test_connection_with_valid_token_in_cookie(
        self, client: TestClient, valid_jwt_token: str
    ) -> None:
        """WebSocket connection with valid token in cookie should be accepted."""
        client.cookies.set("access_token", valid_jwt_token)

        with client.websocket_connect("/api/v1/datafeed/ws") as ws:
            # Connection established successfully if we get here
            assert ws is not None

    def test_token_extracted_from_cookie(
        self, client: TestClient, valid_jwt_token: str
    ) -> None:
        """Token should be correctly extracted from cookie."""
        client.cookies.set("access_token", valid_jwt_token)

        with client.websocket_connect("/api/v1/datafeed/ws") as ws:
            # If we get here, token was successfully extracted and validated
            assert ws is not None

    def test_connection_operational_after_auth(
        self, client: TestClient, valid_jwt_token: str
    ) -> None:
        """WebSocket connection should be fully operational after successful auth."""
        client.cookies.set("access_token", valid_jwt_token)

        with client.websocket_connect("/api/v1/datafeed/ws") as ws:
            # Verify bidirectional communication works
            ws.send_json(
                {
                    "type": "bars.subscribe",
                    "payload": {
                        "sub_id": "test-auth-check",
                        "sub_params": {"symbol": "MSFT", "resolution": "1"},
                    },
                }
            )

            response = ws.receive_json()
            assert response["type"] == "bars.subscribe.response"
            assert response["payload"]["status"] == "ok"


# ============================================================================
# Bars WebSocket Tests
# ============================================================================


class TestBarsWebSocketIntegration:
    """Integration tests for bars WebSocket endpoint."""

    def test_websocket_connection(
        self, client: TestClient, valid_jwt_token: str
    ) -> None:
        """Test basic WebSocket connection to /api/v1/datafeed/ws."""
        client.cookies.set("access_token", valid_jwt_token)

        with client.websocket_connect("/api/v1/datafeed/ws") as websocket:
            # Connection successful if we get here
            assert websocket is not None

    def test_subscribe_to_bars(self, client: TestClient, valid_jwt_token: str) -> None:
        """Test subscribing to bar updates."""
        client.cookies.set("access_token", valid_jwt_token)

        with client.websocket_connect("/api/v1/datafeed/ws") as websocket:
            # Send subscribe message (SubscriptionRequest format: sub_id + sub_params)
            subscribe_msg = {
                "type": "bars.subscribe",
                "payload": {
                    "sub_id": "test-sub-001",
                    "sub_params": {"symbol": "AAPL", "resolution": "1"},
                },
            }
            websocket.send_json(subscribe_msg)

            # Receive response
            response = websocket.receive_json()

            # Verify response structure
            assert response["type"] == "bars.subscribe.response"
            assert response["payload"]["status"] == "ok"
            assert response["payload"]["sub_id"] == "test-sub-001"
            assert (
                response["payload"]["topic"]
                == 'bars:{"resolution":"1","symbol":"AAPL"}'
            )

    def test_subscribe_with_different_resolutions(
        self, client: TestClient, valid_jwt_token: str
    ) -> None:
        """Test subscribing to different resolutions creates different topics."""
        client.cookies.set("access_token", valid_jwt_token)

        with client.websocket_connect("/api/v1/datafeed/ws") as websocket:
            # Subscribe to 1-minute bars
            websocket.send_json(
                {
                    "type": "bars.subscribe",
                    "payload": {
                        "sub_id": "test-sub-1min",
                        "sub_params": {"symbol": "AAPL", "resolution": "1"},
                    },
                }
            )
            response1 = websocket.receive_json()
            assert (
                response1["payload"]["topic"]
                == 'bars:{"resolution":"1","symbol":"AAPL"}'
            )

            # Subscribe to daily bars
            websocket.send_json(
                {
                    "type": "bars.subscribe",
                    "payload": {
                        "sub_id": "test-sub-daily",
                        "sub_params": {"symbol": "AAPL", "resolution": "1D"},
                    },
                }
            )
            response2 = websocket.receive_json()
            assert (
                response2["payload"]["topic"]
                == 'bars:{"resolution":"1D","symbol":"AAPL"}'
            )

    def test_unsubscribe_from_bars(
        self, client: TestClient, valid_jwt_token: str
    ) -> None:
        """Test unsubscribing from bar updates."""
        client.cookies.set("access_token", valid_jwt_token)

        with client.websocket_connect("/api/v1/datafeed/ws") as websocket:
            # First subscribe
            websocket.send_json(
                {
                    "type": "bars.subscribe",
                    "payload": {
                        "sub_id": "test-unsub-001",
                        "sub_params": {"symbol": "GOOGL", "resolution": "5"},
                    },
                }
            )
            subscribe_response = websocket.receive_json()
            assert subscribe_response["payload"]["status"] == "ok"

            # Then unsubscribe
            websocket.send_json(
                {
                    "type": "bars.unsubscribe",
                    "payload": {
                        "sub_id": "test-unsub-001",
                        "sub_params": {"symbol": "GOOGL", "resolution": "5"},
                    },
                }
            )
            unsubscribe_response = websocket.receive_json()

            # Verify unsubscribe response
            assert unsubscribe_response["type"] == "bars.unsubscribe.response"
            assert unsubscribe_response["payload"]["status"] == "ok"
            assert unsubscribe_response["payload"]["sub_id"] == "test-unsub-001"
            assert (
                unsubscribe_response["payload"]["topic"]
                == 'bars:{"resolution":"5","symbol":"GOOGL"}'
            )

    def test_multiple_symbols_subscription(
        self, client: TestClient, valid_jwt_token: str
    ) -> None:
        """Test subscribing to multiple symbols."""
        client.cookies.set("access_token", valid_jwt_token)

        with client.websocket_connect("/api/v1/datafeed/ws") as websocket:
            symbols = ["AAPL", "GOOGL", "MSFT"]

            for i, symbol in enumerate(symbols):
                websocket.send_json(
                    {
                        "type": "bars.subscribe",
                        "payload": {
                            "sub_id": f"test-multi-{i}",
                            "sub_params": {"symbol": symbol, "resolution": "1"},
                        },
                    }
                )
                response = websocket.receive_json()
                assert response["payload"]["status"] == "ok"
                assert (
                    response["payload"]["topic"]
                    == f'bars:{{"resolution":"1","symbol":"{symbol}"}}'
                )

    def test_subscribe_with_explicit_resolution(
        self, client: TestClient, valid_jwt_token: str
    ) -> None:
        """Test that subscribing with explicit resolution works correctly."""
        client.cookies.set("access_token", valid_jwt_token)

        with client.websocket_connect("/api/v1/datafeed/ws") as websocket:
            # Subscribe with explicit resolution
            websocket.send_json(
                {
                    "type": "bars.subscribe",
                    "payload": {
                        "sub_id": "test-explicit-res",
                        "sub_params": {"symbol": "AAPL", "resolution": "1"},
                    },
                }
            )
            response = websocket.receive_json()

            # Should create topic with resolution "1"
            assert (
                response["payload"]["topic"]
                == 'bars:{"resolution":"1","symbol":"AAPL"}'
            )


# ============================================================================
# Quotes WebSocket Tests (Step 6 - to be implemented)
# ============================================================================


class TestQuotesWebSocketIntegration:
    """Integration tests for quotes WebSocket endpoint."""

    # TODO: Step 6 - Add quote subscription tests
