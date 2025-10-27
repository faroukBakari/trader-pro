"""
Integration tests for WebSocket endpoints
"""

import json

from fastapi.testclient import TestClient

from trading_api.main import apiApp


def build_topic(symbol: str, resolution: str) -> str:
    """Build standardized topic string matching backend format"""
    params = {"resolution": resolution, "symbol": symbol}
    serialized = json.dumps(params, sort_keys=True, separators=(",", ":"))
    return f"bars:{serialized}"


class TestBarsWebSocketIntegration:
    """Integration tests for bars WebSocket endpoint"""

    def test_websocket_connection(self):
        """Test basic WebSocket connection to /api/v1/ws"""
        client = TestClient(apiApp)

        with client.websocket_connect("/api/v1/ws") as websocket:
            # Connection successful if we get here
            assert websocket is not None

    def test_subscribe_to_bars(self):
        """Test subscribing to bar updates"""
        client = TestClient(apiApp)

        with client.websocket_connect("/api/v1/ws") as websocket:
            # Send subscribe message
            subscribe_msg = {
                "type": "bars.subscribe",
                "payload": {"symbol": "AAPL", "resolution": "1"},
            }
            websocket.send_json(subscribe_msg)

            # Receive response
            response = websocket.receive_json()

            # Verify response structure
            assert response["type"] == "bars.subscribe.response"
            assert response["payload"]["status"] == "ok"
            assert (
                response["payload"]["topic"]
                == 'bars:{"resolution":"1","symbol":"AAPL"}'
            )
            assert "Subscribed" in response["payload"]["message"]

    def test_subscribe_with_different_resolutions(self):
        """Test subscribing to different resolutions creates different topics"""
        client = TestClient(apiApp)

        with client.websocket_connect("/api/v1/ws") as websocket:
            # Subscribe to 1-minute bars
            websocket.send_json(
                {
                    "type": "bars.subscribe",
                    "payload": {"symbol": "AAPL", "resolution": "1"},
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
                    "payload": {"symbol": "AAPL", "resolution": "D"},
                }
            )
            response2 = websocket.receive_json()
            assert (
                response2["payload"]["topic"]
                == 'bars:{"resolution":"D","symbol":"AAPL"}'
            )

    def test_unsubscribe_from_bars(self):
        """Test unsubscribing from bar updates"""
        client = TestClient(apiApp)

        with client.websocket_connect("/api/v1/ws") as websocket:
            # First subscribe
            websocket.send_json(
                {
                    "type": "bars.subscribe",
                    "payload": {"symbol": "GOOGL", "resolution": "5"},
                }
            )
            subscribe_response = websocket.receive_json()
            assert subscribe_response["payload"]["status"] == "ok"

            # Then unsubscribe
            websocket.send_json(
                {
                    "type": "bars.unsubscribe",
                    "payload": {"symbol": "GOOGL", "resolution": "5"},
                }
            )
            unsubscribe_response = websocket.receive_json()

            # Verify unsubscribe response
            assert unsubscribe_response["type"] == "bars.unsubscribe.response"
            assert unsubscribe_response["payload"]["status"] == "ok"
            assert (
                unsubscribe_response["payload"]["topic"]
                == 'bars:{"resolution":"5","symbol":"GOOGL"}'
            )
            assert "Unsubscribed" in unsubscribe_response["payload"]["message"]

    def test_multiple_symbols_subscription(self):
        """Test subscribing to multiple symbols"""
        client = TestClient(apiApp)

        with client.websocket_connect("/api/v1/ws") as websocket:
            symbols = ["AAPL", "GOOGL", "MSFT"]

            for symbol in symbols:
                websocket.send_json(
                    {
                        "type": "bars.subscribe",
                        "payload": {"symbol": symbol, "resolution": "1"},
                    }
                )
                response = websocket.receive_json()
                assert response["payload"]["status"] == "ok"
                assert (
                    response["payload"]["topic"]
                    == f'bars:{{"resolution":"1","symbol":"{symbol}"}}'
                )

    def test_subscribe_with_explicit_resolution(self):
        """Test that subscribing with explicit resolution works correctly"""
        client = TestClient(apiApp)

        with client.websocket_connect("/api/v1/ws") as websocket:
            # Subscribe with explicit resolution
            websocket.send_json(
                {
                    "type": "bars.subscribe",
                    "payload": {"symbol": "AAPL", "resolution": "1"},
                }
            )
            response = websocket.receive_json()

            # Should create topic with resolution "1"
            assert (
                response["payload"]["topic"]
                == 'bars:{"resolution":"1","symbol":"AAPL"}'
            )
