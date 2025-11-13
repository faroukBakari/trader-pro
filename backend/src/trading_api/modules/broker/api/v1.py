"""
Broker API endpoints for Trading Terminal

This module provides REST API endpoints for broker operations:
- Place, modify, and cancel orders
- Query orders, positions, and executions
- Close positions and edit position brackets
- Manage leverage settings
- Retrieve account information
"""

from typing import Annotated, Any, Dict, List, Optional

from fastapi import Depends, HTTPException, Query

from trading_api.models.auth import UserData
from trading_api.models.broker import (
    AccountMetainfo,
    Brackets,
    Execution,
    LeverageInfo,
    LeverageInfoParams,
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
    SuccessResponse,
)
from trading_api.shared.api import APIRouterInterface
from trading_api.shared.middleware.auth import get_current_user

from ..service import BrokerService


class BrokerApi(APIRouterInterface):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        @self.post(
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
            self.service.reset()
            return SuccessResponse(message="Broker service state reset successfully")

        @self.post(
            "/debug/execute-orders",
            response_model=SuccessResponse,
            summary="Execute all working orders immediately (development only)",
            operation_id="executeWorkingOrders",
            include_in_schema=False,  # Hide from production docs
        )
        async def executeWorkingOrders() -> SuccessResponse:
            """
            Execute all working orders immediately for testing purposes.
            Only available in development mode for testing purposes.
            """
            await self.service.execute_all_working_orders()
            return SuccessResponse(message="All working orders executed successfully")

        @self.post(
            "/orders",
            response_model=PlaceOrderResult,
            summary="Place a new order",
            operation_id="placeOrder",
        )
        async def placeOrder(
            order: PreOrder,
            user_data: Annotated[UserData, Depends(get_current_user)],
        ) -> PlaceOrderResult:
            """
            Place a new order in the trading system.

            Requires authentication. Orders are user-scoped.

            Args:
                order: Order request with symbol, type, side, quantity, and optional prices
                user_data: Authenticated user data (injected by middleware)

            Returns:
                PlaceOrderResult: Result containing the generated order ID
            """
            try:
                return await self.service.place_order(order)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.post(
            "/orders/preview",
            response_model=OrderPreviewResult,
            summary="Preview order costs and requirements",
            operation_id="previewOrder",
        )
        async def previewOrder(
            order: PreOrder,
            user_data: Annotated[UserData, Depends(get_current_user)],
        ) -> OrderPreviewResult:
            """
            Preview order costs, fees, margin, and requirements without placing it.

            Requires authentication. Preview is user-scoped.

            Args:
                order: Order to preview
                user_data: Authenticated user data (injected by middleware)

            Returns:
                OrderPreviewResult: Estimated costs, fees, margin, and confirmation ID
            """
            try:
                return await self.service.preview_order(order)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.put(
            "/orders/{order_id}",
            response_model=SuccessResponse,
            summary="Modify an existing order",
            operation_id="modifyOrder",
        )
        async def modifyOrder(
            order_id: str,
            order: PreOrder,
            user_data: Annotated[UserData, Depends(get_current_user)],
        ) -> SuccessResponse:
            """
            Modify an existing order.

            Requires authentication. Can only modify user's own orders.

            Args:
                order_id: ID of the order to modify
                order: Updated order details
                user_data: Authenticated user data (injected by middleware)

            Returns:
                SuccessResponse: Success confirmation
            """
            try:
                await self.service.modify_order(order_id, order)
                return SuccessResponse()
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.delete(
            "/orders/{order_id}",
            response_model=SuccessResponse,
            summary="Cancel an order",
            operation_id="cancelOrder",
        )
        async def cancelOrder(
            order_id: str,
            user_data: Annotated[UserData, Depends(get_current_user)],
        ) -> SuccessResponse:
            """
            Cancel an order.

            Requires authentication. Can only cancel user's own orders.

            Args:
                order_id: ID of the order to cancel
                user_data: Authenticated user data (injected by middleware)

            Returns:
                SuccessResponse: Success confirmation
            """
            try:
                await self.service.cancel_order(order_id)
                return SuccessResponse()
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.get(
            "/orders",
            response_model=List[PlacedOrder],
            summary="Get all orders",
            operation_id="getOrders",
        )
        async def getOrders(
            user_data: Annotated[UserData, Depends(get_current_user)],
        ) -> List[PlacedOrder]:
            """
            Get all orders with their current status.

            Requires authentication. Returns only user's own orders.

            Args:
                user_data: Authenticated user data (injected by middleware)

            Returns:
                List[PlacedOrder]: List of user's orders
            """
            return await self.service.get_orders()

        @self.get(
            "/positions",
            response_model=List[Position],
            summary="Get all positions",
            operation_id="getPositions",
        )
        async def getPositions(
            user_data: Annotated[UserData, Depends(get_current_user)],
        ) -> List[Position]:
            """
            Get all open positions.

            Requires authentication. Returns only user's own positions.

            Args:
                user_data: Authenticated user data (injected by middleware)

            Returns:
                List[Position]: List of user's open positions
            """
            return await self.service.get_positions()

        @self.get(
            "/executions/{symbol}",
            response_model=List[Execution],
            summary="Get executions for a symbol",
            operation_id="getExecutions",
        )
        async def getExecutions(
            symbol: str,
            user_data: Annotated[UserData, Depends(get_current_user)],
        ) -> List[Execution]:
            """
            Get execution history for a specific symbol.

            Requires authentication. Returns only user's own executions.

            Args:
                symbol: Symbol to get executions for
                user_data: Authenticated user data (injected by middleware)

            Returns:
                List[Execution]: List of user's trade executions for the specified symbol
            """
            return await self.service.get_executions(symbol)

        @self.get(
            "/account",
            response_model=AccountMetainfo,
            summary="Get account information",
            operation_id="getAccountInfo",
        )
        async def getAccountInfo(
            user_data: Annotated[UserData, Depends(get_current_user)],
        ) -> AccountMetainfo:
            """
            Get account metadata.

            Requires authentication. Returns user's account info.

            Args:
                user_data: Authenticated user data (injected by middleware)

            Returns:
                AccountMetainfo: Account metadata including ID and name
            """
            return await self.service.get_account_info()

        @self.delete(
            "/positions/{position_id}",
            response_model=SuccessResponse,
            summary="Close a position",
            operation_id="closePosition",
        )
        async def closePosition(
            position_id: str,
            user_data: Annotated[UserData, Depends(get_current_user)],
            amount: Optional[float] = Query(None),
        ) -> SuccessResponse:
            """
            Close a position (full or partial).

            This endpoint is called when the user clicks the close button on a position.
            If amount is provided, only closes that amount of the position (partial close).
            Otherwise, closes the entire position (full close).

            Requires authentication. Can only close user's own positions.

            Args:
                position_id: ID of the position to close
                user_data: Authenticated user data (injected by middleware)
                amount: Optional amount to close (if not provided, closes entire position)

            Returns:
                SuccessResponse: Success confirmation
            """
            try:
                await self.service.close_position(position_id, amount)
                if amount:
                    return SuccessResponse(
                        message=f"Partially closed position {position_id} ({amount} units)"
                    )
                else:
                    return SuccessResponse(message=f"Closed position {position_id}")
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))

        @self.put(
            "/positions/{position_id}/brackets",
            response_model=SuccessResponse,
            summary="Edit position brackets",
            operation_id="editPositionBrackets",
        )
        async def editPositionBrackets(
            position_id: str,
            brackets: Brackets,
            user_data: Annotated[UserData, Depends(get_current_user)],
            customFields: Optional[Dict[str, Any]] = None,
        ) -> SuccessResponse:
            """
            Update stop-loss and take-profit for an existing position.

            This endpoint is called when the user modifies position brackets
            (stop-loss, take-profit, guaranteed stop, trailing stop).

            Requires authentication. Can only modify user's own positions.

            Args:
                position_id: ID of the position to modify
                brackets: New bracket values
                user_data: Authenticated user data (injected by middleware)
                customFields: Optional custom fields

            Returns:
                SuccessResponse: Success confirmation
            """
            try:
                await self.service.edit_position_brackets(
                    position_id, brackets, customFields
                )
                return SuccessResponse(
                    message=f"Updated brackets for position {position_id}"
                )
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))

        @self.get(
            "/leverage/info",
            response_model=LeverageInfo,
            summary="Get leverage information",
            operation_id="leverageInfo",
        )
        async def leverageInfo(
            user_data: Annotated[UserData, Depends(get_current_user)],
            symbol: str = Query(..., description="Symbol identifier"),
            orderType: OrderType = Query(..., description="Order type"),
            side: Side = Query(..., description="Order side (buy or sell)"),
        ) -> LeverageInfo:
            """
            Get leverage settings and constraints for a symbol.

            This endpoint is called to display current leverage and available
            leverage range in the leverage dialog.

            Requires authentication. Returns user-specific leverage settings.

            Args:
                user_data: Authenticated user data (injected by middleware)
                symbol: Symbol to get leverage info for
                orderType: Type of order
                side: Order side (buy or sell)

            Returns:
                LeverageInfo: Current leverage, min, max, and step values
            """
            params = LeverageInfoParams(
                symbol=symbol, orderType=orderType, side=side, customFields=None
            )
            return await self.service.leverage_info(params)

        @self.put(
            "/leverage/set",
            response_model=LeverageSetResult,
            summary="Set leverage",
            operation_id="setLeverage",
        )
        async def setLeverage(
            params: LeverageSetParams,
            user_data: Annotated[UserData, Depends(get_current_user)],
        ) -> LeverageSetResult:
            """
            Update leverage for a symbol.

            This endpoint is called when the user confirms a leverage change.
            The leverage value should be validated and adjusted if necessary.

            Requires authentication. Sets leverage for user's account.

            Args:
                params: Leverage set parameters including symbol and new leverage value
                user_data: Authenticated user data (injected by middleware)

            Returns:
                LeverageSetResult: Confirmed leverage value
            """
            try:
                return await self.service.set_leverage(params)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.post(
            "/leverage/preview",
            response_model=LeveragePreviewResult,
            summary="Preview leverage changes",
            operation_id="previewLeverage",
        )
        async def previewLeverage(
            params: LeverageSetParams,
            user_data: Annotated[UserData, Depends(get_current_user)],
        ) -> LeveragePreviewResult:
            """
            Preview leverage changes before applying them.

            This endpoint is called to display informational messages, warnings,
            and errors about the proposed leverage change in the leverage dialog.

            Requires authentication. Preview is user-specific.

            Args:
                params: Leverage set parameters including proposed leverage value
                user_data: Authenticated user data (injected by middleware)

            Returns:
                LeveragePreviewResult: Preview messages (infos, warnings, errors)
            """
            return await self.service.preview_leverage(params)

    @property
    def service(self) -> BrokerService:
        """Get the DatafeedService instance.

        Returns:
            DatafeedService: The datafeed service
        """
        if not isinstance(self._service, BrokerService):
            raise ValueError("Service has not been initialized")
        return self._service
