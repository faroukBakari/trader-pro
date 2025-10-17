"""
Integration tests for WebSocket endpoints
"""

import json

import pytest
from fastapi.testclient import TestClient

from trading_api.main import apiApp, wsApp
from trading_api.models import Bar, BarsSubscriptionRequest


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

    def test_subscribe_without_resolution_uses_default(self):
        """Test that subscribing without resolution parameter uses default"""
        client = TestClient(apiApp)

        with client.websocket_connect("/api/v1/ws") as websocket:
            # Subscribe without specifying resolution
            websocket.send_json(
                {"type": "bars.subscribe", "payload": {"symbol": "AAPL"}}
            )
            response = websocket.receive_json()

            # Should use default resolution "1"
            assert (
                response["payload"]["topic"]
                == 'bars:{"resolution":"1","symbol":"AAPL"}'
            )

    @pytest.mark.asyncio
    async def test_broadcast_to_subscribed_clients(self):
        """Test that broadcast sends updates to subscribed clients"""
        import time

        from trading_api.ws.datafeed import bars_topic_builder

        client = TestClient(apiApp)

        with client.websocket_connect("/api/v1/ws") as websocket:
            # Subscribe to AAPL bars
            websocket.send_json(
                {
                    "type": "bars.subscribe",
                    "payload": {"symbol": "AAPL", "resolution": "1"},
                }
            )
            subscribe_response = websocket.receive_json()
            assert subscribe_response["payload"]["status"] == "ok"

            # Broadcast a bar update
            test_bar = Bar(
                time=int(time.time() * 1000),
                open=150.0,
                high=151.0,
                low=149.5,
                close=150.5,
                volume=1000000,
            )

            await wsApp.publish(
                topic=bars_topic_builder(
                    params=BarsSubscriptionRequest(symbol="AAPL", resolution="1")
                ),
                data=test_bar,
                message_type="bars.update",
            )

            # Receive the broadcast message
            update_msg = websocket.receive_json()

            # Verify the update message
            assert update_msg["type"] == "bars.update"

            # The payload is SubscriptionUpdate with topic and payload fields
            assert "payload" in update_msg
            subscription_update = update_msg["payload"]

            # Verify SubscriptionUpdate structure
            assert subscription_update["topic"] == build_topic("AAPL", "1")
            bar_data = subscription_update["payload"]

            # Now verify the actual bar data
            assert bar_data["time"] == test_bar.time
            assert bar_data["open"] == test_bar.open
            assert bar_data["high"] == test_bar.high
            assert bar_data["low"] == test_bar.low
            assert bar_data["close"] == test_bar.close
            assert bar_data["volume"] == test_bar.volume
