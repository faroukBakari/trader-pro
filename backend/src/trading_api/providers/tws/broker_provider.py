"""FakeBrokerProvider - Mock broker for development and testing.

Implements BrokerCapability with in-memory state and simulated execution.
All business logic (orders, positions, P&L) is encapsulated here.
"""

import asyncio
import logging
import os
import random
import time
import uuid
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Awaitable, Callable
from zoneinfo import ZoneInfo

from ibapi.contract import Contract
from ibapi.order import Order

from trading_api.capabilities.broker import BrokerCapability
from trading_api.models.broker import (
    AccountMetainfo,
    Brackets,
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
from trading_api.models.common import CapabilitySpec
from trading_api.models.exceptions import ProviderException, TradingApiException
from trading_api.models.providers.tws_configs import TWSBrokerProviderConfig
from trading_api.providers.tws.order_tracker import TrackedOrder
from trading_api.providers.tws.tws_connection import TWSClient
from trading_api.providers.tws.tws_mappers import (
    preorder_to_tws,
    tracked_order_to_placed_order,
)
from trading_api.shared import Provider

logger = logging.getLogger(__name__)
us_eastern = ZoneInfo("US/Eastern")
DEBUG_TWS_BROKER = os.environ.get("DEBUG_TWS_BROKER") == "true"


class TWSBrokerProvider(Provider, BrokerCapability):
    """Mock broker provider - simulates order execution and account management.

    [IN-MEMORY]: All state stored in dictionaries (orders, positions, executions).
    [CALLBACK-BASED]: Streaming uses registered callbacks, no queues.
    [SINGLE-TASK]: One execution simulator loop triggers all update cascades.
    """

    def __init__(self, config: TWSBrokerProviderConfig | None = None) -> None:
        """Initialize FakeBrokerProvider.

        Args:
            config: Provider configuration (auto-loaded from env if None)
        """
        self._config = config or TWSBrokerProviderConfig()

        # Layer 2: TWSClient with separate client_id
        self._tws_client = TWSClient(
            self._config.host, self._config.port, self._config.client_id
        )

        # Business state (in-memory)
        self._orders: dict[str, PlacedOrder] = {}
        self._positions: dict[str, Position] = {}
        self._executions: list[Execution] = []
        self._order_counter = 1
        self._leverage_settings: dict[str, float] = {}

        # P&L tracking
        self._unrealized_pl: dict[str, float] = {}
        self._equity = EquityData(
            equity=100000.0,
            balance=100000.0,
            unrealizedPL=0.0,
            realizedPL=0.0,
        )

        # Subscription management
        self._subscription_counter = 0
        self._order_callbacks: dict[str, Callable[[PlacedOrder], Awaitable[None]]] = {}
        self._position_callbacks: dict[str, Callable[[Position], Awaitable[None]]] = {}
        self._execution_callbacks: dict[
            str, tuple[str, Callable[[Execution], Awaitable[None]]]
        ] = {}  # sub_id → (symbol, callback)
        self._equity_callbacks: dict[str, Callable[[EquityData], Awaitable[None]]] = {}

        # Error callbacks (one per subscription)
        self._error_callbacks: dict[
            str, Callable[[TradingApiException], Awaitable[None]]
        ] = {}

        # Execution simulator task
        self._execution_simulator_task: asyncio.Task | None = None

        # Shutdown event
        self._shutdown_event = asyncio.Event()

    # =========================================================================
    # Provider Protocol Implementation
    # =========================================================================

    @classmethod
    def provider_dir(cls) -> Path:
        """Return provider directory path."""
        return Path(__file__).parent

    @classmethod
    def capabilities(cls) -> list[CapabilitySpec]:
        """Return capabilities provided by this provider."""
        return [CapabilitySpec(name="broker")]

    @property
    def config(self) -> TWSBrokerProviderConfig:
        """Return provider configuration."""
        return self._config

    # =========================================================================
    # BrokerCapability - Snapshot Methods (async)
    # =========================================================================

    def _select_preferred_exchange(self) -> str:
        """Select preferred exchange based on current time.

        Returns OVERNIGHT during extended hours (8PM-4AM US/Eastern on weekdays),
        otherwise SMART for regular market hours routing.
        """
        now_us_eastern = datetime.now(us_eastern)
        is_weekday = now_us_eastern.weekday() < 5
        current_time = now_us_eastern.time()
        after_8pm = current_time >= datetime.strptime("20:00:00", "%H:%M:%S").time()
        before_4am = current_time < datetime.strptime("4:00:00", "%H:%M:%S").time()

        if is_weekday and (after_8pm or before_4am):
            return "OVERNIGHT"
        return "SMART"

    async def _submit_order(
        self, order: PreOrder, order_id: int | None = None
    ) -> tuple[TrackedOrder, list[TrackedOrder]]:
        """Execute order placement or modification via TWS.

        Shared logic for place_order and modify_order:
        1. Select exchange based on time (OVERNIGHT vs SMART)
        2. Qualify contract with TWS
        3. Convert PreOrder to TWS Order objects (with optional brackets)
        4. Submit via placeOrderGroup

        Args:
            order: PreOrder with order details and optional brackets
            order_id: None for new orders, existing ID for modifications

        Returns:
            Tuple of (parent_tracked_order, child_tracked_orders)
        """
        preferred_exchange = self._select_preferred_exchange()

        qualified = await self._tws_client.qualify_contract(
            order.symbol, [preferred_exchange]
        )

        contract: Contract | None = getattr(
            next(iter(qualified), None), "contract", None
        )

        assert (
            contract is not None and contract.conId > 0
        ), f"Contract not found for symbol {order.symbol}"

        # Convert domain order to TWS types (may return multiple orders for brackets)
        # Empty account string is valid for single-account users
        # order_id=-1 means new order, >0 means modify existing
        parent_order, stop_loss_order, take_profit_order = preorder_to_tws(
            order, "", order_id if order_id is not None else -1
        )

        childs_to_place = [
            o for o in [stop_loss_order, take_profit_order] if o is not None
        ]

        return await self._tws_client.placeOrderGroup(
            contract, parent_order, childs_to_place
        )

    async def place_order(self, order: PreOrder) -> PlaceOrderResult:
        """Place a new order (with optional bracket orders).

        Supports bracket orders (stopLoss, takeProfit, trailingStopPips) by placing
        multiple linked orders via TWS parent/child mechanism with OCA grouping.

        Args:
            order: PreOrder from TradingView containing order details and optional brackets

        Returns:
            PlaceOrderResult with parent order ID
        """
        main_order, _ = await self._submit_order(order)
        return PlaceOrderResult(orderId=str(main_order.orderId))

    async def modify_order(self, order_id: str, order: PreOrder) -> None:
        """Modify an existing order (price, quantity, or bracket parameters).

        Re-submits the order with the same order ID, updating TWS in-place.
        For bracket modifications, new child orders are created with OCA linkage.

        Args:
            order_id: Existing order ID to modify
            order: Updated PreOrder with new parameters (price, qty, brackets)
        """
        await self._submit_order(order, int(order_id))

    async def cancel_order(self, order_id: str) -> None:
        """Cancel an order."""
        await self._tws_client.cancelOrder(int(order_id))

    async def close_position(
        self, position_id: str, amount: float | None = None
    ) -> None:
        """Close position (full or partial)."""
        position = self._positions.get(position_id)
        if not position:
            raise ProviderException(
                code="PROVIDER_BROKER_POSITION_NOT_FOUND",
                message=f"Position {position_id} not found",
                provider="tws",
                capability="broker",
            )

        close_qty = amount if amount is not None else position.qty

        if close_qty <= 0:
            raise ProviderException(
                code="PROVIDER_BROKER_INVALID_AMOUNT",
                message="Amount must be positive",
                provider="tws",
                capability="broker",
            )
        if close_qty > position.qty:
            raise ProviderException(
                code="PROVIDER_BROKER_INVALID_AMOUNT",
                message=f"Amount {close_qty} exceeds position quantity {position.qty}",
                provider="tws",
                capability="broker",
            )

        # Create closing order (opposite side)
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
            seenPrice=None,
            currentQuotes=None,
        )

        await self.place_order(closing_order)

    async def edit_position_brackets(
        self,
        position_id: str,
        brackets: Brackets,
    ) -> None:
        """Update position brackets (stop-loss, take-profit) using OCA groups.

        Creates bracket orders linked via OCA (One-Cancels-All) so when one
        fills, TWS automatically cancels the others - preventing double execution.

        Args:
            position_id: Position to attach brackets to
            brackets: Bracket configuration (stopLoss, takeProfit, trailingStopPips)
        """
        position = self._positions.get(position_id)
        if not position:
            raise ProviderException(
                code="PROVIDER_BROKER_POSITION_NOT_FOUND",
                message=f"Position {position_id} not found",
                provider="tws",
                capability="broker",
            )

        # Build list of bracket orders to place
        bracket_orders: list[Order] = []
        tws_action = "SELL" if position.side == Side.BUY else "BUY"

        # Trailing stop or regular stop loss
        if brackets.trailingStopPips is not None:
            trailing_order = Order()
            trailing_order.action = tws_action
            trailing_order.totalQuantity = Decimal(str(position.qty))
            trailing_order.orderType = "TRAIL"
            trailing_order.auxPrice = brackets.trailingStopPips  # Trail amount
            if brackets.stopLoss is not None:
                trailing_order.trailStopPrice = brackets.stopLoss  # Initial trigger
            trailing_order.tif = "GTC"
            bracket_orders.append(trailing_order)
        elif brackets.stopLoss is not None:
            stop_order = Order()
            stop_order.action = tws_action
            stop_order.totalQuantity = Decimal(str(position.qty))
            stop_order.orderType = "STP"
            stop_order.auxPrice = brackets.stopLoss
            stop_order.tif = "GTC"
            bracket_orders.append(stop_order)

        # Take profit limit order
        if brackets.takeProfit is not None:
            tp_order = Order()
            tp_order.action = tws_action
            tp_order.totalQuantity = Decimal(str(position.qty))
            tp_order.orderType = "LMT"
            tp_order.lmtPrice = brackets.takeProfit
            tp_order.tif = "GTC"
            bracket_orders.append(tp_order)

        # If no bracket orders to place, we're done (just cancelled existing)
        if not bracket_orders:
            return

        # Qualify contract for this position's symbol
        preferred_exchange = self._select_preferred_exchange()
        qualified = await self._tws_client.qualify_contract(
            position.symbol, [preferred_exchange]
        )
        contract: Contract | None = getattr(
            next(iter(qualified), None), "contract", None
        )
        if contract is None or contract.conId <= 0:
            raise ProviderException(
                code="PROVIDER_BROKER_CONTRACT_NOT_FOUND",
                message=f"Contract not found for symbol {position.symbol}",
                provider="tws",
                capability="broker",
            )

        # Generate unique OCA group name for this position's brackets
        oca_group = f"bracket_{position_id}"

        # Place all bracket orders via OCA group (atomic submission)
        await self._tws_client.placeOcaGroup(
            contract,
            bracket_orders,
            oca_group,
            oca_type=1,  # CANCEL_WITH_BLOCK (overfill protection)
        )

    async def get_orders(self) -> list[PlacedOrder]:
        """Get all open orders from TWS.

        Requests all open orders and converts them to domain PlacedOrder models.
        Returns completed snapshot when all orders have been received.
        """
        # Request open orders from TWS (returns list of TrackedOrder objects)
        tws_orders = await self._tws_client.reqOpenOrders()

        # Convert each TrackedOrder to domain PlacedOrder
        return [tracked_order_to_placed_order(tracked) for tracked in tws_orders]

    async def get_positions(self) -> list[Position]:
        """Get all open positions."""
        return list(self._positions.values())

    async def get_executions(self, symbol: str) -> list[Execution]:
        """Get execution history for a symbol."""
        return [e for e in self._executions if e.symbol == symbol]

    async def get_account_info(self) -> AccountMetainfo:
        """Get account metadata."""
        return AccountMetainfo(
            id="NOT-IMPLEMENTED",
            name="NOT-IMPLEMENTED",
        )

    async def get_equity(self) -> EquityData:
        """Get current equity data."""
        return self._equity

    async def preview_order(self, order: PreOrder) -> OrderPreviewResult:
        """Preview order costs and requirements."""
        estimated_price = order.limitPrice or order.stopPrice or 100.0
        order_value = order.qty * estimated_price
        commission = order_value * 0.001  # 0.1% commission
        margin_required = order_value * 0.5  # 50% margin (2:1 leverage)

        sections = []

        # Order Details section
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

        # Cost Analysis section
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

        # Risk Management section (if brackets)
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

        confirm_id = str(uuid.uuid4())

        warnings: list[str] = []
        if order.type == OrderType.MARKET:
            warnings.append("Market orders execute immediately at current market price")
        if order.qty > 1000:
            warnings.append("Large order size may experience slippage")

        return OrderPreviewResult(
            sections=sections,
            confirmId=confirm_id,
            warnings=warnings if warnings else None,
            errors=None,
        )

    async def preview_leverage(
        self, params: LeverageSetParams
    ) -> LeveragePreviewResult:
        """Preview leverage changes."""
        warnings: list[str] = []
        errors: list[str] = []
        infos: list[str] = []

        if params.leverage < 1.0:
            errors.append("Leverage must be at least 1.0")
        elif params.leverage > 100.0:
            errors.append("Leverage cannot exceed 100.0")
        else:
            margin_percent = 100.0 / params.leverage
            infos.append(f"Margin requirement: {margin_percent:.2f}%")

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

    async def get_leverage_info(self, params: LeverageInfoParams) -> LeverageInfo:
        """Get leverage information for symbol."""
        current_leverage = self._leverage_settings.get(params.symbol, 10.0)

        return LeverageInfo(
            title=f"Leverage for {params.symbol}",
            leverage=current_leverage,
            min=1.0,
            max=100.0,
            step=1.0,
        )

    async def set_leverage(self, params: LeverageSetParams) -> LeverageSetResult:
        """Set leverage for symbol."""
        if params.leverage < 1.0:
            raise ProviderException(
                code="PROVIDER_BROKER_INVALID_LEVERAGE",
                message="Leverage must be at least 1.0",
                provider="fakebroker",
                capability="broker",
            )
        if params.leverage > 100.0:
            raise ProviderException(
                code="PROVIDER_BROKER_INVALID_LEVERAGE",
                message="Leverage cannot exceed 100.0",
                provider="fakebroker",
                capability="broker",
            )

        self._leverage_settings[params.symbol] = params.leverage
        return LeverageSetResult(leverage=params.leverage)

    # =========================================================================
    # BrokerCapability - Streaming Methods (callback-based)
    # =========================================================================

    def _generate_subscription_id(self) -> str:
        """Generate unique subscription ID."""
        self._subscription_counter += 1
        return f"sub-{self._subscription_counter}"

    def _start_execution_simulator_if_needed(self) -> None:
        """Start execution simulator if not running and has subscribers."""
        has_subscribers = (
            len(self._order_callbacks) > 0
            or len(self._position_callbacks) > 0
            or len(self._execution_callbacks) > 0
            or len(self._equity_callbacks) > 0
        )

        if self._execution_simulator_task is None and has_subscribers:
            logger.info("Starting execution simulator task")
            self._execution_simulator_task = asyncio.create_task(
                self._execution_simulator()
            )

    def _stop_execution_simulator_if_empty(self) -> None:
        """Stop execution simulator if no more subscribers."""
        has_subscribers = (
            len(self._order_callbacks) > 0
            or len(self._position_callbacks) > 0
            or len(self._execution_callbacks) > 0
            or len(self._equity_callbacks) > 0
        )

        if self._execution_simulator_task is not None and not has_subscribers:
            logger.info("Stopping execution simulator task (no subscribers)")
            self._execution_simulator_task.cancel()
            self._execution_simulator_task = None

    def subscribe_orders(
        self,
        callback: Callable[[PlacedOrder], Awaitable[None]],
        on_error: Callable[[TradingApiException], Awaitable[None]] | None = None,
    ) -> str:
        """Subscribe to order updates."""
        sub_id = self._generate_subscription_id()
        self._order_callbacks[sub_id] = callback
        if on_error:
            self._error_callbacks[sub_id] = on_error

        logger.info(f"Registered order subscription: {sub_id}")
        self._start_execution_simulator_if_needed()

        return sub_id

    def subscribe_positions(
        self,
        callback: Callable[[Position], Awaitable[None]],
        on_error: Callable[[TradingApiException], Awaitable[None]] | None = None,
    ) -> str:
        """Subscribe to position updates."""
        sub_id = self._generate_subscription_id()
        self._position_callbacks[sub_id] = callback
        if on_error:
            self._error_callbacks[sub_id] = on_error

        logger.info(f"Registered position subscription: {sub_id}")
        self._start_execution_simulator_if_needed()

        return sub_id

    def subscribe_executions(
        self,
        symbol: str,
        callback: Callable[[Execution], Awaitable[None]],
        on_error: Callable[[TradingApiException], Awaitable[None]] | None = None,
    ) -> str:
        """Subscribe to execution updates for a symbol."""
        sub_id = self._generate_subscription_id()
        self._execution_callbacks[sub_id] = (symbol, callback)
        if on_error:
            self._error_callbacks[sub_id] = on_error

        logger.info(f"Registered execution subscription for {symbol}: {sub_id}")
        self._start_execution_simulator_if_needed()

        return sub_id

    def subscribe_equity(
        self,
        callback: Callable[[EquityData], Awaitable[None]],
        on_error: Callable[[TradingApiException], Awaitable[None]] | None = None,
    ) -> str:
        """Subscribe to equity updates."""
        sub_id = self._generate_subscription_id()
        self._equity_callbacks[sub_id] = callback
        if on_error:
            self._error_callbacks[sub_id] = on_error

        logger.info(f"Registered equity subscription: {sub_id}")
        self._start_execution_simulator_if_needed()

        return sub_id

    def unsubscribe(self, subscription_id: str) -> None:
        """Unsubscribe from a stream."""
        # Remove from all callback registries
        removed = False

        if subscription_id in self._order_callbacks:
            del self._order_callbacks[subscription_id]
            removed = True
        if subscription_id in self._position_callbacks:
            del self._position_callbacks[subscription_id]
            removed = True
        if subscription_id in self._execution_callbacks:
            del self._execution_callbacks[subscription_id]
            removed = True
        if subscription_id in self._equity_callbacks:
            del self._equity_callbacks[subscription_id]
            removed = True

        # Remove error callback
        self._error_callbacks.pop(subscription_id, None)

        if not removed:
            logger.warning(f"Subscription ID not found: {subscription_id}")

        logger.info(f"Unsubscribed: {subscription_id}")
        self._stop_execution_simulator_if_empty()

    # =========================================================================
    # Execution Simulator (internal)
    # =========================================================================

    async def _execution_simulator(self) -> None:
        """Simulate random order executions at configurable intervals."""
        logger.info("Execution simulator started")

        while not self._shutdown_event.is_set():
            try:
                delay = random.uniform(
                    1.0,
                    2.0,
                )
                await asyncio.sleep(delay)

                # Find all WORKING orders
                working_orders = [
                    order_id
                    for order_id, order in self._orders.items()
                    if order.status == OrderStatus.WORKING
                ]

                if working_orders:
                    order_id = random.choice(working_orders)
                    logger.info(f"Simulating execution for order: {order_id}")
                    await self._simulate_execution(order_id)
                else:
                    logger.debug("No working orders to execute")

            except asyncio.CancelledError:
                logger.info("Execution simulator cancelled")
                break
            except Exception as e:
                logger.exception(f"Error in execution simulator: {e}")
                # Continue running despite errors

    def _get_execution_price(self, order: PlacedOrder) -> float:
        """Determine execution price based on order type."""
        if order.type == OrderType.MARKET:
            return order.limitPrice if order.limitPrice is not None else 100.0
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
        """Simulate order execution and trigger update cascade."""
        await asyncio.sleep(0.2)  # Small delay for realism

        order = self._orders.get(order_id)
        if not order or order.status != OrderStatus.WORKING:
            return

        execution_price = self._get_execution_price(order)

        # Create execution
        execution = Execution(
            symbol=order.symbol,
            price=execution_price,
            qty=order.qty,
            side=order.side,
            time=int(time.time() * 1000),
        )
        self._executions.append(execution)

        # 1. Broadcast execution update
        await self._broadcast_execution(execution)

        # 2. Update order status
        order.status = OrderStatus.FILLED
        order.filledQty = order.qty
        order.avgPrice = execution_price
        order.updateTime = execution.time

        # Broadcast order update
        await self._broadcast_order(order)

        # 3. Update equity (triggers position update)
        await self._update_equity(execution)

    async def _broadcast_order(self, order: PlacedOrder) -> None:
        """Broadcast order update to all subscribers."""
        for callback in list(self._order_callbacks.values()):
            try:
                await callback(order)
            except Exception as e:
                logger.exception(f"Error in order callback: {e}")

    async def _broadcast_position(self, position: Position) -> None:
        """Broadcast position update to all subscribers."""
        for callback in list(self._position_callbacks.values()):
            try:
                await callback(position)
            except Exception as e:
                logger.exception(f"Error in position callback: {e}")

    async def _broadcast_execution(self, execution: Execution) -> None:
        """Broadcast execution to matching symbol subscribers.

        Note: Empty symbol means 'all symbols' subscription.
        """
        for sub_id, (symbol, callback) in list(self._execution_callbacks.items()):
            # Empty symbol means subscribe to all executions
            if symbol == "" or symbol == execution.symbol:
                try:
                    await callback(execution)
                except Exception as e:
                    logger.exception(f"Error in execution callback: {e}")

    async def _broadcast_equity(self) -> None:
        """Broadcast equity update to all subscribers."""
        for callback in list(self._equity_callbacks.values()):
            try:
                await callback(self._equity)
            except Exception as e:
                logger.exception(f"Error in equity callback: {e}")

    async def _update_equity(self, execution: Execution) -> None:
        """Update equity after execution and broadcast changes."""
        position = self._positions.get(execution.symbol)

        if position is not None and position.qty != 0:
            if position.side == execution.side:
                # Adding to position - no realized P&L
                pass
            else:
                # Closing/reducing position - realize P&L
                qty_to_close = min(execution.qty, position.qty)

                if position.side == Side.BUY:
                    pnl = (execution.price - position.avgPrice) * qty_to_close
                else:
                    pnl = (position.avgPrice - execution.price) * qty_to_close

                self._equity.balance += pnl
                self._equity.realizedPL += pnl

                remaining_qty = position.qty - qty_to_close
                if remaining_qty == 0:
                    if execution.symbol in self._unrealized_pl:
                        del self._unrealized_pl[execution.symbol]

        # Broadcast equity update
        await self._broadcast_equity()

        # Trigger position update
        await self._update_position(execution)

    async def _update_position(self, execution: Execution) -> None:
        """Update position from execution and broadcast changes."""
        existing = self._positions.get(execution.symbol)

        if existing:
            if existing.side == execution.side:
                # Adding to position - weighted average price
                total_cost = (existing.qty * existing.avgPrice) + (
                    execution.qty * execution.price
                )
                total_qty = existing.qty + execution.qty

                existing.qty = total_qty
                existing.avgPrice = total_cost / total_qty

                # Calculate unrealized P&L
                if existing.side == Side.BUY:
                    unrealized = (execution.price - existing.avgPrice) * existing.qty
                else:
                    unrealized = (existing.avgPrice - execution.price) * existing.qty

                self._unrealized_pl[execution.symbol] = unrealized
                self._equity.unrealizedPL = sum(self._unrealized_pl.values())
                self._equity.equity = self._equity.balance + self._equity.unrealizedPL

                await self._broadcast_position(existing)
            else:
                # Opposite side - closing or reversing
                if execution.qty < existing.qty:
                    # Partial close
                    existing.qty -= execution.qty

                    if existing.side == Side.BUY:
                        unrealized = (
                            execution.price - existing.avgPrice
                        ) * existing.qty
                    else:
                        unrealized = (
                            existing.avgPrice - execution.price
                        ) * existing.qty

                    self._unrealized_pl[execution.symbol] = unrealized
                    self._equity.unrealizedPL = sum(self._unrealized_pl.values())
                    self._equity.equity = (
                        self._equity.balance + self._equity.unrealizedPL
                    )

                    await self._broadcast_position(existing)

                elif execution.qty == existing.qty:
                    # Full close
                    existing.qty = 0

                    if execution.symbol in self._unrealized_pl:
                        del self._unrealized_pl[execution.symbol]
                    self._equity.unrealizedPL = sum(self._unrealized_pl.values())
                    self._equity.equity = (
                        self._equity.balance + self._equity.unrealizedPL
                    )

                    await self._broadcast_position(existing)
                    del self._positions[execution.symbol]

                else:
                    # Reverse position
                    new_qty = execution.qty - existing.qty

                    existing.side = execution.side
                    existing.qty = new_qty
                    existing.avgPrice = execution.price

                    self._unrealized_pl[execution.symbol] = 0.0
                    self._equity.unrealizedPL = sum(self._unrealized_pl.values())
                    self._equity.equity = (
                        self._equity.balance + self._equity.unrealizedPL
                    )

                    await self._broadcast_position(existing)
        else:
            # New position
            new_position = Position(
                id=execution.symbol,
                symbol=execution.symbol,
                qty=execution.qty,
                side=execution.side,
                avgPrice=execution.price,
            )
            self._positions[execution.symbol] = new_position

            self._unrealized_pl[execution.symbol] = 0.0
            self._equity.unrealizedPL = sum(self._unrealized_pl.values())
            self._equity.equity = self._equity.balance + self._equity.unrealizedPL

            await self._broadcast_position(new_position)

    # =========================================================================
    # Lifecycle / Testing Helpers
    # =========================================================================

    def reset(self) -> None:
        """Reset provider to initial state (for testing)."""
        # Cancel execution simulator
        if self._execution_simulator_task:
            self._execution_simulator_task.cancel()
            self._execution_simulator_task = None

        # Clear all state
        self._orders = {}
        self._positions = {}
        self._executions = []
        self._order_counter = 1
        self._leverage_settings = {}
        self._unrealized_pl = {}
        self._equity = EquityData(
            equity=100000.0,
            balance=100000.0,
            unrealizedPL=0.0,
            realizedPL=0.0,
        )

        # Clear subscriptions
        self._order_callbacks = {}
        self._position_callbacks = {}
        self._execution_callbacks = {}
        self._equity_callbacks = {}
        self._error_callbacks = {}

    async def execute_all_working_orders(self) -> None:
        """Execute all working orders immediately (for testing)."""
        working_order_ids = [
            order_id
            for order_id, order in self._orders.items()
            if order.status == OrderStatus.WORKING
        ]

        for order_id in working_order_ids:
            await self._simulate_execution(order_id)

    def shutdown(self) -> None:
        """Shutdown provider (cancel background tasks)."""
        self._shutdown_event.set()
        if self._execution_simulator_task:
            self._execution_simulator_task.cancel()
            self._execution_simulator_task = None

        if DEBUG_TWS_BROKER:
            logger.info("Shutting down TWSBrokerProvider...")
        self._tws_client.shutdown()
        if DEBUG_TWS_BROKER:
            logger.info("TWSBrokerProvider shutdown complete.")


# Alias for backward compatibility
TWSBrokerProvider = TWSBrokerProvider

__all__ = ["TWSBrokerProvider", "TWSBrokerProvider"]
