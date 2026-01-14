"""Position tracking for TWS broker integration.

Data structures and helper class for tracking TWS position callbacks without
data transformation. Raw TWS objects (Contract) are stored directly.
Domain conversion happens via TrackedAccount.to_domain() method.
"""

from __future__ import annotations

import asyncio
import threading
import uuid
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from ibapi.const import UNSET_DECIMAL, UNSET_DOUBLE

from trading_api.models.broker import AccountMetainfo, EquityData
from trading_api.models.exceptions import ProviderException


def isUnset(value: Any) -> bool:
    """Check if a TWS value is considered 'unset' (default/placeholder)."""
    if value is None:
        return True
    if isinstance(value, (int, float)) and value == UNSET_DOUBLE:
        return True
    if isinstance(value, Decimal) and value == UNSET_DECIMAL:
        return True
    if isinstance(value, str) and value == "":
        return True
    return False


CURRENCY_SIGNS = {
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "JPY": "¥",
    "CHF": "CHF",
    "CAD": "C$",
    "AUD": "A$",
}

# TWS PascalCase tag → Python snake_case field mapping
# Used by update_account() to route accountSummary/updateAccountValue callbacks
TWS_TAG_TO_FIELD: dict[str, str] = {
    # Core equity metrics
    "NetLiquidation": "net_liquidation",
    "TotalCashValue": "total_cash_value",
    "EquityWithLoanValue": "equity_with_loan_value",
    "GrossPositionValue": "gross_position_value",
    "BuyingPower": "buying_power",
    # Margin & risk
    "AvailableFunds": "available_funds",
    "ExcessLiquidity": "excess_liquidity",
    "Cushion": "cushion",
    "InitMarginReq": "init_margin_req",
    "MaintMarginReq": "maint_margin_req",
    "Leverage": "leverage",
    # P&L (from reqPnL, also sent via reqAccountUpdates)
    "DailyPnL": "daily_pnl",
    "UnrealizedPnL": "unrealized_pnl",
    "RealizedPnL": "realized_pnl",
    # Account info
    "Currency": "currency",
    "AccountType": "account_type",
    "DayTradesRemaining": "day_trades_remaining",
    "AccountReady": "account_ready",
}


@dataclass
class TrackedAccount:
    """Wraps raw TWS account data.

    Stores account-level metrics from TWS callbacks (updateAccountValue, accountSummary).
    All values are optional - populated incrementally as updates arrive.

    Data Sources:
        - reqAccountUpdates() → updateAccountValue() callbacks
        - reqAccountSummary() → accountSummary() callbacks
        - reqPnL() → pnl() callbacks

    Thread Safety:
        - Created/updated by reader thread
        - Passed by reference to main thread callbacks (no copies)
        - Main thread consumers should not mutate these objects
    """

    id: str
    pnl_req_id: int | None = None  # Request ID for P&L subscription

    # --- Core Equity Metrics ---
    net_liquidation: Decimal | None = None  # Total account value
    total_cash_value: Decimal | None = None  # Cash + futures P&L
    equity_with_loan_value: Decimal | None = None  # Cash + stocks + bonds + funds
    gross_position_value: Decimal | None = None  # Sum of absolute position values
    buying_power: Decimal | None = None  # Max marginable US stocks purchasable

    # --- Margin & Risk ---
    available_funds: Decimal | None = None  # Available for trading
    excess_liquidity: Decimal | None = None  # Excess over margin requirements
    cushion: Decimal | None = None  # Excess liquidity as % of net liq
    init_margin_req: Decimal | None = None  # Initial margin requirement
    maint_margin_req: Decimal | None = None  # Maintenance margin requirement
    leverage: Decimal | None = None  # GrossPositionValue / NetLiquidation

    # --- P&L (Portfolio Window source) ---
    daily_pnl: Decimal | None = None  # Real-time daily P&L
    unrealized_pnl: Decimal | None = None  # Real-time unrealized P&L
    realized_pnl: Decimal | None = None  # Real-time realized P&L

    # --- Account Info ---
    currency: str | None = None  # Base account currency
    account_type: str | None = None  # Account type identifier
    day_trades_remaining: int | None = None  # PDT day trades remaining (-1 = unlimited)

    # --- Metadata ---
    account_ready: bool = True  # False during TWS server reset
    last_update_time: str | None = None  # Timestamp from updateAccountTime

    # In tws_mappers.py (add after tracked_order_to_placed_order)

    @property
    def currency_sign(self) -> str | None:
        """Get currency sign based on currency code."""
        if self.currency and self.currency in CURRENCY_SIGNS:
            return CURRENCY_SIGNS[self.currency]
        return None

    def equity_data(self) -> EquityData:
        """Convert TrackedAccount to domain EquityData.

        Maps TWS account summary metrics to TradingView broker API equity format.
        Handles optional fields with sensible defaults.

        Data Flow:
            TrackedAccount (TWS callbacks) → EquityData (domain model)

        Args:
            tracked: TrackedAccount with TWS account metrics

        Returns:
            Domain EquityData model for WebSocket streaming

        Notes:
            - equity = net_liquidation (total account value)
            - balance = total_cash_value (cash + futures P&L)
            - Falls back to 0.0 for unset values (TWS sends nulls during updates)
        """

        # Equity: Total account value (net liquidation)
        equity = 0.0
        if self.net_liquidation and not isUnset(self.net_liquidation):
            equity = float(self.net_liquidation)

        # Balance: Cash balance (total cash value)
        balance = 0.0
        if self.total_cash_value and not isUnset(self.total_cash_value):
            balance = float(self.total_cash_value)

        # Unrealized P&L (from real-time reqPnL if available, else 0)
        unrealized_pl = 0.0
        if self.unrealized_pnl and not isUnset(self.unrealized_pnl):
            unrealized_pl = float(self.unrealized_pnl)

        # Realized P&L (from real-time reqPnL if available, else 0)
        realized_pl = 0.0
        if self.realized_pnl and not isUnset(self.realized_pnl):
            realized_pl = float(self.realized_pnl)

        return EquityData(
            equity=equity,
            balance=balance,
            unrealizedPL=unrealized_pl,
            realizedPL=realized_pl,
        )

    def metainfo(self) -> AccountMetainfo:
        """Convert TrackedAccount to AccountMetainfo for account list.

        Args:
            tracked: TrackedAccount with account ID

        Returns:
            Domain AccountMetainfo model
        """
        return AccountMetainfo(
            id=self.id,
            name=self.id,  # TWS doesn't provide separate display name
            currency=self.currency or "USD",
            currencySign=self.currency_sign or "$",
        )


class AccountTracker:
    """Manages position state for IBSocket. Thread-safe via asyncio dispatch.

    Simpler than OrderTracker:
    - No orderId generation needed
    - No per-position waiting hooks
    - No fills history (positions are net aggregates)

    Thread Ownership:
        - Envelope (hooks registration, reset): main thread
        - Content (positions dict): reader thread writes, main thread reads
        - Dispatch (callbacks): reader thread schedules, main thread executes

    Usage:
        - Snapshot: reqPositions() → all_accounts() → resolve_snapshots()
        - Subscription: reqPositionsStream() → create_stream_hook() → dispatch_update()
    """

    def __init__(
        self,
        account_sub_cb: Callable[[str], int],
        account_unsub_cb: Callable[[int], None],
    ) -> None:
        self.account_sub_cb = account_sub_cb
        self.account_unsub_cb = account_unsub_cb
        self._snapshot_requested = threading.Event()
        self._snapshot_complete = threading.Event()
        self._accounts: dict[str, TrackedAccount] = {}
        self._snapshot_hooks: dict[
            str, tuple[asyncio.AbstractEventLoop, asyncio.Future[list[TrackedAccount]]]
        ] = {}
        self._stream_hooks: dict[
            str,
            tuple[
                asyncio.AbstractEventLoop,
                Callable[[TrackedAccount], Coroutine[Any, Any, None]],
                Callable[[ProviderException], Coroutine[Any, Any, None]],
            ],
        ] = {}
        # Per-account hooks for waiting on specific account updates
        self._account_hooks: dict[
            str,
            dict[str, tuple[asyncio.AbstractEventLoop, asyncio.Future[TrackedAccount]]],
        ] = {}
        self.summary_req_id: int | None = None

    # --- Account management (reader thread) ---

    def notify_hooks(self, account_id: str) -> None:
        """Notify all registered hooks with current orders.

        Called from reader thread after reconnect snapshot.
        """
        tracked = self._accounts.get(account_id)
        assert tracked is not None, "notify_hooks called for unknown account"

        def resolve_hook(future: asyncio.Future, tracked: TrackedAccount) -> None:
            if not future.done():
                future.set_result(tracked)

        for loop, future in self._account_hooks.get(tracked.id, {}).values():
            loop.call_soon_threadsafe(resolve_hook, future, tracked)
        for stream_loop, stream_callback, _ in self._stream_hooks.values():
            stream_loop.call_soon_threadsafe(
                stream_loop.create_task,
                stream_callback(tracked),
            )

    def ensure_summary_requested(self, request_cb: Callable[[], int]) -> None:
        """Ensure snapshot request is made only once."""
        if not self._snapshot_requested.is_set():
            self._snapshot_requested.set()
            self.summary_req_id = request_cb()

    def upsert_account(
        self,
        account: str,
    ) -> None:
        """Create or replace TrackedAccount from position callback.

        Called from reader thread. Stores fresh TWS objects directly.

        Args:
            account: Account ID holding the position
            contract: Fresh Contract object from decoder
            position: Position quantity (positive=long, negative=short)
            avgCost: Average cost per unit
        """
        if account in self._accounts:
            return  # Already exists

        tracked = self._accounts.setdefault(account, TrackedAccount(id=account))
        # FIXME: need to trigger subscription request from main thread
        # and pass pnl_req_id through a thread-safe callback
        tracked.pnl_req_id = self.account_sub_cb(tracked.id)
        self.notify_hooks(tracked.id)

    def update_account(
        self,
        account: str,
        tag: str,
        value: str,
        currency: str,
    ) -> None:
        """Update TrackedAccount from account callback.

        Called from reader thread. Stores fresh TWS objects directly.
        Uses TWS_TAG_TO_FIELD mapping to convert PascalCase TWS tags
        to snake_case Python field names.

        Args:
            account: Account ID holding the position
            tag: TWS PascalCase tag name (e.g., "NetLiquidation")
            value: Tag value as string
            currency: Currency of the value (may be empty for non-monetary tags)
        """
        tracked = self._accounts.setdefault(account, TrackedAccount(id=account))
        field_name = TWS_TAG_TO_FIELD.get(tag)
        if not field_name:
            # Unknown tags are common (TWS sends many more tags than we track)
            # Don't log warning for every unknown tag to avoid noise
            return

        # Parse value based on field type
        parsed_value: str | int | Decimal | bool
        if field_name == "account_ready":
            parsed_value = value.lower() == "true"
        elif field_name == "day_trades_remaining":
            parsed_value = int(value) if value.lstrip("-").isdigit() else -1
        elif field_name in ("currency", "account_type"):
            parsed_value = value
        else:
            # Numeric fields (Decimal) - handle edge cases
            try:
                parsed_value = Decimal(value) if value else Decimal(0)
            except Exception:
                parsed_value = Decimal(0)

        setattr(tracked, field_name, parsed_value)

        # Update currency from the callback (only if provided)
        if currency:
            tracked.currency = currency

        self.notify_hooks(tracked.id)

    def update_pnl(
        self,
        reqId: int,
        daily: float,
        unrealized: float,
        realized: float,
    ) -> None:
        """Update P&L fields from pnl() callback.

        Called from reader thread. Updates daily_pnl, unrealized_pnl, realized_pnl
        on the tracked account associated with this reqId.

        Args:
            reqId: Request ID from reqPnL()
            daily: Daily P&L
            unrealized: Unrealized P&L
            realized: Realized P&L
        """
        # Look up account from P&L subscription registry
        tracked: TrackedAccount = next(
            iter(
                [
                    account
                    for account in self._accounts.values()
                    if account.pnl_req_id == reqId
                ]
            )
        )

        tracked.daily_pnl = Decimal(str(daily))
        tracked.unrealized_pnl = Decimal(str(unrealized))
        tracked.realized_pnl = Decimal(str(realized))

        self.notify_hooks(tracked.id)

    def raise_error(self, exception: ProviderException) -> None:
        """Dispatch error to all hooks.

        Called from reader thread.
        """
        # Dispatch to snapshot hooks
        for snapshot_loop, snapshot_future in self._snapshot_hooks.values():

            def resolve_snapshot_error(
                future: asyncio.Future, exc: ProviderException
            ) -> None:
                if not future.done():
                    future.set_exception(exc)

            snapshot_loop.call_soon_threadsafe(
                resolve_snapshot_error, snapshot_future, exception
            )

        # Dispatch to stream hooks
        for stream_loop, _, on_error in self._stream_hooks.values():
            stream_loop.call_soon_threadsafe(
                stream_loop.create_task,
                on_error(exception),
            )

    def mark_snapshot_complete(self) -> None:
        """Mark snapshot as complete. Called from positionEnd."""
        self._snapshot_complete.set()

        for loop, future in self._snapshot_hooks.values():

            def resolve_hook(
                future: asyncio.Future, positions: list[TrackedAccount]
            ) -> None:
                if not future.done():
                    future.set_result(positions)

            loop.call_soon_threadsafe(
                resolve_hook, future, list(self._accounts.values())
            )

    # --- Position registrations (main thread) ---

    def reset(self) -> None:
        """Full reset - like fresh creation.

        Clears all positions, snapshot state, and hooks.
        Called from main thread before new snapshot request.
        """
        self._accounts.clear()
        self._snapshot_requested.clear()
        self._snapshot_complete.clear()
        self._snapshot_hooks.clear()
        self._stream_hooks.clear()

    async def all_accounts(self, timeout: float | None = None) -> list[TrackedAccount]:
        """Get all positions, waiting for snapshot if needed.

        Called from main thread. If snapshot is already complete,
        resolves immediately.

        Args:
            timeout: Optional timeout in seconds

        Returns:
            List of TrackedAccount objects
        """
        loop = asyncio.get_running_loop()
        future: asyncio.Future[list[TrackedAccount]] = loop.create_future()

        if self._snapshot_complete.is_set():
            future.set_result(list(self._accounts.values()))
            return await asyncio.wait_for(future, timeout)

        key = str(uuid.uuid4())
        self._snapshot_hooks[key] = (loop, future)

        try:
            return await asyncio.wait_for(future, timeout)
        finally:
            self._snapshot_hooks.pop(key, None)

    def create_stream_hook(
        self,
        loop: asyncio.AbstractEventLoop,
        callback: Callable[[TrackedAccount], Coroutine[Any, Any, None]],
        on_error: Callable[[ProviderException], Coroutine[Any, Any, None]],
    ) -> str:
        """Register callback for position updates.

        Called from main thread.

        Args:
            loop: Event loop for callbacks
            callback: Called for each position update
            on_error: Error callback

        Returns:
            Unique key for unsubscription
        """
        key = str(uuid.uuid4())
        self._stream_hooks[key] = (loop, callback, on_error)
        return key

    def remove_stream_hook(self, key: str) -> None:
        """Unregister position update callback."""
        self._stream_hooks.pop(key, None)
