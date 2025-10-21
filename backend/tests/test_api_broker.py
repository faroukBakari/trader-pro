"""
Tests for broker API endpoints
"""

import pytest
from httpx import AsyncClient

from trading_api.main import apiApp


@pytest.mark.asyncio
async def test_place_order_endpoint():
    """Test placing a new order"""
    async with AsyncClient(app=apiApp, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/broker/orders",
            json={
                "symbol": "AAPL",
                "type": 1,  # LIMIT
                "side": 1,  # BUY
                "qty": 100,
                "limitPrice": 150.0,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "orderId" in data
        assert data["orderId"].startswith("ORDER-")


@pytest.mark.asyncio
async def test_preview_order_endpoint():
    """Test previewing order costs and requirements"""
    async with AsyncClient(app=apiApp, base_url="http://test") as client:
        response = await client.post(
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
async def test_preview_market_order_warning():
    """Test that market orders get appropriate warnings"""
    async with AsyncClient(app=apiApp, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/broker/orders/preview",
            json={
                "symbol": "AAPL",
                "type": 2,  # MARKET
                "side": 1,  # BUY
                "qty": 100,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Should have warnings for market orders
        assert "warnings" in data
        assert data["warnings"] is not None
        assert any("Market orders" in warning for warning in data["warnings"])


@pytest.mark.asyncio
async def test_preview_large_order_warning():
    """Test that large orders get slippage warnings"""
    async with AsyncClient(app=apiApp, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/broker/orders/preview",
            json={
                "symbol": "AAPL",
                "type": 1,  # LIMIT
                "side": 1,  # BUY
                "qty": 2000,  # Large order
                "limitPrice": 150.0,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Should have warnings for large orders
        assert "warnings" in data
        assert data["warnings"] is not None
        assert any("slippage" in warning for warning in data["warnings"])


@pytest.mark.asyncio
async def test_get_orders_endpoint():
    """Test getting all orders"""
    async with AsyncClient(app=apiApp, base_url="http://test") as client:
        # First place an order
        await client.post(
            "/api/v1/broker/orders",
            json={
                "symbol": "AAPL",
                "type": 1,
                "side": 1,
                "qty": 100,
                "limitPrice": 150.0,
            },
        )

        # Then get all orders
        response = await client.get("/api/v1/broker/orders")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1


@pytest.mark.asyncio
async def test_modify_order_endpoint():
    """Test modifying an existing order"""
    async with AsyncClient(app=apiApp, base_url="http://test") as client:
        # First place an order
        place_response = await client.post(
            "/api/v1/broker/orders",
            json={
                "symbol": "AAPL",
                "type": 1,
                "side": 1,
                "qty": 100,
                "limitPrice": 150.0,
            },
        )
        order_id = place_response.json()["orderId"]

        # Modify the order
        response = await client.put(
            f"/api/v1/broker/orders/{order_id}",
            json={
                "symbol": "AAPL",
                "type": 1,
                "side": 1,
                "qty": 200,  # Changed quantity
                "limitPrice": 155.0,  # Changed price
            },
        )

        assert response.status_code == 200


@pytest.mark.asyncio
async def test_cancel_order_endpoint():
    """Test canceling an order"""
    async with AsyncClient(app=apiApp, base_url="http://test") as client:
        # First place an order
        place_response = await client.post(
            "/api/v1/broker/orders",
            json={
                "symbol": "AAPL",
                "type": 1,
                "side": 1,
                "qty": 100,
                "limitPrice": 150.0,
            },
        )
        order_id = place_response.json()["orderId"]

        # Cancel the order
        response = await client.delete(f"/api/v1/broker/orders/{order_id}")

        assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_positions_endpoint():
    """Test getting all positions"""
    async with AsyncClient(app=apiApp, base_url="http://test") as client:
        response = await client.get("/api/v1/broker/positions")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


@pytest.mark.asyncio
async def test_get_executions_endpoint():
    """Test getting executions for a symbol"""
    async with AsyncClient(app=apiApp, base_url="http://test") as client:
        response = await client.get("/api/v1/broker/executions/AAPL")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


@pytest.mark.asyncio
async def test_get_account_info_endpoint():
    """Test getting account information"""
    async with AsyncClient(app=apiApp, base_url="http://test") as client:
        response = await client.get("/api/v1/broker/account")

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "name" in data
