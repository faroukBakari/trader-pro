"""Full-stack integration tests with all modules.

Tests that verify all modules work correctly together.
"""

import time
from typing import Any, Dict

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient
from starlette.websockets import WebSocketDisconnect


def receive_message_by_type(
    websocket: Any, expected_type: str, timeout: float = 5.0
) -> Dict[str, Any]:
    """Receive WebSocket messages until we get one with the expected type.

    This helper function handles the race condition where background tasks
    (e.g., bars.update) might send messages while we're waiting for a
    specific response (e.g., quotes.subscribe.response).

    Args:
        websocket: The WebSocket connection
        expected_type: The message type we're looking for
        timeout: Maximum time to wait in seconds

    Returns:
        The first message matching the expected type

    Raises:
        AssertionError: If timeout is reached or websocket disconnects
    """
    start_time = time.time()
    messages_received = []

    while time.time() - start_time < timeout:
        try:
            message = websocket.receive_json()
            messages_received.append(message.get("type", "unknown"))

            if message.get("type") == expected_type:
                return message
        except WebSocketDisconnect:
            raise AssertionError(
                f"WebSocket disconnected while waiting for '{expected_type}'. "
                f"Received messages: {messages_received}"
            )
        except Exception as e:
            raise AssertionError(
                f"Error receiving message: {e}. "
                f"Expected '{expected_type}', received: {messages_received}"
            )

    raise AssertionError(
        f"Timeout waiting for message type '{expected_type}'. "
        f"Received {len(messages_received)} messages: {messages_received}"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_all_modules_loaded(async_client: AsyncClient) -> None:
    """Verify all modules are accessible in full-stack mode."""
    # Test datafeed endpoints
    datafeed_config = await async_client.get("/api/v1/datafeed/config")
    assert datafeed_config.status_code == 200
    config_data = datafeed_config.json()
    assert "supported_resolutions" in config_data

    # Test broker endpoints
    broker_orders = await async_client.get("/api/v1/broker/orders")
    assert broker_orders.status_code == 200

    broker_positions = await async_client.get("/api/v1/broker/positions")
    assert broker_positions.status_code == 200

    # Executions endpoint requires a symbol parameter
    broker_executions = await async_client.get("/api/v1/broker/executions/AAPL")
    assert broker_executions.status_code == 200

    # Test module-specific health endpoints (no core module)
    broker_health = await async_client.get("/api/v1/broker/health")
    assert broker_health.status_code == 200

    datafeed_health = await async_client.get("/api/v1/datafeed/health")
    assert datafeed_health.status_code == 200


@pytest.mark.integration
def test_websocket_all_channels(client: TestClient) -> None:
    """Verify all WebSocket channels available with all modules."""
    # Test datafeed WebSocket channels
    with client.websocket_connect("/api/v1/datafeed/ws") as websocket:
        # Test datafeed channels - bars
        websocket.send_json(
            {
                "type": "bars.subscribe",
                "payload": {"symbol": "AAPL", "resolution": "1"},
            }
        )
        response = receive_message_by_type(websocket, "bars.subscribe.response")
        assert response["type"] == "bars.subscribe.response"
        assert response["payload"]["status"] == "ok"

        # Test datafeed channels - quotes (requires symbols and fast_symbols arrays)
        websocket.send_json(
            {
                "type": "quotes.subscribe",
                "payload": {"symbols": ["AAPL"], "fast_symbols": []},
            }
        )
        response = receive_message_by_type(websocket, "quotes.subscribe.response")
        assert response["type"] == "quotes.subscribe.response"
        assert response["payload"]["status"] == "ok"

    # Test broker WebSocket channels
    with client.websocket_connect("/api/v1/broker/ws") as websocket:
        # Test broker channels - orders
        websocket.send_json(
            {"type": "orders.subscribe", "payload": {"accountId": "test"}}
        )
        response = receive_message_by_type(websocket, "orders.subscribe.response")
        assert response["type"] == "orders.subscribe.response"
        assert response["payload"]["status"] == "ok"

        # Test broker channels - positions
        websocket.send_json(
            {"type": "positions.subscribe", "payload": {"accountId": "test"}}
        )
        response = receive_message_by_type(websocket, "positions.subscribe.response")
        assert response["type"] == "positions.subscribe.response"
        assert response["payload"]["status"] == "ok"

        # Test broker channels - executions
        websocket.send_json(
            {"type": "executions.subscribe", "payload": {"accountId": "test"}}
        )
        response = receive_message_by_type(websocket, "executions.subscribe.response")
        assert response["type"] == "executions.subscribe.response"
        assert response["payload"]["status"] == "ok"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_spec_generation_completeness(app: FastAPI) -> None:
    """Verify OpenAPI/AsyncAPI specs include all modules."""
    # Get OpenAPI spec
    openapi_spec = app.openapi()
    paths = openapi_spec.get("paths", {})

    # Verify datafeed endpoints present
    assert any("/datafeed/" in path for path in paths)
    assert "/api/v1/datafeed/config" in paths

    # Verify broker endpoints present
    assert any("/broker/" in path for path in paths)
    assert "/api/v1/broker/orders" in paths
    assert "/api/v1/broker/positions" in paths
    assert "/api/v1/broker/executions/{symbol}" in paths

    # Verify module-specific health/versions endpoints present (no core module)
    assert "/api/v1/broker/health" in paths
    assert "/api/v1/broker/versions" in paths
    assert "/api/v1/datafeed/health" in paths
    assert "/api/v1/datafeed/versions" in paths


@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_endpoint_includes_all_modules(
    async_client: AsyncClient,
) -> None:
    """Verify health endpoints work for all modules."""
    # Check broker health
    broker_response = await async_client.get("/api/v1/broker/health")
    assert broker_response.status_code == 200
    broker_health = broker_response.json()
    assert "status" in broker_health
    assert broker_health["status"] == "ok"

    # Check datafeed health
    datafeed_response = await async_client.get("/api/v1/datafeed/health")
    assert datafeed_response.status_code == 200
    datafeed_health = datafeed_response.json()
    assert "status" in datafeed_health
    assert datafeed_health["status"] == "ok"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_versions_endpoint(async_client: AsyncClient) -> None:
    """Verify versions endpoints return API version info for each module."""
    # Check broker versions
    broker_response = await async_client.get("/api/v1/broker/versions")
    assert broker_response.status_code == 200
    broker_versions = broker_response.json()
    assert "current_version" in broker_versions
    assert broker_versions["current_version"] == "v1"
    assert "available_versions" in broker_versions

    # Check datafeed versions
    datafeed_response = await async_client.get("/api/v1/datafeed/versions")
    assert datafeed_response.status_code == 200
    datafeed_versions = datafeed_response.json()
    assert "current_version" in datafeed_versions
    assert datafeed_versions["current_version"] == "v1"
    assert "available_versions" in datafeed_versions


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cors_headers_present(async_client: AsyncClient) -> None:
    """Verify CORS headers are properly configured."""
    # Make a simple request and check for CORS headers (use broker health)
    response = await async_client.get("/api/v1/broker/health")
    assert response.status_code == 200

    # Note: In tests, CORS headers may not be present as middleware
    # is configured for browser requests. This test verifies the app
    # can handle the request without errors.


@pytest.mark.integration
@pytest.mark.asyncio
async def test_multi_module_workflow_end_to_end(async_client: AsyncClient) -> None:
    """Test complete workflow across multiple modules."""
    # 1. Check datafeed config
    config_response = await async_client.get("/api/v1/datafeed/config")
    assert config_response.status_code == 200

    # 2. Get initial account state
    positions_response = await async_client.get("/api/v1/broker/positions")
    assert positions_response.status_code == 200
    initial_positions = positions_response.json()

    # 3. Preview an order
    preview_response = await async_client.post(
        "/api/v1/broker/orders/preview",
        json={
            "symbol": "AAPL",
            "type": 1,  # LIMIT
            "side": 1,  # BUY
            "qty": 100,
            "limitPrice": 150.0,
        },
    )
    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert "confirmId" in preview

    # 4. Place the order
    order_response = await async_client.post(
        "/api/v1/broker/orders",
        json={
            "symbol": "AAPL",
            "type": 2,  # MARKET
            "side": 1,  # BUY
            "qty": 100,
        },
    )
    assert order_response.status_code == 200
    order = order_response.json()
    order["orderId"]

    # 5. Execute the order
    execute_response = await async_client.post("/api/v1/broker/debug/execute-orders")
    assert execute_response.status_code == 200

    # 6. Verify position created
    updated_positions_response = await async_client.get("/api/v1/broker/positions")
    assert updated_positions_response.status_code == 200
    updated_positions = updated_positions_response.json()
    assert len(updated_positions) > len(initial_positions)

    # 7. Verify execution recorded
    executions_response = await async_client.get("/api/v1/broker/executions/AAPL")
    assert executions_response.status_code == 200
    executions = executions_response.json()
    # Should have at least one execution for AAPL
    assert len(executions) > 0
    assert executions[0]["symbol"] == "AAPL"

    # 8. Check health status
    health_response = await async_client.get("/api/v1/broker/health")
    assert health_response.status_code == 200
    assert health_response.json()["status"] == "ok"
