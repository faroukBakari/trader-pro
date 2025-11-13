"""
Integration tests for broker WebSocket endpoints

Tests subscription and unsubscription flows for:
- Orders
- Positions
- Executions
- Equity
- Broker Connection

Note: Broadcast/update tests are not included as broadcasting mechanics
are not implemented yet. This tests routing endpoints only.
"""

import time

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from trading_api.shared.config import Settings


@pytest.fixture
def valid_jwt_token() -> str:
    """Generate a valid JWT token for testing"""
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


class TestOrdersWebSocket:
    """Tests for orders WebSocket endpoint"""

    def test_subscribe_to_orders(
        self, client: TestClient, valid_jwt_token: str
    ) -> None:
        """Test subscribing to order updates"""

        client.cookies.set("access_token", valid_jwt_token)
        with client.websocket_connect("/api/v1/broker/ws") as websocket:
            # Send subscribe message
            subscribe_msg = {
                "type": "orders.subscribe",
                "payload": {"accountId": "TEST-001"},
            }
            websocket.send_json(subscribe_msg)

            # Receive response
            response = websocket.receive_json()

            # Verify response structure
            assert response["type"] == "orders.subscribe.response"
            assert response["payload"]["status"] == "ok"
            assert response["payload"]["topic"] == 'orders:{"accountId":"TEST-001"}'
            assert "Subscribed" in response["payload"]["message"]

    def test_unsubscribe_from_orders(
        self, client: TestClient, valid_jwt_token: str
    ) -> None:
        """Test unsubscribing from order updates"""

        client.cookies.set("access_token", valid_jwt_token)
        with client.websocket_connect("/api/v1/broker/ws") as websocket:
            # First subscribe
            websocket.send_json(
                {"type": "orders.subscribe", "payload": {"accountId": "TEST-001"}}
            )
            subscribe_response = websocket.receive_json()
            assert subscribe_response["payload"]["status"] == "ok"

            # Then unsubscribe
            websocket.send_json(
                {"type": "orders.unsubscribe", "payload": {"accountId": "TEST-001"}}
            )
            unsubscribe_response = websocket.receive_json()

            # Verify unsubscribe response
            assert unsubscribe_response["type"] == "orders.unsubscribe.response"
            assert unsubscribe_response["payload"]["status"] == "ok"
            assert (
                unsubscribe_response["payload"]["topic"]
                == 'orders:{"accountId":"TEST-001"}'
            )
            assert "Unsubscribed" in unsubscribe_response["payload"]["message"]

    def test_subscribe_multiple_accounts(
        self, client: TestClient, valid_jwt_token: str
    ) -> None:
        """Test subscribing to orders for multiple accounts"""

        client.cookies.set("access_token", valid_jwt_token)
        with client.websocket_connect("/api/v1/broker/ws") as websocket:
            accounts = ["DEMO-001", "DEMO-002", "DEMO-003"]

            for account in accounts:
                websocket.send_json(
                    {"type": "orders.subscribe", "payload": {"accountId": account}}
                )
                response = websocket.receive_json()
                assert response["payload"]["status"] == "ok"
                assert (
                    response["payload"]["topic"]
                    == f'orders:{{"accountId":"{account}"}}'
                )


class TestPositionsWebSocket:
    """Tests for positions WebSocket endpoint"""

    def test_subscribe_to_positions(
        self, client: TestClient, valid_jwt_token: str
    ) -> None:
        """Test subscribing to position updates"""

        client.cookies.set("access_token", valid_jwt_token)
        with client.websocket_connect("/api/v1/broker/ws") as websocket:
            # Send subscribe message
            subscribe_msg = {
                "type": "positions.subscribe",
                "payload": {"accountId": "TEST-001"},
            }
            websocket.send_json(subscribe_msg)

            # Receive response
            response = websocket.receive_json()

            # Verify response structure
            assert response["type"] == "positions.subscribe.response"
            assert response["payload"]["status"] == "ok"
            assert response["payload"]["topic"] == 'positions:{"accountId":"TEST-001"}'
            assert "Subscribed" in response["payload"]["message"]

    def test_unsubscribe_from_positions(
        self, client: TestClient, valid_jwt_token: str
    ) -> None:
        """Test unsubscribing from position updates"""

        client.cookies.set("access_token", valid_jwt_token)
        with client.websocket_connect("/api/v1/broker/ws") as websocket:
            # First subscribe
            websocket.send_json(
                {"type": "positions.subscribe", "payload": {"accountId": "TEST-001"}}
            )
            subscribe_response = websocket.receive_json()
            assert subscribe_response["payload"]["status"] == "ok"

            # Then unsubscribe
            websocket.send_json(
                {"type": "positions.unsubscribe", "payload": {"accountId": "TEST-001"}}
            )
            unsubscribe_response = websocket.receive_json()

            # Verify unsubscribe response
            assert unsubscribe_response["type"] == "positions.unsubscribe.response"
            assert unsubscribe_response["payload"]["status"] == "ok"
            assert (
                unsubscribe_response["payload"]["topic"]
                == 'positions:{"accountId":"TEST-001"}'
            )
            assert "Unsubscribed" in unsubscribe_response["payload"]["message"]


class TestExecutionsWebSocket:
    """Tests for executions WebSocket endpoint"""

    def test_subscribe_to_executions(
        self, client: TestClient, valid_jwt_token: str
    ) -> None:
        """Test subscribing to execution updates"""

        client.cookies.set("access_token", valid_jwt_token)
        with client.websocket_connect("/api/v1/broker/ws") as websocket:
            # Send subscribe message
            subscribe_msg = {
                "type": "executions.subscribe",
                "payload": {"accountId": "TEST-001"},
            }
            websocket.send_json(subscribe_msg)

            # Receive response
            response = websocket.receive_json()

            # Verify response structure
            assert response["type"] == "executions.subscribe.response"
            assert response["payload"]["status"] == "ok"
            # Topic includes both accountId and symbol (empty string if not provided)
            assert '"accountId":"TEST-001"' in response["payload"]["topic"]
            assert "Subscribed" in response["payload"]["message"]

    def test_subscribe_to_executions_with_symbol_filter(
        self, client: TestClient, valid_jwt_token: str
    ) -> None:
        """Test subscribing to executions with optional symbol filter"""

        client.cookies.set("access_token", valid_jwt_token)
        with client.websocket_connect("/api/v1/broker/ws") as websocket:
            # Send subscribe message with symbol filter
            subscribe_msg = {
                "type": "executions.subscribe",
                "payload": {"accountId": "TEST-001", "symbol": "AAPL"},
            }
            websocket.send_json(subscribe_msg)

            # Receive response
            response = websocket.receive_json()

            # Verify response - topic should include the symbol in some way
            assert response["type"] == "executions.subscribe.response"
            assert response["payload"]["status"] == "ok"
            # Topic format includes the symbol parameter
            assert "TEST-001" in response["payload"]["topic"]

    def test_unsubscribe_from_executions(
        self, client: TestClient, valid_jwt_token: str
    ) -> None:
        """Test unsubscribing from execution updates"""

        client.cookies.set("access_token", valid_jwt_token)
        with client.websocket_connect("/api/v1/broker/ws") as websocket:
            # First subscribe
            websocket.send_json(
                {"type": "executions.subscribe", "payload": {"accountId": "TEST-001"}}
            )
            subscribe_response = websocket.receive_json()
            assert subscribe_response["payload"]["status"] == "ok"

            # Then unsubscribe
            websocket.send_json(
                {
                    "type": "executions.unsubscribe",
                    "payload": {"accountId": "TEST-001"},
                }
            )
            unsubscribe_response = websocket.receive_json()

            # Verify unsubscribe response
            assert unsubscribe_response["type"] == "executions.unsubscribe.response"
            assert unsubscribe_response["payload"]["status"] == "ok"
            # Topic includes both accountId and symbol
            assert '"accountId":"TEST-001"' in unsubscribe_response["payload"]["topic"]
            assert "Unsubscribed" in unsubscribe_response["payload"]["message"]


class TestEquityWebSocket:
    """Tests for equity/balance WebSocket endpoint"""

    def test_subscribe_to_equity(
        self, client: TestClient, valid_jwt_token: str
    ) -> None:
        """Test subscribing to equity updates"""

        client.cookies.set("access_token", valid_jwt_token)
        with client.websocket_connect("/api/v1/broker/ws") as websocket:
            # Send subscribe message
            subscribe_msg = {
                "type": "equity.subscribe",
                "payload": {"accountId": "TEST-001"},
            }
            websocket.send_json(subscribe_msg)

            # Receive response
            response = websocket.receive_json()

            # Verify response structure
            assert response["type"] == "equity.subscribe.response"
            assert response["payload"]["status"] == "ok"
            assert response["payload"]["topic"] == 'equity:{"accountId":"TEST-001"}'
            assert "Subscribed" in response["payload"]["message"]

    def test_unsubscribe_from_equity(
        self, client: TestClient, valid_jwt_token: str
    ) -> None:
        """Test unsubscribing from equity updates"""

        client.cookies.set("access_token", valid_jwt_token)
        with client.websocket_connect("/api/v1/broker/ws") as websocket:
            # First subscribe
            websocket.send_json(
                {"type": "equity.subscribe", "payload": {"accountId": "TEST-001"}}
            )
            subscribe_response = websocket.receive_json()
            assert subscribe_response["payload"]["status"] == "ok"

            # Then unsubscribe
            websocket.send_json(
                {"type": "equity.unsubscribe", "payload": {"accountId": "TEST-001"}}
            )
            unsubscribe_response = websocket.receive_json()

            # Verify unsubscribe response
            assert unsubscribe_response["type"] == "equity.unsubscribe.response"
            assert unsubscribe_response["payload"]["status"] == "ok"
            assert (
                unsubscribe_response["payload"]["topic"]
                == 'equity:{"accountId":"TEST-001"}'
            )
            assert "Unsubscribed" in unsubscribe_response["payload"]["message"]


class TestBrokerConnectionWebSocket:
    """Tests for broker connection status WebSocket endpoint"""

    def test_subscribe_to_broker_connection(
        self, client: TestClient, valid_jwt_token: str
    ) -> None:
        """Test subscribing to broker connection status updates"""

        client.cookies.set("access_token", valid_jwt_token)
        with client.websocket_connect("/api/v1/broker/ws") as websocket:
            # Send subscribe message
            subscribe_msg = {
                "type": "broker-connection.subscribe",
                "payload": {"accountId": "TEST-001"},
            }
            websocket.send_json(subscribe_msg)

            # Receive response
            response = websocket.receive_json()

            # Verify response structure
            assert response["type"] == "broker-connection.subscribe.response"
            assert response["payload"]["status"] == "ok"
            assert (
                response["payload"]["topic"]
                == 'broker-connection:{"accountId":"TEST-001"}'
            )
            assert "Subscribed" in response["payload"]["message"]

    def test_unsubscribe_from_broker_connection(
        self, client: TestClient, valid_jwt_token: str
    ) -> None:
        """Test unsubscribing from broker connection status updates"""

        client.cookies.set("access_token", valid_jwt_token)
        with client.websocket_connect("/api/v1/broker/ws") as websocket:
            # First subscribe
            websocket.send_json(
                {
                    "type": "broker-connection.subscribe",
                    "payload": {"accountId": "TEST-001"},
                }
            )
            subscribe_response = websocket.receive_json()
            assert subscribe_response["payload"]["status"] == "ok"

            # Then unsubscribe
            websocket.send_json(
                {
                    "type": "broker-connection.unsubscribe",
                    "payload": {"accountId": "TEST-001"},
                }
            )
            unsubscribe_response = websocket.receive_json()

            # Verify unsubscribe response
            assert (
                unsubscribe_response["type"] == "broker-connection.unsubscribe.response"
            )
            assert unsubscribe_response["payload"]["status"] == "ok"
            assert (
                unsubscribe_response["payload"]["topic"]
                == 'broker-connection:{"accountId":"TEST-001"}'
            )
            assert "Unsubscribed" in unsubscribe_response["payload"]["message"]


class TestBrokerWebSocketGeneral:
    """General tests for broker WebSocket functionality"""

    def test_websocket_connection(
        self, client: TestClient, valid_jwt_token: str
    ) -> None:
        """Test basic WebSocket connection still works with broker routes"""

        client.cookies.set("access_token", valid_jwt_token)
        with client.websocket_connect("/api/v1/broker/ws") as websocket:
            # Connection successful if we get here
            assert websocket is not None

    def test_subscribe_to_all_broker_endpoints(
        self, client: TestClient, valid_jwt_token: str
    ) -> None:
        """Test subscribing to all broker endpoints in one session"""

        client.cookies.set("access_token", valid_jwt_token)
        with client.websocket_connect("/api/v1/broker/ws") as websocket:
            endpoints = [
                "orders",
                "positions",
                "executions",
                "equity",
                "broker-connection",
            ]

            for endpoint in endpoints:
                websocket.send_json(
                    {
                        "type": f"{endpoint}.subscribe",
                        "payload": {"accountId": "TEST-ALL"},
                    }
                )
                response = websocket.receive_json()
                assert response["type"] == f"{endpoint}.subscribe.response"
                assert response["payload"]["status"] == "ok"
                # Verify topic contains both route and accountId
                assert endpoint in response["payload"]["topic"]
                assert "TEST-ALL" in response["payload"]["topic"]
