"""
Broker API endpoints for Trading Terminal

This module provides REST API endpoints for broker operations:
- Place, modify, and cancel orders
- Query orders, positions, and executions
- Close positions and edit position brackets
- Manage leverage settings
- Retrieve account information
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from trading_api.core.broker_service import BrokerService
from trading_api.models.broker import (
    AccountMetainfo,
    Brackets,
    Execution,
    LeverageInfo,
    LeveragePreviewResult,
    LeverageSetParams,
    LeverageSetResult,
    OrderPreviewResult,
    OrderType,
    PlacedOrder,
    PlaceOrderResult,
    Position,
    PreOrder,
    Side,
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


@router.post(
    "/orders/preview",
    response_model=OrderPreviewResult,
    summary="Preview order costs and requirements",
    operation_id="previewOrder",
)
async def previewOrder(order: PreOrder) -> OrderPreviewResult:
    """
    Preview order costs, fees, margin, and requirements without placing it.

    Args:
        order: Order to preview

    Returns:
        OrderPreviewResult: Estimated costs, fees, margin, and confirmation ID
    """
    try:
        return await broker_service.preview_order(order)
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


@router.delete(
    "/positions/{position_id}",
    response_model=SuccessResponse,
    summary="Close a position",
    operation_id="closePosition",
)
async def closePosition(
    position_id: str, amount: Optional[float] = Query(None)
) -> SuccessResponse:
    """
    Close a position (full or partial).

    This endpoint is called when the user clicks the close button on a position.
    If amount is provided, only closes that amount of the position (partial close).
    Otherwise, closes the entire position (full close).

    Args:
        position_id: ID of the position to close
        amount: Optional amount to close (if not provided, closes entire position)

    Returns:
        SuccessResponse: Success confirmation
    """
    try:
        await broker_service.close_position(position_id, amount)
        if amount:
            return SuccessResponse(
                message=f"Partially closed position {position_id} ({amount} units)"
            )
        else:
            return SuccessResponse(message=f"Closed position {position_id}")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put(
    "/positions/{position_id}/brackets",
    response_model=SuccessResponse,
    summary="Edit position brackets",
    operation_id="editPositionBrackets",
)
async def editPositionBrackets(
    position_id: str,
    brackets: Brackets,
    customFields: Optional[Dict[str, Any]] = None,
) -> SuccessResponse:
    """
    Update stop-loss and take-profit for an existing position.

    This endpoint is called when the user modifies position brackets
    (stop-loss, take-profit, guaranteed stop, trailing stop).

    Args:
        position_id: ID of the position to modify
        brackets: New bracket values
        customFields: Optional custom fields

    Returns:
        SuccessResponse: Success confirmation
    """
    try:
        await broker_service.edit_position_brackets(position_id, brackets, customFields)
        return SuccessResponse(message=f"Updated brackets for position {position_id}")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/leverage/info",
    response_model=LeverageInfo,
    summary="Get leverage information",
    operation_id="leverageInfo",
)
async def leverageInfo(
    symbol: str = Query(..., description="Symbol identifier"),
    orderType: OrderType = Query(..., description="Order type"),
    side: Side = Query(..., description="Order side (buy or sell)"),
) -> LeverageInfo:
    """
    Get leverage settings and constraints for a symbol.

    This endpoint is called to display current leverage and available
    leverage range in the leverage dialog.

    Args:
        symbol: Symbol to get leverage info for
        orderType: Type of order
        side: Order side (buy or sell)

    Returns:
        LeverageInfo: Current leverage, min, max, and step values
    """
    from trading_api.models.broker import LeverageInfoParams

    params = LeverageInfoParams(
        symbol=symbol, orderType=orderType, side=side, customFields=None
    )
    return await broker_service.leverage_info(params)


@router.put(
    "/leverage/set",
    response_model=LeverageSetResult,
    summary="Set leverage",
    operation_id="setLeverage",
)
async def setLeverage(params: LeverageSetParams) -> LeverageSetResult:
    """
    Update leverage for a symbol.

    This endpoint is called when the user confirms a leverage change.
    The leverage value should be validated and adjusted if necessary.

    Args:
        params: Leverage set parameters including symbol and new leverage value

    Returns:
        LeverageSetResult: Confirmed leverage value
    """
    try:
        return await broker_service.set_leverage(params)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/leverage/preview",
    response_model=LeveragePreviewResult,
    summary="Preview leverage changes",
    operation_id="previewLeverage",
)
async def previewLeverage(params: LeverageSetParams) -> LeveragePreviewResult:
    """
    Preview leverage changes before applying them.

    This endpoint is called to display informational messages, warnings,
    and errors about the proposed leverage change in the leverage dialog.

    Args:
        params: Leverage set parameters including proposed leverage value

    Returns:
        LeveragePreviewResult: Preview messages (infos, warnings, errors)
    """
    return await broker_service.preview_leverage(params)
