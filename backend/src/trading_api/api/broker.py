"""
Broker API endpoints for Trading Terminal

This module provides REST API endpoints for broker operations:
- Place, modify, and cancel orders
- Query orders, positions, and executions
- Retrieve account information
"""

from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from trading_api.core.broker_service import BrokerService
from trading_api.models.broker import (
    AccountMetainfo,
    Execution,
    PlacedOrder,
    PlaceOrderResult,
    Position,
    PreOrder,
)


class SuccessResponse(BaseModel):
    """Generic success response for operations that don't return data"""

    success: bool = True
    message: str = "Operation completed successfully"


router = APIRouter(prefix="/broker", tags=["broker"])

broker_service = BrokerService()


@router.post(
    "/debug/reset",
    response_model=SuccessResponse,
    summary="Reset broker service state (development only)",
    operation_id="resetBrokerState",
    include_in_schema=False,  # Hide from production docs
)
async def resetBrokerState() -> SuccessResponse:
    """
    Reset the broker service state. This clears all orders, positions, and executions.
    Only available in development mode for testing purposes.
    """
    global broker_service
    broker_service = BrokerService()
    return SuccessResponse(message="Broker service state reset successfully")


@router.post(
    "/orders",
    response_model=PlaceOrderResult,
    summary="Place a new order",
    operation_id="placeOrder",
)
async def placeOrder(order: PreOrder) -> PlaceOrderResult:
    """
    Place a new order in the trading system.

    Args:
        order: Order request with symbol, type, side, quantity, and optional prices

    Returns:
        PlaceOrderResult: Result containing the generated order ID
    """
    try:
        return await broker_service.place_order(order)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put(
    "/orders/{order_id}",
    response_model=SuccessResponse,
    summary="Modify an existing order",
    operation_id="modifyOrder",
)
async def modifyOrder(order_id: str, order: PreOrder) -> SuccessResponse:
    """
    Modify an existing order.

    Args:
        order_id: ID of the order to modify
        order: Updated order details

    Returns:
        SuccessResponse: Success confirmation
    """
    try:
        await broker_service.modify_order(order_id, order)
        return SuccessResponse()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete(
    "/orders/{order_id}",
    response_model=SuccessResponse,
    summary="Cancel an order",
    operation_id="cancelOrder",
)
async def cancelOrder(order_id: str) -> SuccessResponse:
    """
    Cancel an order.

    Args:
        order_id: ID of the order to cancel

    Returns:
        SuccessResponse: Success confirmation
    """
    try:
        await broker_service.cancel_order(order_id)
        return SuccessResponse()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/orders",
    response_model=List[PlacedOrder],
    summary="Get all orders",
    operation_id="getOrders",
)
async def getOrders() -> List[PlacedOrder]:
    """
    Get all orders with their current status.

    Returns:
        List[PlacedOrder]: List of all orders
    """
    return await broker_service.get_orders()


@router.get(
    "/positions",
    response_model=List[Position],
    summary="Get all positions",
    operation_id="getPositions",
)
async def getPositions() -> List[Position]:
    """
    Get all open positions.

    Returns:
        List[Position]: List of all open positions
    """
    return await broker_service.get_positions()


@router.get(
    "/executions/{symbol}",
    response_model=List[Execution],
    summary="Get executions for a symbol",
    operation_id="getExecutions",
)
async def getExecutions(symbol: str) -> List[Execution]:
    """
    Get execution history for a specific symbol.

    Args:
        symbol: Symbol to get executions for

    Returns:
        List[Execution]: List of trade executions for the specified symbol
    """
    return await broker_service.get_executions(symbol)


@router.get(
    "/account",
    response_model=AccountMetainfo,
    summary="Get account information",
    operation_id="getAccountInfo",
)
async def getAccountInfo() -> AccountMetainfo:
    """
    Get account metadata.

    Returns:
        AccountMetainfo: Account metadata including ID and name
    """
    return await broker_service.get_account_info()
