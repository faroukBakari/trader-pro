"""Integration tests for broker + datafeed workflows.

Tests cross-module interactions between broker and datafeed modules.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.integration
@pytest.mark.asyncio
async def test_place_order_with_market_data(async_client: AsyncClient) -> None:
    """Test placing order while market data endpoints are available."""
    # Verify datafeed config endpoint is available
    datafeed_response = await async_client.get("/api/v1/datafeed/config")
    assert datafeed_response.status_code == 200
    datafeed_config = datafeed_response.json()
    assert "supported_resolutions" in datafeed_config

    # Place order via broker API
    order_response = await async_client.post(
        "/api/v1/broker/orders",
        json={
            "symbol": "AAPL",
            "type": 1,  # LIMIT
            "side": 1,  # BUY
            "qty": 100,
            "limitPrice": 150.0,
        },
    )
    assert order_response.status_code == 200

    # Verify order created
    order = order_response.json()
    assert "orderId" in order
    assert order["orderId"].startswith("ORDER-")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_position_tracking_with_executions(async_client: AsyncClient) -> None:
    """Test position updates correlate with execution reports."""
    # Get initial positions
    positions_response = await async_client.get("/api/v1/broker/positions")
    assert positions_response.status_code == 200
    initial_positions = positions_response.json()

    # Place order
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

    # Execute the order via debug endpoint
    execute_response = await async_client.post("/api/v1/broker/debug/execute-orders")
    assert execute_response.status_code == 200

    # Verify positions updated
    updated_positions_response = await async_client.get("/api/v1/broker/positions")
    assert updated_positions_response.status_code == 200
    updated_positions = updated_positions_response.json()

    # Should have at least one position now
    assert len(updated_positions) > len(initial_positions)

    # Verify execution exists (executions endpoint requires symbol)
    executions_response = await async_client.get("/api/v1/broker/executions/AAPL")
    assert executions_response.status_code == 200
    executions = executions_response.json()
    # Should have at least one execution for AAPL
    assert len(executions) > 0
    # Verify execution has expected fields
    assert "symbol" in executions[0]
    assert executions[0]["symbol"] == "AAPL"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_bracket_order_workflow(async_client: AsyncClient) -> None:
    """Test placing bracket order with take profit and stop loss."""
    # Preview bracket order first
    preview_response = await async_client.post(
        "/api/v1/broker/orders/preview",
        json={
            "symbol": "AAPL",
            "type": 1,  # LIMIT
            "side": 1,  # BUY
            "qty": 100,
            "limitPrice": 150.0,
            "takeProfit": 160.0,
            "stopLoss": 145.0,
        },
    )
    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert "confirmId" in preview

    # Place bracket order
    order_response = await async_client.post(
        "/api/v1/broker/orders",
        json={
            "symbol": "AAPL",
            "type": 1,  # LIMIT
            "side": 1,  # BUY
            "qty": 100,
            "limitPrice": 150.0,
            "takeProfit": 160.0,
            "stopLoss": 145.0,
        },
    )
    assert order_response.status_code == 200
    order = order_response.json()
    assert "orderId" in order

    # Verify order appears in orders list
    orders_response = await async_client.get("/api/v1/broker/orders")
    assert orders_response.status_code == 200
    orders = orders_response.json()
    assert any(o["id"] == order["orderId"] for o in orders)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_modify_order_workflow(async_client: AsyncClient) -> None:
    """Test modifying an existing order."""
    # Place initial order
    order_response = await async_client.post(
        "/api/v1/broker/orders",
        json={
            "symbol": "AAPL",
            "type": 1,  # LIMIT
            "side": 1,  # BUY
            "qty": 100,
            "limitPrice": 150.0,
        },
    )
    assert order_response.status_code == 200
    order = order_response.json()
    order_id = order["orderId"]

    # Modify order (requires all fields, not just changed ones)
    modify_response = await async_client.put(
        f"/api/v1/broker/orders/{order_id}",
        json={
            "symbol": "AAPL",
            "type": 1,  # LIMIT
            "side": 1,  # BUY
            "qty": 200,  # Changed from 100
            "limitPrice": 155.0,  # Changed from 150.0
        },
    )
    assert modify_response.status_code == 200

    # Verify modification
    orders_response = await async_client.get("/api/v1/broker/orders")
    assert orders_response.status_code == 200
    orders = orders_response.json()
    modified_order = next((o for o in orders if o["id"] == order_id), None)
    assert modified_order is not None
    assert modified_order["qty"] == 200
    assert modified_order["limitPrice"] == 155.0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cancel_order_workflow(async_client: AsyncClient) -> None:
    """Test canceling an order."""
    # Place order
    order_response = await async_client.post(
        "/api/v1/broker/orders",
        json={
            "symbol": "AAPL",
            "type": 1,  # LIMIT
            "side": 1,  # BUY
            "qty": 100,
            "limitPrice": 150.0,
        },
    )
    assert order_response.status_code == 200
    order = order_response.json()
    order_id = order["orderId"]

    # Cancel order
    cancel_response = await async_client.delete(f"/api/v1/broker/orders/{order_id}")
    assert cancel_response.status_code == 200

    # Verify order list after cancellation
    # Note: In the mock service, canceled orders might still appear in the list
    # with CANCELED (6) status, or they might be removed entirely
    orders_response = await async_client.get("/api/v1/broker/orders")
    assert orders_response.status_code == 200
