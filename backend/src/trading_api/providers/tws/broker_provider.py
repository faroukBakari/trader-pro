"""FakeBrokerProvider - Mock broker for development and testing.

Implements BrokerCapability with in-memory state and simulated execution.
All business logic (orders, positions, P&L) is encapsulated here.
"""

import asyncio
import itertools
import logging
import os
import random
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
    OrderType,
    PlacedOrder,
    PlaceOrderResult,
    Position,
    PreOrder,
    Side,
)
from trading_api.models.common import CapabilitySpec
from trading_api.models.exceptions import ProviderException, TradingApiException
from trading_api.models.market.quotes import GetQuotesRequest
from trading_api.models.providers.tws_configs import TWSBrokerProviderConfig
from trading_api.providers.tws.order_tracker import TrackedOrder
from trading_api.providers.tws.position_tracker import TrackedPosition
from trading_api.providers.tws.tws_connection import TWSClient
from trading_api.providers.tws.tws_mappers import (
    order_state_to_preview_result,
    preorder_to_tws,
    tracked_order_to_placed_order,
)
from trading_api.shared import Provider
from trading_api.shared.client_factory import InterModuleClients

logger = logging.getLogger(__name__)
us_eastern = ZoneInfo("US/Eastern")
DEBUG_TWS_BROKER = os.environ.get("DEBUG_TWS_BROKER") == "true"


# =============================================================================
# Bracket Order Grouping Helpers
# =============================================================================


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

        self.inter_module_clients = InterModuleClients(caller_id="tws-broker-provider")

        # Layer 2: TWSClient with separate client_id
        self._tws_client = TWSClient(
            self._config.host, self._config.port, self._config.client_id
        )

        # Business state (in-memory)
        self._executions: list[Execution] = []
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

    async def _resolve_trading_contract(self, ticker: str) -> Contract:
        """Resolve contract for current trading session.

        Uses session contract by default. If market closed AND darkpool
        available, opportunistically routes to OVERNIGHT exchange.

        Args:
            ticker: Symbol ticker (e.g., "NASDAQ:AAPL")

        Returns:
            Contract suitable for current trading session

        Raises:
            ProviderException: If contract not found
        """
        details = await self._tws_client.req_ticker_details(ticker)

        return details.build_best_contract()

    async def _submit_order(
        self, order: PreOrder, order_id: int | None = None
    ) -> tuple[TrackedOrder, list[TrackedOrder]]:
        """Execute order placement or modification via TWS.

        Shared logic for place_order and modify_order:
        1. Resolve contract for current session (uses darkpool if market closed)
        2. Convert PreOrder to TWS Order objects (with optional brackets)
        3. Submit via placeOrderGroup

        Args:
            order: PreOrder with order details and optional brackets
            order_id: None for new orders, existing ID for modifications

        Returns:
            Tuple of (parent_tracked_order, child_tracked_orders)
        """
        contract = await self._resolve_trading_contract(order.symbol)

        # Convert domain order to TWS types (may return multiple orders for brackets)
        # Empty account string is valid for single-account users
        # order_id=-1 means new order, >0 means modify existing
        parent_order, stop_loss_order, take_profit_order = preorder_to_tws(
            order, contract, order_id=order_id
        )

        parent_order.tif = "DAY" if contract.exchange == "OVERNIGHT" else "GTC"

        childs_to_place = [
            o for o in [stop_loss_order, take_profit_order] if o is not None
        ]

        return await self._tws_client.placeOrderGroup(
            contract, parent_order, childs_to_place
        )

    async def place_order(
        self, order: PreOrder, confirm_id: str | None = None
    ) -> PlaceOrderResult:
        """Place a new order (with optional bracket orders).

        Supports bracket orders (stopLoss, takeProfit, trailingStopPips) by placing
        multiple linked orders via TWS parent/child mechanism with OCA grouping.

        Args:
            order: PreOrder from TradingView containing order details and optional brackets
            confirm_id: Optional confirmation ID from preview (for audit logging)

        Returns:
            PlaceOrderResult with parent order ID
        """
        if confirm_id:
            logger.debug(f"Placing order with confirm_id={confirm_id}")
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

    async def get_orders(self) -> list[PlacedOrder]:
        """Get all open orders from TWS.

        Requests all open orders and converts them to domain PlacedOrder models.
        Groups bracket orders and enriches parent orders with stopLoss/takeProfit.
        Child orders are linked with parentId/parentType for TradingView UI.
        """
        # Request open orders from TWS (returns list of TrackedOrder objects)
        tws_orders = await self._tws_client.reqOpenOrders()

        # Filter out whatIf orders
        real_orders = [
            o for o in tws_orders if (o.order.transmit and not o.order.whatIf)
        ]

        # Build contract details map for symbol resolution
        details_map: dict[int, Contract] = {
            d.contract.conId: d.contract
            for d in itertools.chain.from_iterable(
                await asyncio.gather(
                    *[
                        self._tws_client.reqContractDetails(c)
                        for c in {
                            o.contract.conId: o.contract for o in real_orders
                        }.values()
                    ]
                )
            )
        }

        return [
            tracked_order_to_placed_order(
                o, details_map.get(o.contract.conId, o.contract)
            )
            for o in real_orders
        ]

    async def get_positions(self) -> list[Position]:
        """Get all open positions from TWS.

        Returns:
            List of Position objects for all open positions
        """
        # Request positions from TWS
        tracked_positions = await self._tws_client.reqPositions()

        # Convert each TrackedPosition to domain Position using to_domain()
        return [p.to_domain() for p in tracked_positions]

    async def _get_position_by_id(self, position_id: str) -> Position | None:
        """Get position by ID."""
        positions = await self.get_positions()
        return next((p for p in positions if p.id == position_id), None)

    async def close_position(
        self, position_id: str, amount: float | None = None
    ) -> None:
        """Close position (full or partial)."""
        position = await self._get_position_by_id(position_id)
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
        position = await self._get_position_by_id(position_id)
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

        # Resolve contract for this position's symbol
        contract = await self._resolve_trading_contract(position.symbol)

        # Generate unique OCA group name for this position's brackets
        oca_group = f"brackets_{position_id}"

        # Place all bracket orders via OCA group (atomic submission)
        await self._tws_client.placeOcaGroup(
            contract,
            bracket_orders,
            oca_group,
            oca_type=1,  # CANCEL_WITH_BLOCK (overfill protection)
        )

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
        """Preview order costs and margin requirements using TWS whatIf mode.

        Uses TWS order.whatIf=True to get real margin/commission data from
        Interactive Brokers without actually placing the order.

        Args:
            order: PreOrder with order details

        Returns:
            OrderPreviewResult with margin requirements, commission, and warnings

        Note:
            Only previews the entry order. Bracket orders (stopLoss, takeProfit)
            are exit orders that release margin, so their preview is not needed.
        """
        # Resolve contract for current session (uses darkpool if market closed)
        contract = await self._resolve_trading_contract(order.symbol)

        # Convert PreOrder to TWS Order (only entry order, no brackets for preview)
        parent_order, _, _ = preorder_to_tws(order, contract)

        # Enable whatIf mode - TWS returns margin/commission without executing
        parent_order.whatIf = True

        # Place whatIf order - returns TrackedOrder with OrderState containing
        # margin requirements and commission estimates
        tracked_order = await self._tws_client.placeWhatifOrder(contract, parent_order)

        # Map OrderState to domain OrderPreviewResult
        return order_state_to_preview_result(
            tracked_order.orderState, order, str(tracked_order.orderId)
        )

    def _build_fallback_preview(
        self, order: PreOrder, confirm_id: str
    ) -> OrderPreviewResult:
        """Build fallback preview when TWS whatIf fails.

        Provides estimated values based on order details when real
        TWS margin/commission data is unavailable.

        Args:
            order: PreOrder with order details
            confirm_id: UUID for order confirmation

        Returns:
            OrderPreviewResult with estimated values and warning
        """
        estimated_price = order.limitPrice or order.stopPrice or 100.0
        order_value = order.qty * estimated_price

        sections = []

        # Order Details section
        order_type_map = {
            OrderType.MARKET: "Market",
            OrderType.LIMIT: "Limit",
            OrderType.STOP: "Stop",
            OrderType.TRAIL: "Trailing Stop",
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

        # Estimated Cost section (fallback values)
        cost_section = OrderPreviewSection(
            header="Estimated Cost (Offline)",
            rows=[
                OrderPreviewSectionRow(
                    title="Estimated Price", value=f"${estimated_price:.2f}"
                ),
                OrderPreviewSectionRow(
                    title="Order Value", value=f"${order_value:.2f}"
                ),
            ],
        )
        sections.append(cost_section)

        # Risk Management section (if brackets)
        if order.takeProfit or order.stopLoss or order.trailingStopPips:
            bracket_rows = []

            if order.takeProfit:
                bracket_rows.append(
                    OrderPreviewSectionRow(
                        title="Take Profit", value=f"${order.takeProfit:.2f}"
                    )
                )

            if order.stopLoss:
                bracket_rows.append(
                    OrderPreviewSectionRow(
                        title="Stop Loss", value=f"${order.stopLoss:.2f}"
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

        warnings: list[str] = [
            "Preview unavailable from broker - showing estimated values only"
        ]
        if order.type == OrderType.MARKET:
            warnings.append("Market orders execute immediately at current market price")

        return OrderPreviewResult(
            sections=sections,
            confirmId=confirm_id,
            warnings=warnings,
            errors=None,
        )

    async def preview_leverage(
        self, params: LeverageSetParams
    ) -> LeveragePreviewResult:
        """Preview leverage change.

        [NOT-SUPPORTED]: IBKR uses account-level margin, not per-symbol leverage.
        """
        raise ProviderException(
            code="PROVIDER_BROKER_LEVERAGE_NOT_SUPPORTED",
            message="IBKR does not support per-symbol leverage. Use account margin settings.",
            provider="tws",
            capability="broker",
        )

    # Dead code - POC for inter-module client usage
    async def _get_symbol_price(self, symbol: str) -> float:
        """Get current price for a symbol via inter-module Datafeed API.

        Uses DatafeedClient to fetch quotes through the datafeed module's
        HTTP API, maintaining proper module isolation.

        Args:
            symbol: Symbol in ticker format (e.g., "AAPL:NASDAQ:STK")

        Returns:
            Current price (last price from quote), or 0.0 on error
        """
        try:
            quotes = await self.inter_module_clients.datafeed.getQuotes(
                body=GetQuotesRequest(symbols=[symbol])
            )
            if not quotes or quotes[0].s != "ok":
                logger.warning(f"No quote data for {symbol}")
                return 0.0

            # Extract last price from quote values
            quote_values = quotes[0].v
            if isinstance(quote_values, dict):
                return float(quote_values.get("lp", 0.0))
            return float(quote_values.lp)
        except Exception as e:
            logger.warning(f"Failed to get price for {symbol}: {e}")
            return 0.0

    async def get_leverage_info(self, params: LeverageInfoParams) -> LeverageInfo:
        """Get leverage information via WhatIf order margin simulation.

        IBKR doesn't support per-symbol leverage settings, but we can compute
        implied leverage from the margin requirement using a WhatIf order.

        Formula: impliedLeverage = orderValue / marginRequired

        Args:
            params: Symbol, order type, and side for leverage query

        Returns:
            LeverageInfo with computed leverage based on margin requirements
        """
        # Resolve contract via TWSClient (cached, session-aware)
        cached_contract = await self._tws_client.req_ticker_details(params.symbol)
        contract = cached_contract.build_best_contract()

        current_price = await self._get_symbol_price(params.symbol)

        # Build WhatIf order (simulation only, no execution)
        order = Order()
        order.action = "BUY" if params.side == 1 else "SELL"
        order.totalQuantity = Decimal("1")  # Single unit for margin calc
        order.orderType = "LMT"
        order.lmtPrice = current_price if current_price > 0 else 100.0
        order.whatIf = True
        order.account = self._config.account_id

        # Single async call - OrderTracker handles callback orchestration
        tracked = await self._tws_client.placeWhatifOrder(contract, order, timeout=10.0)

        # Extract margin from TrackedOrder.orderState
        order_state = tracked.orderState
        if order_state is None:
            raise ProviderException(
                code="PROVIDER_BROKER_MARGIN_UNAVAILABLE",
                message="WhatIf order did not return margin information",
                provider="tws",
                capability="broker",
            )

        # Parse initMarginChange from OrderState (string like "25000.00")
        margin_change_str = getattr(order_state, "initMarginChange", "") or "0"
        try:
            margin_change = float(margin_change_str.replace(",", ""))
        except ValueError:
            margin_change = 0.0

        # Get current price for leverage calculation via inter-module API
        current_price = (
            tracked.order.lmtPrice
        )  # await self._get_symbol_price(params.symbol)

        # Compute implied leverage: price / margin_per_share
        if margin_change > 0 and current_price > 0:
            implied_leverage = current_price / margin_change
        else:
            implied_leverage = 1.0  # Reg T default (50% margin = 2x)

        return LeverageInfo(
            title=f"Margin Info ({params.symbol})",
            leverage=round(implied_leverage, 2),
            min=1.0,
            max=round(implied_leverage, 2),
            step=0.0,
        )

    async def set_leverage(self, params: LeverageSetParams) -> LeverageSetResult:
        """Set leverage.

        [NOT-SUPPORTED]: IBKR uses account-level margin, not per-symbol leverage.
        """
        raise ProviderException(
            code="PROVIDER_BROKER_LEVERAGE_NOT_SUPPORTED",
            message="IBKR does not support per-symbol leverage. Use account margin settings.",
            provider="tws",
            capability="broker",
        )

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
            len(self._execution_callbacks) > 0 or len(self._equity_callbacks) > 0
        )

        if self._execution_simulator_task is None and has_subscribers:
            logger.info("Starting execution simulator task")
            self._execution_simulator_task = asyncio.create_task(
                self._execution_simulator()
            )

    def _stop_execution_simulator_if_empty(self) -> None:
        """Stop execution simulator if no more subscribers."""
        has_subscribers = (
            len(self._execution_callbacks) > 0 or len(self._equity_callbacks) > 0
        )

        if self._execution_simulator_task is not None and not has_subscribers:
            logger.info("Stopping execution simulator task (no subscribers)")
            self._execution_simulator_task.cancel()
            self._execution_simulator_task = None

    async def subscribe_orders(
        self,
        callback: Callable[[PlacedOrder], Awaitable[None]],
        on_error: Callable[[TradingApiException], Awaitable[None]] | None = None,
    ) -> str:
        # Domain callback wrapper
        async def tws_callback(tracked: TrackedOrder) -> None:
            # Resolve contract for full symbol info
            if tracked.order.whatIf or not tracked.order.transmit:
                return  # Ignore whatIf orders
            details = await self._tws_client.reqContractDetails(tracked.contract)
            if details:
                contract = next(iter(details)).contract
                placed = tracked_order_to_placed_order(tracked, contract)
                await callback(placed)

        async def tws_on_error(exc: ProviderException) -> None:
            if on_error:
                await on_error(exc)

        sub_id = self._tws_client.reqOrdersStream(tws_callback, tws_on_error)

        return sub_id

    async def subscribe_positions(
        self,
        callback: Callable[[Position], Awaitable[None]],
        on_error: Callable[[TradingApiException], Awaitable[None]] | None = None,
    ) -> str:
        """Subscribe to position updates."""

        # Domain callback wrapper (TWS → Domain conversion)
        async def tws_callback(tracked: TrackedPosition) -> None:
            # TrackedPosition already has to_domain() method
            position = tracked.to_domain()
            await callback(position)

        # Error callback wrapper
        async def tws_on_error(exc: ProviderException) -> None:
            if on_error:
                await on_error(exc)

        # Delegate to TWSClient (handles stream registration + snapshot trigger)
        sub_id = self._tws_client.reqPositionsStream(tws_callback, tws_on_error)

        return sub_id

    async def subscribe_executions(
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

    async def subscribe_equity(
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

        self._tws_client.cancel_broker_stream(subscription_id)

        # Remove error callback
        self._error_callbacks.pop(subscription_id, None)

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

                logger.debug("No working orders to execute")

            except asyncio.CancelledError:
                logger.info("Execution simulator cancelled")
                break
            except Exception as e:
                logger.exception(f"Error in execution simulator: {e}")
                # Continue running despite errors

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
        position = await self._get_position_by_id(execution.symbol)

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
        self._executions = []
        self._leverage_settings = {}
        self._unrealized_pl = {}
        self._equity = EquityData(
            equity=100000.0,
            balance=100000.0,
            unrealizedPL=0.0,
            realizedPL=0.0,
        )

        # Clear subscriptions
        self._execution_callbacks = {}
        self._equity_callbacks = {}
        self._error_callbacks = {}

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
