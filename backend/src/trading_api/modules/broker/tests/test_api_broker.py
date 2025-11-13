"""
Tests for broker API endpoints
"""

import time

import pytest
from httpx import AsyncClient
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


@pytest.fixture
def auth_cookies(valid_jwt_token: str) -> dict[str, str]:
    """Generate authentication cookies for testing"""
    return {"access_token": valid_jwt_token}


@pytest.mark.asyncio
async def test_place_order_endpoint(
    async_client: AsyncClient, auth_cookies: dict[str, str]
) -> None:
    """Test placing a new order"""
    response = await async_client.post(
        "/api/v1/broker/orders",
        json={
            "symbol": "AAPL",
            "type": 1,  # LIMIT
            "side": 1,  # BUY
            "qty": 100,
            "limitPrice": 150.0,
        },
        cookies=auth_cookies,
    )

    assert response.status_code == 200
    data = response.json()
    assert "orderId" in data
    assert data["orderId"].startswith("ORDER-")


@pytest.mark.asyncio
async def test_preview_order_endpoint(
    async_client: AsyncClient, auth_cookies: dict[str, str]
) -> None:
    """Test previewing order costs and requirements"""
    response = await async_client.post(
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
        cookies=auth_cookies,
    )

    assert response.status_code == 200
    data = response.json()

    # Validate structure
    assert "sections" in data
    assert len(data["sections"]) >= 2  # At least order details and cost
    assert "confirmId" in data
    assert data["confirmId"] is not None

    # Validate sections
    order_section = data["sections"][0]
    assert order_section["header"] == "Order Details"
    assert len(order_section["rows"]) > 0

    cost_section = data["sections"][1]
    assert cost_section["header"] == "Cost Analysis"
    assert any(row["title"] == "Commission" for row in cost_section["rows"])

    # Should have risk management section for bracket orders
    assert len(data["sections"]) >= 3
    risk_section = data["sections"][2]
    assert risk_section["header"] == "Risk Management"
    assert any(row["title"] == "Take Profit" for row in risk_section["rows"])
    assert any(row["title"] == "Stop Loss" for row in risk_section["rows"])


@pytest.mark.asyncio
async def test_preview_market_order_warning(
    async_client: AsyncClient, auth_cookies: dict[str, str]
) -> None:
    """Test that market orders get appropriate warnings"""
    response = await async_client.post(
        "/api/v1/broker/orders/preview",
        json={
            "symbol": "AAPL",
            "type": 2,  # MARKET
            "side": 1,  # BUY
            "qty": 100,
        },
        cookies=auth_cookies,
    )

    assert response.status_code == 200
    data = response.json()

    # Should have warnings for market orders
    assert "warnings" in data
    assert data["warnings"] is not None
    assert any("Market orders" in warning for warning in data["warnings"])


@pytest.mark.asyncio
async def test_preview_large_order_warning(
    async_client: AsyncClient, auth_cookies: dict[str, str]
) -> None:
    """Test that large orders get slippage warnings"""
    response = await async_client.post(
        "/api/v1/broker/orders/preview",
        json={
            "symbol": "AAPL",
            "type": 1,  # LIMIT
            "side": 1,  # BUY
            "qty": 2000,  # Large order
            "limitPrice": 150.0,
        },
        cookies=auth_cookies,
    )

    assert response.status_code == 200
    data = response.json()

    # Should have warnings for large orders
    assert "warnings" in data
    assert data["warnings"] is not None
    assert any("slippage" in warning for warning in data["warnings"])


@pytest.mark.asyncio
async def test_get_orders_endpoint(
    async_client: AsyncClient, auth_cookies: dict[str, str]
) -> None:
    """Test getting all orders"""
    # First place an order
    await async_client.post(
        "/api/v1/broker/orders",
        json={
            "symbol": "AAPL",
            "type": 1,
            "side": 1,
            "qty": 100,
            "limitPrice": 150.0,
        },
        cookies=auth_cookies,
    )

    # Then get all orders
    response = await async_client.get("/api/v1/broker/orders", cookies=auth_cookies)

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_modify_order_endpoint(
    async_client: AsyncClient, auth_cookies: dict[str, str]
) -> None:
    """Test modifying an existing order"""
    # First place an order
    place_response = await async_client.post(
        "/api/v1/broker/orders",
        json={
            "symbol": "AAPL",
            "type": 1,
            "side": 1,
            "qty": 100,
            "limitPrice": 150.0,
        },
        cookies=auth_cookies,
    )
    order_id = place_response.json()["orderId"]

    # Modify the order
    response = await async_client.put(
        f"/api/v1/broker/orders/{order_id}",
        json={
            "symbol": "AAPL",
            "type": 1,
            "side": 1,
            "qty": 200,  # Changed quantity
            "limitPrice": 155.0,  # Changed price
        },
        cookies=auth_cookies,
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_cancel_order_endpoint(
    async_client: AsyncClient, auth_cookies: dict[str, str]
) -> None:
    """Test canceling an order"""
    # First place an order
    place_response = await async_client.post(
        "/api/v1/broker/orders",
        json={
            "symbol": "AAPL",
            "type": 1,
            "side": 1,
            "qty": 100,
            "limitPrice": 150.0,
        },
        cookies=auth_cookies,
    )
    order_id = place_response.json()["orderId"]

    # Cancel the order
    response = await async_client.delete(
        f"/api/v1/broker/orders/{order_id}", cookies=auth_cookies
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_positions_endpoint(
    async_client: AsyncClient, auth_cookies: dict[str, str]
) -> None:
    """Test getting all positions"""
    response = await async_client.get("/api/v1/broker/positions", cookies=auth_cookies)

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_get_executions_endpoint(
    async_client: AsyncClient, auth_cookies: dict[str, str]
) -> None:
    """Test getting executions for a symbol"""
    response = await async_client.get(
        "/api/v1/broker/executions/AAPL", cookies=auth_cookies
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_get_account_info_endpoint(
    async_client: AsyncClient, auth_cookies: dict[str, str]
) -> None:
    """Test getting account information"""
    response = await async_client.get("/api/v1/broker/account", cookies=auth_cookies)

    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert "name" in data


@pytest.mark.asyncio
async def test_close_position_endpoint(
    async_client: AsyncClient, auth_cookies: dict[str, str]
) -> None:
    """Test closing a position (full close) - verify closing order is created"""
    # Reset broker state
    await async_client.post("/api/v1/broker/debug/reset")

    # Create a position via proper API flow (place order → execution → position)
    # Step 1: Place a BUY order
    place_response = await async_client.post(
        "/api/v1/broker/orders",
        json={
            "symbol": "AAPL",
            "type": 2,  # MARKET order (will execute immediately)
            "side": 1,  # BUY
            "qty": 100.0,
        },
        cookies=auth_cookies,
    )
    assert place_response.status_code == 200

    # Step 2: Execute the order immediately (for testing)
    execute_response = await async_client.post("/api/v1/broker/debug/execute-orders")
    assert execute_response.status_code == 200

    # Step 3: Verify position was created
    positions_response = await async_client.get(
        "/api/v1/broker/positions", cookies=auth_cookies
    )
    positions = positions_response.json()
    assert len(positions) == 1
    position = positions[0]
    position_id = position["id"]
    assert position["symbol"] == "AAPL"
    assert position["qty"] == 100.0
    assert position["side"] == 1  # BUY

    # Step 4: Close the position
    close_response = await async_client.delete(
        f"/api/v1/broker/positions/{position_id}", cookies=auth_cookies
    )
    assert close_response.status_code == 200
    data = close_response.json()
    assert data["success"] is True

    # Step 5: Verify closing order was created
    orders_response = await async_client.get(
        "/api/v1/broker/orders", cookies=auth_cookies
    )
    orders = orders_response.json()
    # Should have 2 orders: original BUY (filled) + closing SELL (working)
    assert len(orders) == 2
    closing_order = next((o for o in orders if o["side"] == -1), None)
    assert closing_order is not None
    assert closing_order["symbol"] == "AAPL"
    assert closing_order["side"] == -1  # SELL (opposite of BUY)
    assert closing_order["qty"] == 100.0
    assert closing_order["type"] == 2  # MARKET
    assert closing_order["status"] == 6  # WORKING


@pytest.mark.asyncio
async def test_close_position_partial_endpoint(
    async_client: AsyncClient, auth_cookies: dict[str, str]
) -> None:
    """Test partially closing a position - verify partial closing order is created"""
    # Reset broker state
    await async_client.post("/api/v1/broker/debug/reset")

    # Create a position via proper API flow (place order → execution → position)
    # Step 1: Place a BUY order
    place_response = await async_client.post(
        "/api/v1/broker/orders",
        json={
            "symbol": "AAPL",
            "type": 2,  # MARKET order (will execute immediately)
            "side": 1,  # BUY
            "qty": 100.0,
        },
        cookies=auth_cookies,
    )
    assert place_response.status_code == 200

    # Step 2: Execute the order immediately (for testing)
    execute_response = await async_client.post("/api/v1/broker/debug/execute-orders")
    assert execute_response.status_code == 200

    # Step 3: Verify position was created
    positions_response = await async_client.get(
        "/api/v1/broker/positions", cookies=auth_cookies
    )
    positions = positions_response.json()
    assert len(positions) == 1
    position = positions[0]
    position_id = position["id"]
    assert position["symbol"] == "AAPL"
    assert position["qty"] == 100.0
    assert position["side"] == 1  # BUY

    # Step 4: Partially close position (50 units)
    close_response = await async_client.delete(
        f"/api/v1/broker/positions/{position_id}?amount=50", cookies=auth_cookies
    )
    assert close_response.status_code == 200

    # Step 5: Verify closing order was created for partial amount
    orders_response = await async_client.get(
        "/api/v1/broker/orders", cookies=auth_cookies
    )
    orders = orders_response.json()
    # Should have 2 orders: original BUY (filled) + partial closing SELL (working)
    assert len(orders) == 2
    closing_order = next((o for o in orders if o["side"] == -1), None)
    assert closing_order is not None
    assert closing_order["symbol"] == "AAPL"
    assert closing_order["side"] == -1  # SELL (opposite of BUY)
    assert closing_order["qty"] == 50.0  # Partial close amount
    assert closing_order["type"] == 2  # MARKET
    assert closing_order["status"] == 6  # WORKING


@pytest.mark.asyncio
async def test_edit_position_brackets_endpoint(
    async_client: AsyncClient, auth_cookies: dict[str, str]
) -> None:
    """Test editing position brackets (stop-loss, take-profit) - verify bracket orders are created"""
    # Reset broker state
    await async_client.post("/api/v1/broker/debug/reset")

    # Create a position via proper API flow (place order → execution → position)
    # Step 1: Place a BUY order
    place_response = await async_client.post(
        "/api/v1/broker/orders",
        json={
            "symbol": "AAPL",
            "type": 2,  # MARKET order (will execute immediately)
            "side": 1,  # BUY
            "qty": 100.0,
        },
        cookies=auth_cookies,
    )
    assert place_response.status_code == 200

    # Step 2: Execute the order immediately (for testing)
    execute_response = await async_client.post("/api/v1/broker/debug/execute-orders")
    assert execute_response.status_code == 200

    # Step 3: Verify position was created
    positions_response = await async_client.get(
        "/api/v1/broker/positions", cookies=auth_cookies
    )
    positions = positions_response.json()
    assert len(positions) == 1
    position = positions[0]
    position_id = position["id"]
    assert position["symbol"] == "AAPL"
    assert position["qty"] == 100.0
    assert position["side"] == 1  # BUY

    # Step 4: Edit position brackets
    brackets_response = await async_client.put(
        f"/api/v1/broker/positions/{position_id}/brackets",
        json={
            "brackets": {
                "stopLoss": 90.0,
                "takeProfit": 110.0,
                "trailingStopPips": 5.0,
            },
            "customFields": None,
        },
        cookies=auth_cookies,
    )
    assert brackets_response.status_code == 200
    data = brackets_response.json()
    assert data["success"] is True

    # Step 5: Verify bracket orders were created
    orders_response = await async_client.get(
        "/api/v1/broker/orders", cookies=auth_cookies
    )
    orders = orders_response.json()
    # Should have 3 orders: original BUY (filled) + 2 bracket orders (stop loss + take profit)
    assert len(orders) == 3

    # Filter to bracket orders only (exclude filled BUY order)
    bracket_orders = [o for o in orders if o["status"] == 6]  # WORKING status
    assert len(bracket_orders) == 2

    # Find stop loss order (STOP type with stopPrice)
    stop_loss_order = next(
        (o for o in bracket_orders if o["type"] == 3 and o["stopPrice"] == 90.0),
        None,
    )
    assert stop_loss_order is not None
    assert stop_loss_order["symbol"] == "AAPL"
    assert stop_loss_order["side"] == -1  # SELL (opposite of position)
    assert stop_loss_order["qty"] == 100.0
    assert stop_loss_order["status"] == 6  # WORKING

    # Find take profit order (LIMIT type with limitPrice)
    take_profit_order = next(
        (o for o in bracket_orders if o["type"] == 1 and o["limitPrice"] == 110.0),
        None,
    )
    assert take_profit_order is not None
    assert take_profit_order["symbol"] == "AAPL"
    assert take_profit_order["side"] == -1  # SELL (opposite of position)
    assert take_profit_order["qty"] == 100.0
    assert take_profit_order["status"] == 6  # WORKING


@pytest.mark.asyncio
async def test_leverage_info_endpoint(
    async_client: AsyncClient, auth_cookies: dict[str, str]
) -> None:
    """Test getting leverage information for a symbol"""
    response = await async_client.get(
        "/api/v1/broker/leverage/info",
        params={"symbol": "AAPL", "orderType": 1, "side": 1},
        cookies=auth_cookies,
    )

    assert response.status_code == 200
    data = response.json()
    assert "title" in data
    assert "leverage" in data
    assert "min" in data
    assert "max" in data
    assert "step" in data
    assert data["leverage"] == 10.0  # Default leverage
    assert data["min"] == 1.0
    assert data["max"] == 100.0
    assert data["step"] == 1.0


@pytest.mark.asyncio
async def test_set_leverage_endpoint(
    async_client: AsyncClient, auth_cookies: dict[str, str]
) -> None:
    """Test setting leverage for a symbol"""
    response = await async_client.put(
        "/api/v1/broker/leverage/set",
        json={
            "symbol": "AAPL",
            "orderType": 1,
            "side": 1,
            "leverage": 20.0,
            "customFields": None,
        },
        cookies=auth_cookies,
    )

    assert response.status_code == 200
    data = response.json()
    assert "leverage" in data
    assert data["leverage"] == 20.0

    # Verify leverage was persisted
    info_response = await async_client.get(
        "/api/v1/broker/leverage/info",
        params={"symbol": "AAPL", "orderType": 1, "side": 1},
        cookies=auth_cookies,
    )
    info_data = info_response.json()
    assert info_data["leverage"] == 20.0


@pytest.mark.asyncio
async def test_set_leverage_invalid_range_endpoint(
    async_client: AsyncClient, auth_cookies: dict[str, str]
) -> None:
    """Test setting leverage with invalid value"""
    # Test leverage too high
    response = await async_client.put(
        "/api/v1/broker/leverage/set",
        json={
            "symbol": "AAPL",
            "orderType": 1,
            "side": 1,
            "leverage": 150.0,
            "customFields": None,
        },
        cookies=auth_cookies,
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_preview_leverage_endpoint(
    async_client: AsyncClient, auth_cookies: dict[str, str]
) -> None:
    """Test previewing leverage changes"""
    # Test moderate leverage
    response = await async_client.post(
        "/api/v1/broker/leverage/preview",
        json={
            "symbol": "AAPL",
            "orderType": 1,
            "side": 1,
            "leverage": 25.0,
            "customFields": None,
        },
        cookies=auth_cookies,
    )

    assert response.status_code == 200
    data = response.json()
    assert "infos" in data or data.get("infos") is None
    assert "warnings" in data or data.get("warnings") is None
    assert "errors" in data or data.get("errors") is None

    # Should have info about margin requirement
    if data.get("infos"):
        assert any("Margin requirement" in info for info in data["infos"])

    # Should have warning about moderate leverage
    if data.get("warnings"):
        assert any("leverage" in warning.lower() for warning in data["warnings"])


@pytest.mark.asyncio
async def test_preview_leverage_high_leverage_warning(
    async_client: AsyncClient, auth_cookies: dict[str, str]
) -> None:
    """Test leverage preview shows warning for high leverage"""
    response = await async_client.post(
        "/api/v1/broker/leverage/preview",
        json={
            "symbol": "AAPL",
            "orderType": 1,
            "side": 1,
            "leverage": 75.0,
            "customFields": None,
        },
        cookies=auth_cookies,
    )

    assert response.status_code == 200
    data = response.json()
    assert data.get("warnings") is not None
    assert any("High leverage" in warning for warning in data["warnings"])


@pytest.mark.asyncio
async def test_preview_leverage_invalid_range(
    async_client: AsyncClient, auth_cookies: dict[str, str]
) -> None:
    """Test leverage preview shows error for invalid range"""
    response = await async_client.post(
        "/api/v1/broker/leverage/preview",
        json={
            "symbol": "AAPL",
            "orderType": 1,
            "side": 1,
            "leverage": 150.0,
            "customFields": None,
        },
        cookies=auth_cookies,
    )

    assert response.status_code == 200
    data = response.json()
    assert data.get("errors") is not None
    assert any("cannot exceed" in error.lower() for error in data["errors"])
    assert any("cannot exceed" in error.lower() for error in data["errors"])
