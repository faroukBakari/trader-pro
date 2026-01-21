"""Broker capability interface."""

from abc import ABC, abstractmethod
from typing import Awaitable, Callable

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
from trading_api.models.exceptions import TradingApiException


class BrokerCapability(ABC):
    """Broker capability interface - order execution and account management.

    Providers implementing this capability can provide broker operations including:
    - Order management (place, modify, cancel)
    - Position management (close, edit brackets)
    - Account information (equity, leverage)
    - Real-time subscriptions (orders, positions, executions, equity)

    [PROVIDER-AGNOSTIC]: All methods use domain models only (no provider-specific types).
    [ASYNC]: All data-fetching methods are async for I/O efficiency.
    [STREAMING]: Subscription methods use callback pattern (sync method returning subscription ID).
    """

    # =========================================================================
    # Snapshot Methods (async) - Request/Response pattern
    # =========================================================================

    @abstractmethod
    async def place_order(
        self, order: PreOrder, confirm_id: str | None = None
    ) -> PlaceOrderResult:
        """Place a new order.

        Args:
            order: Order request with symbol, type, side, qty, prices
            confirm_id: Optional confirmation ID from preview (for correlation/audit)

        Returns:
            PlaceOrderResult with generated order ID

        Raises:
            ProviderException: If order placement fails
        """
        ...

    @abstractmethod
    async def modify_order(self, order_id: str, order: PreOrder) -> None:
        """Modify an existing order.

        Args:
            order_id: ID of the order to modify
            order: Updated order details

        Raises:
            ProviderException: If order not found or cannot be modified
        """
        ...

    @abstractmethod
    async def cancel_order(self, order_id: str) -> None:
        """Cancel an order.

        Args:
            order_id: ID of the order to cancel

        Raises:
            ProviderException: If order not found or cannot be cancelled
        """
        ...

    @abstractmethod
    async def close_position(
        self, position_id: str, amount: float | None = None
    ) -> None:
        """Close position (full or partial).

        Args:
            position_id: ID of the position to close
            amount: Amount to close (None = full position)

        Raises:
            ProviderException: If position not found or invalid amount
        """
        ...

    @abstractmethod
    async def edit_position_brackets(
        self,
        position_id: str,
        brackets: Brackets,
    ) -> None:
        """Update position brackets (stop-loss, take-profit).

        Args:
            position_id: ID of the position to modify
            brackets: New bracket values

        Raises:
            ProviderException: If position not found
        """
        ...

    @abstractmethod
    async def get_orders(self) -> list[PlacedOrder]:
        """Get all orders.

        Returns:
            List of all orders (working, filled, cancelled)
        """
        ...

    @abstractmethod
    async def get_positions(self) -> list[Position]:
        """Get all open positions.

        Returns:
            List of open positions
        """
        ...

    @abstractmethod
    async def get_executions(self, symbol: str) -> list[Execution]:
        """Get execution history for a symbol.

        Args:
            symbol: Symbol to get executions for

        Returns:
            List of executions for the symbol
        """
        ...

    @abstractmethod
    async def get_all_executions(self) -> list[Execution]:
        """Get all execution history (across all symbols).

        Returns:
            List of all executions
        """
        ...

    @abstractmethod
    async def get_account_info(self) -> AccountMetainfo:
        """Get account metadata.

        Returns:
            Account metadata (ID, name)
        """
        ...

    @abstractmethod
    async def get_equity(self) -> EquityData:
        """Get current equity/balance data.

        Returns:
            Equity data (balance, equity, P&L)
        """
        ...

    @abstractmethod
    async def preview_order(self, order: PreOrder) -> OrderPreviewResult:
        """Preview order costs and requirements.

        Args:
            order: Order to preview

        Returns:
            Preview with estimated costs, fees, margin requirements
        """
        ...

    @abstractmethod
    async def preview_leverage(
        self, params: LeverageSetParams
    ) -> LeveragePreviewResult:
        """Preview leverage change.

        Args:
            params: Leverage parameters to preview

        Returns:
            Preview with warnings/errors
        """
        ...

    @abstractmethod
    async def get_leverage_info(self, params: LeverageInfoParams) -> LeverageInfo:
        """Get leverage information for symbol.

        Args:
            params: Symbol to get leverage info for

        Returns:
            Current leverage settings and constraints
        """
        ...

    @abstractmethod
    async def set_leverage(self, params: LeverageSetParams) -> LeverageSetResult:
        """Set leverage for symbol.

        Args:
            params: Leverage parameters

        Returns:
            Confirmed leverage value

        Raises:
            ProviderException: If leverage out of range
        """
        ...

    # =========================================================================
    # Streaming Methods (async, callback-based) - matches DatafeedCapability
    # =========================================================================

    @abstractmethod
    async def subscribe_orders(
        self,
        callback: Callable[[PlacedOrder], Awaitable[None]],
        on_error: Callable[[TradingApiException], Awaitable[None]] | None = None,
    ) -> str:
        """Subscribe to order updates.

        Args:
            callback: Callback invoked for each order update
            on_error: Optional callback for streaming errors

        Returns:
            Subscription ID (for unsubscribe)

        Raises:
            ProviderException: If subscription fails

        [CONTINUOUS]: Callback invoked on every order status change.
        [THREAD-SAFE]: Callback may be invoked from provider thread.
        """
        ...

    @abstractmethod
    async def subscribe_positions(
        self,
        callback: Callable[[Position], Awaitable[None]],
        on_error: Callable[[TradingApiException], Awaitable[None]] | None = None,
    ) -> str:
        """Subscribe to position updates.

        Args:
            callback: Callback invoked for each position update
            on_error: Optional callback for streaming errors

        Returns:
            Subscription ID (for unsubscribe)

        Raises:
            ProviderException: If subscription fails

        [CONTINUOUS]: Callback invoked on every position change.
        [CLOSURE]: Position with qty=0 indicates closure.
        """
        ...

    @abstractmethod
    async def subscribe_executions(
        self,
        symbol: str,
        callback: Callable[[Execution], Awaitable[None]],
        on_error: Callable[[TradingApiException], Awaitable[None]] | None = None,
    ) -> str:
        """Subscribe to execution updates for a symbol.

        Args:
            symbol: Symbol to subscribe to
            callback: Callback invoked for each execution
            on_error: Optional callback for streaming errors

        Returns:
            Subscription ID (for unsubscribe)

        Raises:
            ProviderException: If subscription fails

        [CONTINUOUS]: Callback invoked for each new execution.
        """
        ...

    @abstractmethod
    async def subscribe_equity(
        self,
        callback: Callable[[EquityData], Awaitable[None]],
        on_error: Callable[[TradingApiException], Awaitable[None]] | None = None,
    ) -> str:
        """Subscribe to equity/balance updates.

        Args:
            callback: Callback invoked for each equity update
            on_error: Optional callback for streaming errors

        Returns:
            Subscription ID (for unsubscribe)

        Raises:
            ProviderException: If subscription fails

        [CONTINUOUS]: Callback invoked on balance/P&L changes.
        """
        ...

    @abstractmethod
    def unsubscribe(self, subscription_id: str) -> None:
        """Unsubscribe from a stream.

        Args:
            subscription_id: ID returned from subscribe_* methods

        Raises:
            ProviderException: If subscription ID not found
        """
        ...
