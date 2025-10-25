"""
Broker service implementation for Trading Terminal

This module provides mock broker functionality for development:
- Order management (place, modify, cancel)
- Position tracking
- Execution simulation
- Account information
- FIFO event pipes for real-time updates

Event Pipes:
    The service includes asyncio.Queue instances for each business object type,
    enabling event-driven architecture for broadcasting updates to WebSocket clients
    or other consumers. These FIFO pipes ensure ordered delivery of updates:

    - bars_queue: Market bar/OHLC updates
    - quotes_queue: Real-time quote updates
    - orders_queue: Order status changes
    - positions_queue: Position updates
    - executions_queue: Trade execution events
    - equity_queue: Account equity/balance updates
    - broker_connection_queue: Broker connection status changes

Note: This is a mock implementation. In production, this would integrate
with a real broker API.
"""

import asyncio
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from trading_api.models.broker import (
    AccountMetainfo,
    Brackets,
    BrokerConnectionStatus,
    EquityData,
    Execution,
    LeverageInfo,
    LeverageInfoParams,
    LeveragePreviewResult,
    LeverageSetParams,
    LeverageSetResult,
    OrderPreviewResult,
    OrderPreviewSection,
    OrderPreviewSectionRow,
    OrderStatus,
    OrderType,
    PlacedOrder,
    PlaceOrderResult,
    Position,
    PreOrder,
    Side,
)
from trading_api.ws.router_interface import WsRouteService

logger = logging.getLogger(__name__)


class BrokerService(WsRouteService):
    """
    Mock broker service for development

    Provides broker operations and maintains FIFO event pipes for real-time updates.

    Attributes:
        _orders: Dictionary of active orders keyed by order ID
        _positions: Dictionary of open positions keyed by position ID
        _executions: List of all trade executions
        _order_counter: Counter for generating unique order IDs
        _account_id: Demo account identifier
        _account_name: Demo account display name
        _leverage_settings: Per-symbol leverage settings

    Event Pipes (FIFO Queues):
        _bars_queue: Queue[Bar] - Market bar updates
        _quotes_queue: Queue[QuoteData] - Real-time quote updates
        _orders_queue: Queue[PlacedOrder] - Order status changes
        _positions_queue: Queue[Position] - Position updates
        _executions_queue: Queue[Execution] - Trade execution events
        _equity_queue: Queue[EquityData] - Account equity/balance updates
        _broker_connection_queue: Queue[BrokerConnectionStatus] - Connection status changes

    The event pipes enable decoupled, async broadcasting of business object updates
    to WebSocket clients, background tasks, or other consumers. Updates are not yet
    automatically enqueued; integration will be added in future work.
    """

    def __init__(self) -> None:
        super().__init__()
        self._topic_queues: dict[str, asyncio.Queue] = {}
        self._orders: Dict[str, PlacedOrder] = {}
        self._positions: Dict[str, Position] = {}
        self._executions: List[Execution] = []
        self._order_counter = 1
        self._account_id = "DEMO-ACCOUNT"
        self._account_name = "Demo Trading Account"
        self._leverage_settings: Dict[str, float] = {}
        self.unrealizedPL: Dict[str, float] = {}
        self.initial_balance = 100000.0
        self._equity: EquityData = EquityData(
            equity=0.0,
            balance=100000.0,
            unrealizedPL=0.0,
            realizedPL=0.0,
        )

        # FIFO event pipes for business object updates
        # These queues enable async event-driven architecture for broadcasting
        # updates to WebSocket clients or other consumers
        self._orders_queue: asyncio.Queue[PlacedOrder] = asyncio.Queue()
        self._positions_queue: asyncio.Queue[Position] = asyncio.Queue()
        self._executions_queue: asyncio.Queue[Execution] = asyncio.Queue()
        self._equity_queue: asyncio.Queue[EquityData] = asyncio.Queue()
        self._broker_connection_queue: asyncio.Queue[
            BrokerConnectionStatus
        ] = asyncio.Queue()

    async def create_topic(self, topic: str) -> None:
        logger.info(f"Creating topic queue for: {topic}")

    def get_topic_queue(self, topic: str) -> asyncio.Queue:
        return self._topic_queues.setdefault(topic, asyncio.Queue())

    def del_topic(self, topic: str) -> None:
        self._topic_queues.pop(topic, None)

    def reset(self) -> None:
        """Reset the broker service to initial state (for testing)"""
        self._orders = {}
        self._positions = {}
        self._executions = []
        self._order_counter = 1
        self._account_id = "DEMO-ACCOUNT"
        self._account_name = "Demo Trading Account"
        self._leverage_settings = {}
        self.unrealizedPL = {}
        self.initial_balance = 100000.0
        self._equity = EquityData(
            equity=0.0,
            balance=100000.0,
            unrealizedPL=0.0,
            realizedPL=0.0,
        )

        # FIFO event pipes for business object updates
        self._orders_queue = asyncio.Queue()
        self._positions_queue = asyncio.Queue()
        self._executions_queue = asyncio.Queue()
        self._equity_queue = asyncio.Queue()
        self._broker_connection_queue = asyncio.Queue()

    # ================================ GETTERS =================================#

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

    async def preview_order(self, order: PreOrder) -> OrderPreviewResult:
        """
        Preview order costs and requirements without placing it

        Args:
            order: Order to preview

        Returns:
            OrderPreviewResult: Estimated costs, fees, and requirements
        """
        # Calculate order value and costs
        # For limit/stop orders, use specified price; for market, use last known price
        estimated_price = order.limitPrice or order.stopPrice or 100.0  # Mock price
        order_value = order.qty * estimated_price

        # Calculate mock fees (0.1% commission)
        commission = order_value * 0.001

        # Calculate margin requirement (assuming 2:1 leverage = 50% margin)
        margin_required = order_value * 0.5

        # Build preview sections
        sections = []

        # Section 1: Order Details
        order_type_map = {
            OrderType.MARKET: "Market",
            OrderType.LIMIT: "Limit",
            OrderType.STOP: "Stop",
            OrderType.STOP_LIMIT: "Stop Limit",
        }

        order_details_rows = [
            OrderPreviewSectionRow(title="Symbol", value=order.symbol),
            OrderPreviewSectionRow(
                title="Side", value="Buy" if order.side == Side.BUY else "Sell"
            ),
            OrderPreviewSectionRow(title="Quantity", value=f"{order.qty:.2f}"),
            OrderPreviewSectionRow(
                title="Order Type", value=order_type_map.get(order.type, "Unknown")
            ),
        ]

        if order.limitPrice:
            order_details_rows.append(
                OrderPreviewSectionRow(
                    title="Limit Price", value=f"${order.limitPrice:.2f}"
                )
            )
        if order.stopPrice:
            order_details_rows.append(
                OrderPreviewSectionRow(
                    title="Stop Price", value=f"${order.stopPrice:.2f}"
                )
            )

        sections.append(
            OrderPreviewSection(header="Order Details", rows=order_details_rows)
        )

        # Section 2: Cost Analysis
        cost_section = OrderPreviewSection(
            header="Cost Analysis",
            rows=[
                OrderPreviewSectionRow(
                    title="Estimated Price", value=f"${estimated_price:.2f}"
                ),
                OrderPreviewSectionRow(
                    title="Order Value", value=f"${order_value:.2f}"
                ),
                OrderPreviewSectionRow(title="Commission", value=f"${commission:.2f}"),
                OrderPreviewSectionRow(
                    title="Margin Required", value=f"${margin_required:.2f}"
                ),
                OrderPreviewSectionRow(
                    title="Total Cost", value=f"${order_value + commission:.2f}"
                ),
            ],
        )
        sections.append(cost_section)

        # Section 3: Bracket Orders (if applicable)
        if order.takeProfit or order.stopLoss or order.guaranteedStop:
            bracket_rows = []

            if order.takeProfit:
                potential_profit = abs((order.takeProfit - estimated_price) * order.qty)
                bracket_rows.append(
                    OrderPreviewSectionRow(
                        title="Take Profit",
                        value=f"${order.takeProfit:.2f} (+${potential_profit:.2f})",
                    )
                )

            if order.stopLoss:
                potential_loss = abs((order.stopLoss - estimated_price) * order.qty)
                bracket_rows.append(
                    OrderPreviewSectionRow(
                        title="Stop Loss",
                        value=f"${order.stopLoss:.2f} (-${potential_loss:.2f})",
                    )
                )

            if order.guaranteedStop:
                bracket_rows.append(
                    OrderPreviewSectionRow(
                        title="Guaranteed Stop", value=f"${order.guaranteedStop:.2f}"
                    )
                )

            if order.trailingStopPips:
                bracket_rows.append(
                    OrderPreviewSectionRow(
                        title="Trailing Stop",
                        value=f"{order.trailingStopPips:.1f} pips",
                    )
                )

            if bracket_rows:
                sections.append(
                    OrderPreviewSection(header="Risk Management", rows=bracket_rows)
                )

        # Generate unique confirmation ID
        confirm_id = str(uuid.uuid4())

        # Add warnings/validation
        warnings: list[str] = []
        errors: list[str] = []

        # Example validation: check for risky orders
        if order.type == OrderType.MARKET:
            warnings.append("Market orders execute immediately at current market price")

        if order.qty > 1000:
            warnings.append("Large order size may experience slippage")

        return OrderPreviewResult(
            sections=sections,
            confirmId=confirm_id,
            warnings=warnings if warnings else None,
            errors=errors if errors else None,
        )

    async def preview_leverage(
        self, params: LeverageSetParams
    ) -> LeveragePreviewResult:
        """
        Preview leverage changes before applying

        Args:
            params: Leverage set parameters

        Returns:
            LeveragePreviewResult: Preview messages (infos, warnings, errors)
        """
        warnings: List[str] = []
        errors: List[str] = []
        infos: List[str] = []

        # Validate range
        if params.leverage < 1.0:
            errors.append("Leverage must be at least 1.0")
        elif params.leverage > 100.0:
            errors.append("Leverage cannot exceed 100.0")
        else:
            # Calculate margin requirement
            margin_percent = 100.0 / params.leverage
            infos.append(f"Margin requirement: {margin_percent:.2f}%")

            # Add warnings for high leverage
            if params.leverage > 50:
                warnings.append(
                    f"High leverage ({params.leverage}x) significantly increases risk. "
                    "You may lose more than your initial investment."
                )
            elif params.leverage > 20:
                warnings.append(
                    f"Moderate leverage ({params.leverage}x) increases risk. "
                    "Ensure adequate risk management."
                )

            # Additional info
            if params.leverage == 1.0:
                infos.append("No leverage applied (1:1 ratio)")
            else:
                infos.append(
                    f"With {params.leverage}x leverage, a $1,000 investment "
                    f"controls ${1000 * params.leverage:.2f} in assets"
                )

        return LeveragePreviewResult(
            infos=infos if infos else None,
            warnings=warnings if warnings else None,
            errors=errors if errors else None,
        )

    async def leverage_info(self, params: LeverageInfoParams) -> LeverageInfo:
        """
        Get leverage information for symbol

        Args:
            params: Leverage info request parameters

        Returns:
            LeverageInfo: Leverage settings and constraints
        """
        # Get current leverage or default
        current_leverage = self._leverage_settings.get(params.symbol, 10.0)

        return LeverageInfo(
            title=f"Leverage for {params.symbol}",
            leverage=current_leverage,
            min=1.0,
            max=100.0,
            step=1.0,
        )

    # ================================ SETTERS =================================#
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

        if order.status not in [
            OrderStatus.WORKING,
            OrderStatus.PLACING,
            OrderStatus.FILLED,
        ]:
            raise ValueError(
                f"Cannot cancel order {order_id} with status {order.status}"
            )

        order.status = OrderStatus.CANCELED
        order.updateTime = int(time.time() * 1000)

    async def close_position(
        self, position_id: str, amount: Optional[float] = None
    ) -> None:
        """
        Close position (full or partial) by creating a closing order

        Args:
            position_id: ID of the position to close
            amount: Amount to close (if None, closes entire position)

        Raises:
            ValueError: If position not found or invalid amount
        """
        position = self._positions.get(position_id)
        if not position:
            raise ValueError(f"Position {position_id} not found")

        # Determine quantity to close
        close_qty = amount if amount is not None else position.qty

        if close_qty <= 0:
            raise ValueError("Amount must be positive")
        if close_qty > position.qty:
            raise ValueError(
                f"Amount {close_qty} exceeds position quantity {position.qty}"
            )

        # Create a closing order (opposite side of the position)
        closing_side = Side.SELL if position.side == Side.BUY else Side.BUY

        closing_order = PreOrder(
            symbol=position.symbol,
            type=OrderType.MARKET,
            side=closing_side,
            qty=close_qty,
            limitPrice=None,
            stopPrice=None,
            takeProfit=None,
            stopLoss=None,
            guaranteedStop=None,
            trailingStopPips=None,
            stopType=None,
        )

        # Place the closing order - execution will be simulated via normal flow
        await self.place_order(closing_order)

    async def edit_position_brackets(
        self,
        position_id: str,
        brackets: Brackets,
        custom_fields: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Update position brackets (stop-loss, take-profit) by creating bracket orders

        Args:
            position_id: ID of the position to modify
            brackets: New bracket values
            custom_fields: Optional custom fields

        Raises:
            ValueError: If position not found
        """
        position = self._positions.get(position_id)
        if not position:
            raise ValueError(f"Position {position_id} not found")

        # Cancel existing bracket orders for this position
        # Bracket orders are identified by symbol and opposite side
        opposite_side = Side.SELL if position.side == Side.BUY else Side.BUY
        for order_id, order in list(self._orders.items()):
            if (
                order.symbol == position.symbol
                and order.side == opposite_side
                and order.status in [OrderStatus.WORKING, OrderStatus.PLACING]
                and (order.stopPrice is not None or order.limitPrice is not None)
            ):
                order.status = OrderStatus.CANCELED
                order.updateTime = int(time.time() * 1000)

        # Create new bracket orders based on the brackets parameter
        # Stop Loss order (market order triggered at stop price)
        if brackets.stopLoss is not None:
            stop_loss_order = PreOrder(
                symbol=position.symbol,
                type=OrderType.STOP,
                side=opposite_side,
                qty=position.qty,
                limitPrice=None,
                stopPrice=brackets.stopLoss,
                takeProfit=None,
                stopLoss=None,
                guaranteedStop=None,
                trailingStopPips=None,
                stopType=None,
            )
            await self.place_order(stop_loss_order)

        # Take Profit order (limit order at take profit price)
        if brackets.takeProfit is not None:
            take_profit_order = PreOrder(
                symbol=position.symbol,
                type=OrderType.LIMIT,
                side=opposite_side,
                qty=position.qty,
                limitPrice=brackets.takeProfit,
                stopPrice=None,
                takeProfit=None,
                stopLoss=None,
                guaranteedStop=None,
                trailingStopPips=None,
                stopType=None,
            )
            await self.place_order(take_profit_order)

    async def set_leverage(self, params: LeverageSetParams) -> LeverageSetResult:
        """
        Set leverage for symbol

        Args:
            params: Leverage set parameters

        Returns:
            LeverageSetResult: Confirmed leverage value

        Raises:
            ValueError: If leverage value is out of range
        """
        # Validate leverage range
        if params.leverage < 1.0:
            raise ValueError("Leverage must be at least 1.0")
        if params.leverage > 100.0:
            raise ValueError("Leverage cannot exceed 100.0")

        # Store leverage setting
        self._leverage_settings[params.symbol] = params.leverage

        return LeverageSetResult(leverage=params.leverage)

    # ========================== EVENT PIPE METHODS ===========================

    async def executions_updates(self) -> Execution:
        update = await self._executions_queue.get()
        return update

    async def orders_updates(self) -> PlacedOrder:
        update = await self._orders_queue.get()
        return update

    async def positions_updates(self) -> Position:
        update = await self._positions_queue.get()
        return update

    async def equity_updates(self) -> EquityData:
        update = await self._equity_queue.get()
        return update

    async def broker_connection_updates(self) -> BrokerConnectionStatus:
        update = await self._broker_connection_queue.get()
        return update

    # ================================ SIMULATION =================================
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
        self._executions_queue.put_nowait(execution)

        order.status = OrderStatus.FILLED
        order.filledQty = order.qty
        order.avgPrice = execution_price
        order.updateTime = execution.time

        self._update_equity(execution)

    def _update_equity(self, execution: Execution) -> None:
        """
        Update equity after execution

        Args:
            execution: Execution that affects equity
        """
        # Calculate execution value
        current_price = execution.price
        current_position = self._positions.get(execution.symbol)
        if current_position is not None and current_position.qty > 0:
            self.unrealizedPL[execution.symbol] = (
                (current_price - current_position.avgPrice)
                * current_position.qty
                * current_position.side
            )
            self._equity.unrealizedPL = sum(self.unrealizedPL.values())
            if execution.side != current_position.side:
                self._equity.realizedPL += (
                    (current_price - current_position.avgPrice)
                    * execution.qty
                    * current_position.side
                )

        # Update balance (initial balance + realized P/L)
        self._equity.balance = self.initial_balance + self._equity.realizedPL

        # Update equity (balance + unrealized P/L)
        self._equity.equity = self._equity.balance + self._equity.unrealizedPL

        # Enqueue equity update event
        self._equity_queue.put_nowait(self._equity)

        # Update position
        self._update_position(execution)

    def _update_position(self, execution: Execution) -> None:
        """
        Update position from execution

        Args:
            execution: Execution to update position from
        """
        existing = self._positions.get(execution.symbol)

        if existing:
            total_qty = abs(
                (existing.qty * existing.side) + (execution.qty * execution.side)
            )
            total_cost = abs(
                (existing.qty * existing.avgPrice * existing.side)
                + (execution.qty * execution.price * execution.side)
            )

            total_side = (
                existing.side if existing.qty > execution.qty else execution.side
            )

            if total_qty > 0:
                existing.side = total_side
                existing.qty = total_qty
                existing.avgPrice = total_cost / total_qty
            else:
                del self._positions[execution.symbol]
        else:
            existing = self._positions[execution.symbol] = Position(
                id=execution.symbol,
                symbol=execution.symbol,
                qty=execution.qty,
                side=execution.side,
                avgPrice=execution.price,
            )
        self._positions_queue.put_nowait(existing)
        self._positions_queue.put_nowait(existing)
