"""
Broker service implementation for Trading Terminal

This module provides mock broker functionality for development:
- Order management (place, modify, cancel)
- Position tracking
- Execution simulation
- Account information

Note: This is a mock implementation. In production, this would integrate
with a real broker API.
"""

import asyncio
import time
from typing import Dict, List

from trading_api.models.broker import (
    AccountMetainfo,
    Execution,
    OrderStatus,
    OrderType,
    PlacedOrder,
    PlaceOrderResult,
    Position,
    PreOrder,
)


class BrokerService:
    """Mock broker service for development"""

    def __init__(self) -> None:
        self._orders: Dict[str, PlacedOrder] = {}
        self._positions: Dict[str, Position] = {}
        self._executions: List[Execution] = []
        self._order_counter = 1
        self._account_id = "DEMO-ACCOUNT"
        self._account_name = "Demo Trading Account"

    async def place_order(self, order: PreOrder) -> PlaceOrderResult:
        """
        Place a new order

        Args:
            order: Order request from client

        Returns:
            PlaceOrderResult: Result containing the generated order ID
        """
        order_id = f"ORDER-{self._order_counter}"
        self._order_counter += 1

        placed_order = PlacedOrder(
            id=order_id,
            symbol=order.symbol,
            type=order.type,
            side=order.side,
            qty=order.qty,
            status=OrderStatus.WORKING,
            limitPrice=order.limitPrice,
            stopPrice=order.stopPrice,
            takeProfit=order.takeProfit,
            stopLoss=order.stopLoss,
            guaranteedStop=order.guaranteedStop,
            trailingStopPips=order.trailingStopPips,
            stopType=order.stopType,
            filledQty=0.0,
            avgPrice=None,
            updateTime=int(time.time() * 1000),
        )

        self._orders[order_id] = placed_order

        asyncio.create_task(self._simulate_execution(order_id))

        return PlaceOrderResult(orderId=order_id)

    async def modify_order(self, order_id: str, order: PreOrder) -> None:
        """
        Modify an existing order

        Args:
            order_id: ID of the order to modify
            order: Updated order details
        """
        existing_order = self._orders.get(order_id)
        if not existing_order:
            raise ValueError(f"Order {order_id} not found")

        if existing_order.status not in [OrderStatus.WORKING, OrderStatus.PLACING]:
            raise ValueError(
                f"Cannot modify order {order_id} with status {existing_order.status}"
            )

        existing_order.qty = order.qty
        existing_order.limitPrice = order.limitPrice
        existing_order.stopPrice = order.stopPrice
        existing_order.takeProfit = order.takeProfit
        existing_order.stopLoss = order.stopLoss
        existing_order.guaranteedStop = order.guaranteedStop
        existing_order.trailingStopPips = order.trailingStopPips
        existing_order.stopType = order.stopType
        existing_order.updateTime = int(time.time() * 1000)

    async def cancel_order(self, order_id: str) -> None:
        """
        Cancel an order

        Args:
            order_id: ID of the order to cancel
        """
        order = self._orders.get(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")

        if order.status not in [OrderStatus.WORKING, OrderStatus.PLACING]:
            raise ValueError(
                f"Cannot cancel order {order_id} with status {order.status}"
            )

        order.status = OrderStatus.CANCELED
        order.updateTime = int(time.time() * 1000)

    async def get_orders(self) -> List[PlacedOrder]:
        """
        Get all orders

        Returns:
            List[PlacedOrder]: List of all orders
        """
        return list(self._orders.values())

    async def get_positions(self) -> List[Position]:
        """
        Get all positions

        Returns:
            List[Position]: List of all open positions
        """
        return list(self._positions.values())

    async def get_executions(self, symbol: str) -> List[Execution]:
        """
        Get execution history for a specific symbol

        Args:
            symbol: Symbol to get executions for

        Returns:
            List[Execution]: List of trade executions for the specified symbol
        """
        return [e for e in self._executions if e.symbol == symbol]

    async def get_account_info(self) -> AccountMetainfo:
        """
        Get account metadata

        Returns:
            AccountMetainfo: Account metadata including ID and name
        """
        return AccountMetainfo(id=self._account_id, name=self._account_name)

    async def _simulate_execution(self, order_id: str) -> None:
        """
        Simulate order execution after a small delay

        Args:
            order_id: ID of the order to execute
        """
        await asyncio.sleep(0.2)

        order = self._orders.get(order_id)
        if not order or order.status != OrderStatus.WORKING:
            return

        execution_price = self._get_execution_price(order)

        execution = Execution(
            symbol=order.symbol,
            price=execution_price,
            qty=order.qty,
            side=order.side,
            time=int(time.time() * 1000),
        )
        self._executions.append(execution)

        order.status = OrderStatus.FILLED
        order.filledQty = order.qty
        order.avgPrice = execution_price
        order.updateTime = execution.time

        self._update_position(execution)

    def _get_execution_price(self, order: PlacedOrder) -> float:
        """
        Determine execution price based on order type

        Args:
            order: Order to get execution price for

        Returns:
            float: Execution price
        """
        if order.type == OrderType.MARKET:
            return 100.0
        elif order.type == OrderType.LIMIT and order.limitPrice is not None:
            return order.limitPrice
        elif order.type == OrderType.STOP and order.stopPrice is not None:
            return order.stopPrice
        elif order.type == OrderType.STOP_LIMIT:
            if order.limitPrice is not None:
                return order.limitPrice
            elif order.stopPrice is not None:
                return order.stopPrice
        return 100.0

    def _update_position(self, execution: Execution) -> None:
        """
        Update position from execution

        Args:
            execution: Execution to update position from
        """
        position_id = f"{execution.symbol}-POS"
        existing = self._positions.get(position_id)

        if existing:
            total_qty = existing.qty
            total_cost = existing.avgPrice * existing.qty

            if execution.side == existing.side:
                total_qty += execution.qty
                total_cost += execution.price * execution.qty
                existing.qty = total_qty
                existing.avgPrice = total_cost / total_qty
            else:
                if execution.qty >= existing.qty:
                    net_qty = execution.qty - existing.qty
                    if net_qty > 0:
                        existing.qty = net_qty
                        existing.side = execution.side
                        existing.avgPrice = execution.price
                    else:
                        del self._positions[position_id]
                        return
                else:
                    existing.qty -= execution.qty
        else:
            self._positions[position_id] = Position(
                id=position_id,
                symbol=execution.symbol,
                qty=execution.qty,
                side=execution.side,
                avgPrice=execution.price,
            )
