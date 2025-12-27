"""TWS broker provider - Interactive Brokers order execution integration.

Layer 3 of TWS integration:
- Implements BrokerCapability interface
- Domain conversion (TWS types ↔ core models) via tws_mappers
- Delegates TWS communication to TWSClient (Layer 2)
- Provider-agnostic error translation

Architecture:
- TWSBrokerProvider (Layer 3): BrokerCapability impl, domain conversion
- TWSClient (Layer 2): AsyncIO bridge, EWrapper callbacks
- IBSocket (Layer 1): Raw TCP protocol, message framing

Note: Uses separate client_id from TWSDatafeedProvider (default: 2 vs 1).
"""

import asyncio
import logging
from decimal import Decimal
from pathlib import Path
from typing import Any, Awaitable, Callable

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
    PlacedOrder,
    PlaceOrderResult,
    Position,
    PreOrder,
)
from trading_api.models.common import CapabilitySpec
from trading_api.models.exceptions import ProviderException, TradingApiException
from trading_api.models.providers.tws_configs import TWSBrokerProviderConfig
from trading_api.providers.tws.tws_connection import TWSClient
from trading_api.providers.tws.tws_mappers import (
    build_contract,
    preorder_to_tws,
    tws_account_summary_to_account_info,
    tws_account_summary_to_equity,
    tws_order_to_placed_order,
    tws_position_to_domain,
)
from trading_api.shared import Provider

logger = logging.getLogger(__name__)


class TWSBrokerProvider(Provider, BrokerCapability):
    """TWS broker provider - implements BrokerCapability with AsyncIO bridge.

    [LAYER 3]: Domain interface on top of TWSClient (Layer 2)
    [CONNECTION-OWNER]: Manages own TWSClient with separate client_id
    [THREAD-SAFE]: AsyncIO bridge handles cross-thread communication
    [DOMAIN-ONLY]: All public methods use domain models (no TWS types)
    """

    def __init__(self, config: TWSBrokerProviderConfig | None = None) -> None:
        """Initialize TWSBrokerProvider.

        Args:
            config: Provider configuration (auto-loaded from env if None)
        """
        self._config: TWSBrokerProviderConfig = config or TWSBrokerProviderConfig()

        # Layer 2: TWSClient with separate client_id
        self._tws_client = TWSClient(
            self._config.host, self._config.port, self._config.client_id
        )

        # Subscription management (account-wide, not per-symbol)
        self._subscription_counter = 0
        self._order_callbacks: dict[str, Callable[[PlacedOrder], Awaitable[None]]] = {}
        self._position_callbacks: dict[str, Callable[[Position], Awaitable[None]]] = {}
        self._execution_callbacks: dict[
            str, tuple[str, Callable[[Execution], Awaitable[None]]]
        ] = {}  # sub_id → (symbol, callback)
        self._equity_callbacks: dict[str, Callable[[EquityData], Awaitable[None]]] = {}
        self._error_callbacks: dict[
            str, Callable[[TradingApiException], Awaitable[None]]
        ] = {}

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
    def config(self) -> TWSBrokerProviderConfig:  # type: ignore[override]
        """Return provider configuration."""
        return self._config

    # =========================================================================
    # BrokerCapability - Snapshot Methods (async)
    # =========================================================================

    async def place_order(self, order: PreOrder) -> PlaceOrderResult:
        """Place a new order via TWS.

        Converts PreOrder to TWS Contract+Order, submits via TWSClient,
        and returns PlaceOrderResult with the assigned order ID.
        """
        # Convert domain order to TWS types
        contract, tws_order = preorder_to_tws(order, self._config.account_id)

        # Get next valid order ID from TWS
        order_id = self._tws_client.next_order_id

        # Submit order via TWSClient (sync, fire-and-forget)
        self._tws_client.placeOrder(order_id, contract, tws_order)

        # Return result with assigned order ID
        return PlaceOrderResult(orderId=str(order_id))

    async def modify_order(self, order_id: str, order: PreOrder) -> None:
        """Modify an existing order via TWS.

        TWS modifies orders by re-submitting with the same order ID.
        The order fields are replaced with the new PreOrder values.
        """
        # Convert domain order to TWS types
        contract, tws_order = preorder_to_tws(order, self._config.account_id)

        # Re-submit with same order ID to modify (sync, fire-and-forget)
        self._tws_client.placeOrder(int(order_id), contract, tws_order)

    async def cancel_order(self, order_id: str) -> None:
        """Cancel an order via TWS.

        Sends cancel request to TWS. Order status updates are
        received asynchronously via order callbacks.
        """
        # Sync call, fire-and-forget
        self._tws_client.cancelOrder(int(order_id))

    async def get_orders(self) -> list[PlacedOrder]:
        """Get all open orders from TWS.

        Requests all open orders and converts them to domain PlacedOrder models.
        Returns completed snapshot when all orders have been received.
        """
        # Request open orders from TWS (returns list of order data dicts)
        tws_orders = await self._tws_client.reqOpenOrders()

        # Convert each TWS order to domain PlacedOrder
        placed_orders: list[PlacedOrder] = []
        for order_data in tws_orders:
            placed_order = tws_order_to_placed_order(order_data)
            placed_orders.append(placed_order)

        return placed_orders

    async def close_position(
        self, position_id: str, amount: float | None = None
    ) -> None:
        """Close position via TWS by placing an opposite order.

        Args:
            position_id: Position ID (typically the symbol ticker)
            amount: Amount to close (None = close entire position)
        """
        # Get current positions to find the one we're closing
        positions = await self.get_positions()
        target_position = next(
            (p for p in positions if p.id == position_id or p.symbol == position_id),
            None,
        )

        if target_position is None:
            raise ProviderException(
                code="PROVIDER_BROKER_POSITION_NOT_FOUND",
                message=f"Position not found: {position_id}",
                provider="tws",
                capability="broker",
            )

        # Determine quantity to close
        qty_to_close = amount if amount is not None else target_position.qty

        if qty_to_close <= 0:
            return  # Nothing to close

        # Build opposite order to close position
        from ibapi.order import Order as TWSOrder

        contract = build_contract(target_position.symbol)

        order = TWSOrder()
        # Opposite side: if long (BUY), we SELL to close; if short (SELL), we BUY to close
        order.action = "SELL" if target_position.side == 1 else "BUY"
        order.totalQuantity = Decimal(str(qty_to_close))
        order.orderType = "MKT"  # Market order for immediate execution
        order.tif = "GTC"
        order.account = self._config.account_id
        order.transmit = True

        # Place the closing order
        order_id = self._tws_client.next_order_id
        self._tws_client.placeOrder(order_id, contract, order)

    async def edit_position_brackets(
        self,
        position_id: str,
        brackets: Brackets,
    ) -> None:
        """Update position brackets via TWS bracket orders.

        TWS bracket orders require creating linked parent/child orders with
        parentId relationships. This is complex to implement correctly and
        requires careful order state management.

        Future implementation would:
        1. Find existing bracket orders for the position
        2. Cancel/modify stop loss and take profit child orders
        3. Place new bracket orders with updated prices

        Raises:
            NotImplementedError: Bracket editing not yet supported
        """
        raise NotImplementedError(
            "TWSBrokerProvider.edit_position_brackets not yet implemented. "
            "Use manual bracket orders via place_order() with parentId."
        )

    async def get_positions(self) -> list[Position]:
        """Get all open positions from TWS.

        Returns:
            List of Position objects for all open positions
        """
        # Request positions from TWS
        tws_positions = await self._tws_client.reqPositions()

        # Convert each TWS position to domain Position
        positions: list[Position] = []
        for position_data in tws_positions:
            # Skip zero-quantity positions (closed)
            if float(position_data.get("position", 0)) == 0:
                continue
            position = tws_position_to_domain(position_data)
            positions.append(position)

        return positions

    async def get_executions(self, symbol: str) -> list[Execution]:
        """Get execution history for a symbol from TWS.

        Note: TWS executions require reqExecutions() with ExecutionFilter.
        For now, return empty list - full implementation in Phase 4.
        """
        # TODO: Phase 4 - Implement with TWSClient.reqExecutions()
        # TWS requires ExecutionFilter and returns execDetails callbacks
        return []

    async def get_account_info(self) -> AccountMetainfo:
        """Get account metadata from TWS.

        Returns:
            AccountMetainfo with account ID and name
        """
        # Request account summary to get account info
        summary_data = await self._tws_client.reqAccountSummarySnapshot(
            group="All",
            tags="AccountType",  # Just need account ID
        )

        return tws_account_summary_to_account_info(
            summary_data, self._config.account_id
        )

    async def get_equity(self) -> EquityData:
        """Get current equity data from TWS.

        Returns:
            EquityData with equity, balance, and P&L values
        """
        # Request account summary with equity-related tags
        summary_data = await self._tws_client.reqAccountSummarySnapshot(
            group="All",
            tags="NetLiquidation,TotalCashValue,UnrealizedPnL,RealizedPnL",
        )

        return tws_account_summary_to_equity(summary_data)

    async def preview_order(self, order: PreOrder) -> OrderPreviewResult:
        """Preview order costs (estimated, TWS has limited support).

        TWS doesn't provide a native order preview API, so we return
        estimated values based on order parameters. For accurate costs,
        use the broker's platform directly.

        Returns:
            OrderPreviewResult with estimated order cost sections
        """
        from trading_api.models.broker import (
            OrderPreviewSection,
            OrderPreviewSectionRow,
        )

        # Calculate estimated order value
        price = order.limitPrice or order.stopPrice or 0.0
        estimated_value = price * order.qty if price > 0 else 0.0

        # Build preview sections
        order_section = OrderPreviewSection(
            header="Order Details",
            rows=[
                OrderPreviewSectionRow(
                    title="Symbol", value=order.symbol.split(":")[0]
                ),
                OrderPreviewSectionRow(
                    title="Side", value="Buy" if order.side == 1 else "Sell"
                ),
                OrderPreviewSectionRow(title="Quantity", value=str(order.qty)),
                OrderPreviewSectionRow(
                    title="Order Type",
                    value={1: "Limit", 2: "Market", 3: "Stop", 4: "Stop Limit"}.get(
                        order.type, "Unknown"
                    ),
                ),
            ],
        )

        cost_section = OrderPreviewSection(
            header="Estimated Costs",
            rows=[
                OrderPreviewSectionRow(
                    title="Order Value",
                    value=f"${estimated_value:,.2f}" if estimated_value > 0 else "N/A",
                ),
                OrderPreviewSectionRow(
                    title="Commission",
                    value="Varies (see IBKR fee schedule)",
                ),
                OrderPreviewSectionRow(
                    title="Total",
                    value="Estimated at execution",
                ),
            ],
        )

        return OrderPreviewResult(
            sections=[order_section, cost_section],
            confirmId=None,  # TWS doesn't use confirm IDs
            warnings=["Costs are estimated. Actual costs determined at execution."],
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
        from ibapi.order import Order as TWSOrder

        contract = build_contract(params.symbol)

        # Build WhatIf order (simulation only, no execution)
        order = TWSOrder()
        order.action = "BUY" if params.side == 1 else "SELL"
        order.totalQuantity = Decimal("1")  # Single unit for margin calc
        order.orderType = "MKT"
        order.whatIf = True  # Key flag: margin simulation mode
        order.account = self._config.account_id

        # Capture response via one-shot callback
        loop = asyncio.get_event_loop()
        result_future: asyncio.Future[dict[str, Any]] = loop.create_future()
        target_order_id = self._tws_client.next_order_id

        async def capture_whatif_response(order_data: dict[str, Any]) -> None:
            if (
                order_data.get("orderId") == target_order_id
                and not result_future.done()
            ):
                result_future.set_result(order_data)

        # Save and replace order hooks temporarily
        original_hooks = self._tws_client.ibsocket._order_hooks
        self._tws_client.registerOrderCallback(capture_whatif_response)

        try:
            # Fire-and-forget: TWS responds via openOrder callback
            self._tws_client.placeOrder(target_order_id, contract, order)

            # Await the callback response
            order_data = await asyncio.wait_for(result_future, timeout=10.0)
        finally:
            # Restore original hooks
            self._tws_client.ibsocket._order_hooks = original_hooks

        # Extract margin from OrderState
        order_state = order_data.get("orderState")
        if order_state is None:
            raise ProviderException(
                code="PROVIDER_BROKER_MARGIN_UNAVAILABLE",
                message="WhatIf order did not return margin information",
                provider="tws",
                capability="broker",
            )

        # Parse margin change (string like "25000.00" or empty)
        margin_change_str = getattr(order_state, "initMarginChange", "") or "0"
        try:
            margin_change = float(margin_change_str.replace(",", ""))
        except ValueError:
            margin_change = 0.0

        # Get current price for leverage calculation
        current_price = await self._get_symbol_price(params.symbol)

        # Compute implied leverage: price / margin_per_share
        if margin_change > 0 and current_price > 0:
            implied_leverage = current_price / margin_change
        else:
            # Fallback: Reg T default (50% margin = 2x leverage)
            implied_leverage = 2.0

        symbol_display = params.symbol.split(":")[0]
        return LeverageInfo(
            title=f"Margin Info ({symbol_display})",
            leverage=round(implied_leverage, 2),
            min=1.0,  # Cash (no margin)
            max=round(implied_leverage, 2),  # Max = current implied (not adjustable)
            step=0.0,  # Not adjustable via API
        )

    async def _get_symbol_price(self, symbol: str) -> float:
        """Get current price for a symbol via quote snapshot.

        Args:
            symbol: Symbol in format "SYMBOL:EXCHANGE:SECTYPE-CONID"

        Returns:
            Current price (last trade or mid-price)
        """
        contract = build_contract(symbol)

        try:
            snapshot = await self._tws_client.reqQuoteSnapshot(contract, timeout=5.0)
            # Prefer last price, fall back to mid of bid/ask
            last_price = snapshot.get("last", 0.0)
            if last_price and last_price > 0:
                return float(last_price)

            bid = snapshot.get("bid", 0.0)
            ask = snapshot.get("ask", 0.0)
            if bid and ask and bid > 0 and ask > 0:
                return float((bid + ask) / 2)

            return 0.0
        except Exception as e:
            logger.warning(f"Failed to get price for {symbol}: {e}")
            return 0.0

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
        return f"tws-broker-sub-{self._subscription_counter}"

    async def _on_tws_order_update(self, order_data: dict) -> None:
        """Internal handler for TWS order updates - dispatches to all subscribers."""
        placed_order = tws_order_to_placed_order(order_data)
        for callback in self._order_callbacks.values():
            try:
                await callback(placed_order)
            except Exception as e:
                logger.error(f"Error in order callback: {e}")

    async def _on_tws_order_error(self, error: ProviderException) -> None:
        """Internal handler for TWS order errors - dispatches to all error callbacks."""
        for sub_id in self._order_callbacks:
            error_cb = self._error_callbacks.get(sub_id)
            if error_cb:
                try:
                    await error_cb(error)
                except Exception as e:
                    logger.error(f"Error in order error callback: {e}")

    async def _on_tws_position_update(self, position_data: dict) -> None:
        """Internal handler for TWS position updates - dispatches to all subscribers."""
        position = tws_position_to_domain(position_data)
        for callback in self._position_callbacks.values():
            try:
                await callback(position)
            except Exception as e:
                logger.error(f"Error in position callback: {e}")

    async def _on_tws_position_error(self, error: ProviderException) -> None:
        """Internal handler for TWS position errors - dispatches to all error callbacks."""
        for sub_id in self._position_callbacks:
            error_cb = self._error_callbacks.get(sub_id)
            if error_cb:
                try:
                    await error_cb(error)
                except Exception as e:
                    logger.error(f"Error in position error callback: {e}")

    def subscribe_orders(
        self,
        callback: Callable[[PlacedOrder], Awaitable[None]],
        on_error: Callable[[TradingApiException], Awaitable[None]] | None = None,
    ) -> str:
        """Subscribe to order updates from TWS.

        Registers callback for real-time order updates (openOrder, orderStatus).
        Multiple subscriptions share the same TWS callback registration.
        """
        sub_id = self._generate_subscription_id()
        self._order_callbacks[sub_id] = callback
        if on_error:
            self._error_callbacks[sub_id] = on_error

        # Register TWS callback if first subscriber
        if len(self._order_callbacks) == 1:
            self._tws_client.registerOrderCallback(
                self._on_tws_order_update,
                self._on_tws_order_error,
            )

        logger.info(f"Subscribed to orders: {sub_id}")
        return sub_id

    def subscribe_positions(
        self,
        callback: Callable[[Position], Awaitable[None]],
        on_error: Callable[[TradingApiException], Awaitable[None]] | None = None,
    ) -> str:
        """Subscribe to position updates from TWS.

        Registers callback for real-time position updates.
        Multiple subscriptions share the same TWS callback registration.
        """
        sub_id = self._generate_subscription_id()
        self._position_callbacks[sub_id] = callback
        if on_error:
            self._error_callbacks[sub_id] = on_error

        # Register TWS callback if first subscriber
        if len(self._position_callbacks) == 1:
            self._tws_client.registerPositionCallback(
                self._on_tws_position_update,
                self._on_tws_position_error,
            )

        logger.info(f"Subscribed to positions: {sub_id}")
        return sub_id

    def subscribe_executions(
        self,
        symbol: str,
        callback: Callable[[Execution], Awaitable[None]],
        on_error: Callable[[TradingApiException], Awaitable[None]] | None = None,
    ) -> str:
        """Subscribe to execution updates from TWS.

        Note: TWS execution streaming requires reqExecutions() with filter.
        For now, returns subscription ID but execution updates will come
        through order callbacks. Full implementation planned for later.
        """
        sub_id = self._generate_subscription_id()
        self._execution_callbacks[sub_id] = (symbol, callback)
        if on_error:
            self._error_callbacks[sub_id] = on_error

        logger.info(f"Subscribed to executions for {symbol}: {sub_id}")
        # Note: TWS execution streaming requires additional implementation
        # Executions are typically delivered via commissionReport callbacks
        return sub_id

    def subscribe_equity(
        self,
        callback: Callable[[EquityData], Awaitable[None]],
        on_error: Callable[[TradingApiException], Awaitable[None]] | None = None,
    ) -> str:
        """Subscribe to equity updates from TWS.

        Note: TWS doesn't push account changes in real-time. This subscription
        registers the callback but equity updates require polling via
        get_equity() or periodic reqAccountSummary() calls.
        """
        sub_id = self._generate_subscription_id()
        self._equity_callbacks[sub_id] = callback
        if on_error:
            self._error_callbacks[sub_id] = on_error

        logger.info(f"Subscribed to equity: {sub_id}")
        # Note: Equity updates require polling - TWS doesn't push account data
        # Caller should implement periodic polling using get_equity()
        return sub_id

    def unsubscribe(self, subscription_id: str) -> None:
        """Unsubscribe from a stream.

        Cleans up TWS callback registrations when no subscribers remain.
        """
        # Remove from all callback registries
        removed = False

        if subscription_id in self._order_callbacks:
            del self._order_callbacks[subscription_id]
            removed = True
            # Unregister TWS callback if no more order subscribers
            if len(self._order_callbacks) == 0:
                self._tws_client.unregisterOrderCallback()

        if subscription_id in self._position_callbacks:
            del self._position_callbacks[subscription_id]
            removed = True
            # Unregister TWS callback if no more position subscribers
            if len(self._position_callbacks) == 0:
                self._tws_client.unregisterPositionCallback()

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

    # =========================================================================
    # Lifecycle
    # =========================================================================

    def shutdown(self) -> None:
        """Perform any necessary cleanup on provider shutdown.

        Idempotent: safe to call multiple times.
        """
        if not hasattr(self, "_tws_client"):
            return  # Already shutdown

        logger.info("Shutting down TWSBrokerProvider...")
        self._tws_client.shutdown()
        logger.info("TWSBrokerProvider shutdown complete.")


# Alias for auto-discovery compatibility
TwsBrokerProvider = TWSBrokerProvider

__all__ = ["TWSBrokerProvider", "TwsBrokerProvider"]
