"""Quote tracking for TWS datafeed integration.

Tracks real-time market data (quotes) from TWS tick callbacks. Provides both
snapshot and streaming patterns for quote data consumption.

Thread Safety:
    - TrackedQuote objects are updated from the reader thread via IBSocket callbacks
    - Snapshot/stream hooks are dispatched to the main thread via asyncio event loops
    - Main thread consumers register hooks and receive updates asynchronously
"""

import asyncio
import logging
import os
import threading
import time
import uuid
from collections.abc import Callable, Coroutine
from typing import Any

from ibapi.contract import Contract

from trading_api.models.exceptions import ProviderException
from trading_api.models.market import QuoteData, QuoteValues
from trading_api.providers.tws.cached_contract import CachedContract

logger = logging.getLogger(__name__)

DEBUG_TWS_DATAFEED = os.environ.get("DEBUG_TWS_DATAFEED") == "true"


def _parse_rt_volume(rt_volume_str: str | None) -> tuple[float, int, float]:
    """Parse RT Trade Volume string to extract last price, volume, and vwap.

    Format: "price;size;timestamp;totalVolume;vwap;singleMM"
    Example: "320.64;1.0;1765200318856;363.0;320.359;true"

    Args:
        rt_volume_str: RT Volume or RT Trade Volume string from TWS

    Returns:
        Tuple of (last_price, total_volume, vwap) - returns (0.0, 0, 0.0) if parsing fails
    """
    if not rt_volume_str or rt_volume_str.startswith(";"):
        # Empty string or starts with ";" (odd lot with no price)
        return 0.0, 0, 0.0

    parts = rt_volume_str.split(";")
    if len(parts) >= 5:
        last_price = float(parts[0]) if parts[0] else 0.0
        total_volume = int(float(parts[3])) if parts[3] else 0
        vwap = float(parts[4]) if parts[4] else 0.0
        return last_price, total_volume, vwap

    return 0.0, 0, 0.0


class TrackedQuote:
    """Tracks real-time quote data from TWS tick callbacks.

    Stores tick values as explicit attributes mapped from TICK_TYPE_TO_FIELD.
    Supports both snapshot (one-time fetch) and streaming (continuous updates) patterns.

    Thread Safety:
        - Updated by reader thread via update() method
        - Hooks dispatched to main thread via asyncio event loops
        - Main thread consumers should not mutate these objects

    Attributes:
        cached_contract: CachedContract with ticker name and contract details
        req_id: TWS request ID for this quote subscription
        last_update: Timestamp of most recent tick update
    """

    # All tick field attributes (from TICK_TYPE_TO_FIELD values)
    __slots__ = (
        # Core identifiers
        "cached_contract",
        "req_id",
        "last_update",
        # Core prices
        "bid",
        "ask",
        "last",
        "high",
        "low",
        "close",
        "open",
        # Core sizes
        "bid_size",
        "ask_size",
        "last_size",
        "volume",
        # Historical ranges
        "low_13_week",
        "high_13_week",
        "low_26_week",
        "high_26_week",
        "low_52_week",
        "high_52_week",
        "avg_volume",
        # Options
        "open_interest",
        "option_historical_vol",
        "option_implied_vol",
        "option_bid_exch",
        "option_ask_exch",
        "option_call_open_interest",
        "option_put_open_interest",
        "option_call_volume",
        "option_put_volume",
        # Index/futures
        "index_future_premium",
        # Exchange info
        "bid_exch",
        "ask_exch",
        # Auction
        "auction_volume",
        "auction_price",
        "auction_imbalance",
        # Mark price
        "mark_price",
        # Timestamp
        "last_timestamp",
        # Shortability
        "shortable",
        "shortable_shares",
        # Fundamental
        "fundamental_ratios",
        # Real-time volume
        "rt_volume",
        "rt_trd_volume",
        # Trading status
        "halted",
        # Yield
        "bid_yield",
        "ask_yield",
        "last_yield",
        # Trade stats
        "trade_count",
        "trade_rate",
        "volume_rate",
        "last_rth_trade",
        # Volatility
        "rt_historical_vol",
        # Dividends
        "ib_dividends",
        # Bond
        "bond_factor_multiplier",
        # Regulatory
        "regulatory_imbalance",
        # News
        "news_tick",
        # Short-term volume
        "short_term_volume_3_min",
        "short_term_volume_5_min",
        "short_term_volume_10_min",
        # Delayed data
        "delayed_bid",
        "delayed_ask",
        "delayed_last",
        "delayed_bid_size",
        "delayed_ask_size",
        "delayed_last_size",
        "delayed_high",
        "delayed_low",
        "delayed_volume",
        "delayed_close",
        "delayed_open",
        "delayed_last_timestamp",
        "delayed_halted",
        # Credit manager
        "creditman_mark_price",
        "creditman_slow_mark_price",
        # Exchange
        "last_exch",
        "last_reg_time",
        # Futures
        "futures_open_interest",
        # Options avg volume
        "avg_opt_volume",
        # ETF NAV
        "etf_nav_close",
        "etf_nav_prior_close",
        "etf_nav_bid",
        "etf_nav_ask",
        "etf_nav_last",
        "etf_frozen_nav_last",
        "etf_nav_high",
        "etf_nav_low",
        # Social
        "social_market_analytics",
        # IPO
        "estimated_ipo_midpoint",
        "final_ipo_last",
        # Delayed yield
        "delayed_yield_bid",
        "delayed_yield_ask",
        # OHLC bar data (from realtime bars)
        "bar_open",
        "bar_high",
        "bar_low",
        "bar_close",
        "bar_volume",
        "bar_wap",
        "bar_count",
        "snapshot_complete",
    )

    def __init__(
        self,
        contract: CachedContract,
        req_id: int,
    ) -> None:
        """Initialize TrackedQuote with contract and request ID.

        Args:
            contract: CachedContract with ticker name and contract details
            req_id: TWS request ID for quote data subscription
        """
        self.cached_contract: CachedContract = contract
        self.req_id: int = req_id
        self.last_update: float = time.time()

        # Initialize all tick fields to None
        self.bid: float | None = None
        self.ask: float | None = None
        self.last: float | None = None
        self.high: float | None = None
        self.low: float | None = None
        self.close: float | None = None
        self.open: float | None = None
        self.bid_size: int | None = None
        self.ask_size: int | None = None
        self.last_size: int | None = None
        self.volume: int | None = None
        self.low_13_week: float | None = None
        self.high_13_week: float | None = None
        self.low_26_week: float | None = None
        self.high_26_week: float | None = None
        self.low_52_week: float | None = None
        self.high_52_week: float | None = None
        self.avg_volume: int | None = None
        self.open_interest: int | None = None
        self.option_historical_vol: float | None = None
        self.option_implied_vol: float | None = None
        self.option_bid_exch: str | None = None
        self.option_ask_exch: str | None = None
        self.option_call_open_interest: int | None = None
        self.option_put_open_interest: int | None = None
        self.option_call_volume: int | None = None
        self.option_put_volume: int | None = None
        self.index_future_premium: float | None = None
        self.bid_exch: str | None = None
        self.ask_exch: str | None = None
        self.auction_volume: int | None = None
        self.auction_price: float | None = None
        self.auction_imbalance: int | None = None
        self.mark_price: float | None = None
        self.last_timestamp: str | None = None
        self.shortable: float | None = None
        self.shortable_shares: int | None = None
        self.fundamental_ratios: str | None = None
        self.rt_volume: str | None = None
        self.rt_trd_volume: str | None = None
        self.halted: int | None = None
        self.bid_yield: float | None = None
        self.ask_yield: float | None = None
        self.last_yield: float | None = None
        self.trade_count: int | None = None
        self.trade_rate: float | None = None
        self.volume_rate: float | None = None
        self.last_rth_trade: float | None = None
        self.rt_historical_vol: float | None = None
        self.ib_dividends: str | None = None
        self.bond_factor_multiplier: float | None = None
        self.regulatory_imbalance: int | None = None
        self.news_tick: str | None = None
        self.short_term_volume_3_min: int | None = None
        self.short_term_volume_5_min: int | None = None
        self.short_term_volume_10_min: int | None = None
        self.delayed_bid: float | None = None
        self.delayed_ask: float | None = None
        self.delayed_last: float | None = None
        self.delayed_bid_size: int | None = None
        self.delayed_ask_size: int | None = None
        self.delayed_last_size: int | None = None
        self.delayed_high: float | None = None
        self.delayed_low: float | None = None
        self.delayed_volume: int | None = None
        self.delayed_close: float | None = None
        self.delayed_open: float | None = None
        self.delayed_last_timestamp: str | None = None
        self.delayed_halted: int | None = None
        self.creditman_mark_price: float | None = None
        self.creditman_slow_mark_price: float | None = None
        self.last_exch: str | None = None
        self.last_reg_time: str | None = None
        self.futures_open_interest: int | None = None
        self.avg_opt_volume: int | None = None
        self.etf_nav_close: float | None = None
        self.etf_nav_prior_close: float | None = None
        self.etf_nav_bid: float | None = None
        self.etf_nav_ask: float | None = None
        self.etf_nav_last: float | None = None
        self.etf_frozen_nav_last: float | None = None
        self.etf_nav_high: float | None = None
        self.etf_nav_low: float | None = None
        self.social_market_analytics: str | None = None
        self.estimated_ipo_midpoint: float | None = None
        self.final_ipo_last: float | None = None
        self.delayed_yield_bid: float | None = None
        self.delayed_yield_ask: float | None = None
        # Bar data fields
        self.bar_open: float | None = None
        self.bar_high: float | None = None
        self.bar_low: float | None = None
        self.bar_close: float | None = None
        self.bar_volume: int | None = None
        self.bar_wap: float | None = None
        self.bar_count: int | None = None

        self.snapshot_complete: threading.Event = threading.Event()

    @property
    def is_live(self) -> bool:
        """Check if quote is receiving recent updates.

        A quote is considered live if it has received an update
        within the last 5 seconds.
        """
        return (time.time() - self.last_update) <= 5.0

    @property
    def is_ready(self) -> bool:
        """Check if quote has minimum required data for snapshot resolution.

        A quote is considered ready when it has bid, ask, and last price.
        For some instruments (forex, indices), not all may be available -
        this can be extended to check delayed data as fallback.
        """
        if not self.is_live:
            return False

        if self.snapshot_complete.is_set():
            return True

        # Check real-time data first
        if self.bid is not None and self.ask is not None:
            return True
        # Fallback to delayed data
        if self.delayed_bid is not None and self.delayed_ask is not None:
            return True
        return False

    def update(self, updates: dict[str, int | float | str]) -> None:
        """Apply tick updates and notify hooks.

        Called from reader thread. Updates attributes and dispatches
        to snapshot/stream hooks on their respective event loops.

        Args:
            updates: Dict of field_name -> value from tick callbacks
        """
        self.last_update = time.time()

        # Apply updates to attributes
        for field_name, value in updates.items():
            if field_name == "snapshot_complete":
                self.snapshot_complete.set()
            elif hasattr(self, field_name):
                setattr(self, field_name, value)

    def to_domain(self) -> QuoteData:
        """Convert TrackedQuote to domain QuoteData model.

        Uses fallback chain for values:
        1. Real-time tick data (bid, ask, last, etc.)
        2. RT Trade Volume parsed data
        3. Delayed data
        4. Zero/defaults

        Returns:
            QuoteData model for API response
        """
        contract = self.cached_contract.contract
        symbol = contract.symbol
        exchange = contract.exchange or contract.primaryExchange or "SMART"

        # Parse RT Trade Volume as fallback source (more reliable than rt_volume)
        rt_trd_volume = self.rt_trd_volume or self.rt_volume
        rt_last, rt_volume, _ = _parse_rt_volume(rt_trd_volume)

        # Use real-time data with delayed fallback
        bid = self.bid if self.bid is not None else (self.delayed_bid or 0.0)
        ask = self.ask if self.ask is not None else (self.delayed_ask or 0.0)
        last = (
            self.last
            if self.last is not None
            else (self.delayed_last or rt_last or 0.0)
        )

        # OHLC data - prefer bar data, fall back to tick data, then last price
        open_price = self.bar_open or self.open or self.delayed_open or last
        high_price = self.bar_high or self.high or self.delayed_high or last
        low_price = self.bar_low or self.low or self.delayed_low or last
        close_price = self.bar_close or self.close or self.delayed_close or last

        # Volume from bar data or tick data
        volume = self.bar_volume or self.volume or self.delayed_volume or rt_volume or 0

        # Round values for display
        bid = round(bid, 2)
        ask = round(ask, 2)
        last = round(last, 2)
        open_price = round(open_price, 2)
        high_price = round(high_price, 2)
        low_price = round(low_price, 2)
        close_price = round(close_price, 2)

        # Calculate spread
        spread = round(ask - bid, 2) if (ask > 0 and bid > 0) else 0.0

        # Calculate change and change percent (from previous close)
        if last > 0 and close_price > 0:
            change = round(last - close_price, 2)
            change_percent = round((change / close_price) * 100, 2)
        else:
            change = 0.0
            change_percent = 0.0

        quote_values = QuoteValues(
            lp=last,
            ask=ask,
            bid=bid,
            spread=spread,
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            prev_close_price=close_price,
            volume=int(volume),
            ch=change,
            chp=change_percent,
            short_name=symbol,
            exchange=exchange,
            description=f"Quote for {symbol}",
            original_name=symbol,
        )

        return QuoteData(s="ok", n=self.cached_contract.ticker, v=quote_values)


def resolve_snapshot(fut: asyncio.Future[QuoteData], quote: TrackedQuote) -> None:
    if not fut.done():
        fut.set_result(quote.to_domain())


def reject_snapshot(fut: asyncio.Future[QuoteData], exc: ProviderException) -> None:
    if not fut.done():
        fut.set_exception(exc)


async def dispatch_update(
    callback: Callable[[QuoteData], Coroutine[Any, Any, None]],
    quote: TrackedQuote,
) -> None:
    await callback(quote.to_domain())


class QuoteTracker:
    """Manages quote subscriptions and dispatches tick updates to TrackedQuotes.

    Provides a unified interface for quote data access:
    - Snapshot pattern: Get current quote data, waiting if needed
    - Streaming pattern: Subscribe to continuous quote updates

    The tracker maintains a mapping from tickers to TrackedQuotes and
    handles TWS request ID allocation for new quote subscriptions.

    Thread Safety:
        - Lookup methods (_get_or_create_quote, snapshot): main thread
        - Update methods (update, raise_error): reader thread via IBSocket callbacks
        - Subscription management: main thread

    Usage:
        tracker = QuoteTracker(ibsocket)

        # Snapshot pattern
        quote_data = await tracker.snapshot(cached_contract)

        # Streaming pattern
        key = tracker.subscribe(cached_contract, on_update, on_error)
        # ... receive updates via on_update callback ...
        tracker.unsubscribe(key)
    """

    def __init__(
        self,
        quote_request_hook: Callable[[Contract], int],
        quote_cancel_hook: Callable[[int], None],
        timeout: float = 11.0,
    ) -> None:
        """Initialize QuoteTracker.

        Args:
            quote_request_hook: Callable to request a quote given a Contract
            quote_cancel_hook: Callable to cancel a quote given a request ID
            timeout: Default timeout in seconds for snapshot requests
        """
        self.tracker_lock = threading.Lock()
        self._quote_request_hook = quote_request_hook
        self._quote_cancel_hook = quote_cancel_hook
        self._timeout = timeout

        # shared quote storage
        self._quotes: dict[int, TrackedQuote] = {}  # req_id -> TrackedQuote
        self._requests: dict[str, int] = {}  # ticker_name -> req_id

        # shared hook storage
        self._snapshot_hooks: dict[
            int, dict[str, tuple[asyncio.AbstractEventLoop, asyncio.Future[QuoteData]]]
        ] = {}
        self._stream_hooks: dict[
            int,
            dict[
                str,
                tuple[
                    asyncio.AbstractEventLoop,
                    Callable[[QuoteData], Coroutine[Any, Any, None]],
                    Callable[[ProviderException], Coroutine[Any, Any, None]],
                ],
            ],
        ] = {}

    def _quote_in_use(self, req_id: int) -> bool:
        """Check if a TrackedQuote has any active snapshot or stream hooks."""
        in_use = bool(
            self._snapshot_hooks.get(req_id, {}) or self._stream_hooks.get(req_id, {})
        )
        return in_use

    def _get_or_create_quote(self, cached: CachedContract) -> TrackedQuote:
        """Get existing quote or create new TWS subscription.

        If a quote for this ticker already exists, returns it.
        Otherwise, allocates a new request ID, creates a TrackedQuote,
        and initiates a TWS market data request.

        Args:
            cached: CachedContract with ticker name and resolved contract

        Returns:
            TrackedQuote for the ticker (existing or newly created)
        """
        req_id = self._requests.get(cached.ticker)
        if req_id is None:
            best_contract = cached.build_best_contract()
            if DEBUG_TWS_DATAFEED:
                logger.info(
                    f"Requesting new quote for {cached.ticker}@{best_contract.exchange}"
                )
            req_id = self._quote_request_hook(best_contract)
            self._requests[cached.ticker] = req_id

            self._quotes[req_id] = TrackedQuote(cached, req_id)

            if DEBUG_TWS_DATAFEED:
                logger.info(f"active quotes: [{list(self._requests.keys())}]")

        quote = self._quotes.get(req_id)
        assert quote is not None, "quote should exist after requesting quote"
        return quote

    def _debounce_cancel_quote_data(self, req_id: int) -> None:
        """Debounce unsubscribe - remove quote if no active subscriptions."""

        def debounce_cancel(req_id: int) -> None:
            with self.tracker_lock:
                quote = self._quotes.get(req_id)
                if quote is None:
                    if DEBUG_TWS_DATAFEED:
                        logger.info(
                            f"debounce_cancel: No quote found for req_id {req_id}"
                        )
                    return
                if not self._quote_in_use(req_id):
                    self._requests.pop(quote.cached_contract.ticker, None)
                    self._quote_cancel_hook(req_id)
                    self._quotes.pop(req_id, None)
                elif DEBUG_TWS_DATAFEED:
                    logger.info(
                        f"debounce_cancel: Quote for req_id {req_id} still in use {quote.cached_contract.ticker}, "
                        f"snapshot_hooks={[key[-12:] for key in self._snapshot_hooks.get(req_id, {}).keys()]}, "
                        f"stream_hooks={[key[-12:] for key in self._stream_hooks.get(req_id, {}).keys()]}"
                    )
                if DEBUG_TWS_DATAFEED:
                    logger.info(f"remaining quotes: {list(self._requests.keys())}")

        asyncio.get_running_loop().call_later(1.0, debounce_cancel, req_id)

    # === Lookup Methods (main thread) ===

    async def request(
        self, cached: CachedContract, timeout: float | None = None
    ) -> QuoteData:
        """Get quote data for a contract, waiting for data if needed.

        Creates a TWS subscription if needed, waits for minimum quote data
        (bid/ask/last), and returns the quote as a domain model.

        Args:
            cached: CachedContract with ticker name and resolved contract
            timeout: Optional timeout override (uses default if not specified)

        Returns:
            QuoteData domain model with quote values

        Raises:
            asyncio.TimeoutError: If quote data not received within timeout
            ProviderException: If TWS returns an error for this request
        """
        key = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        future: asyncio.Future[QuoteData] = loop.create_future()

        with self.tracker_lock:
            quote = self._get_or_create_quote(cached)
            quote_snapshot_hooks = self._snapshot_hooks.setdefault(quote.req_id, {})
            quote_snapshot_hooks[key] = (loop, future)
            if DEBUG_TWS_DATAFEED:
                logger.info(
                    f"Registered snapshot hook for {cached.ticker} "
                    f"(req_id {quote.req_id}) => {key}"
                )

        # Resolve immediately if already ready
        if quote.is_ready:
            future.set_result(quote.to_domain())

        try:
            return await asyncio.wait_for(future, timeout=timeout or self._timeout)
        finally:
            with self.tracker_lock:
                quote_snapshot_hooks = self._snapshot_hooks.setdefault(quote.req_id, {})
                quote_snapshot_hooks.pop(key, None)
            if DEBUG_TWS_DATAFEED:
                logger.info(
                    f"Unregistered snapshot hook for {cached.ticker} "
                    f"(req_id {quote.req_id}) => {key}"
                )
            self._debounce_cancel_quote_data(quote.req_id)

    # === Subscription Methods (main thread) ===

    def subscribe(
        self,
        cached: CachedContract,
        on_update: Callable[[QuoteData], Coroutine[Any, Any, None]],
        on_error: Callable[[ProviderException], Coroutine[Any, Any, None]],
    ) -> str:
        """Subscribe to streaming quote updates for a contract.

        Creates a TWS subscription if needed and registers callbacks
        for continuous quote updates.

        Args:
            cached: CachedContract with ticker name and resolved contract
            on_update: Async callback invoked on each quote update
            on_error: Async callback invoked on error

        Returns:
            Subscription key for unsubscribe()
        """
        key = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        with self.tracker_lock:
            quote = self._get_or_create_quote(cached)
            quote_stream_hooks = self._stream_hooks.setdefault(quote.req_id, {})
            quote_stream_hooks[key] = (loop, on_update, on_error)
            if DEBUG_TWS_DATAFEED:
                logger.info(
                    f"Registered stream hook for {cached.ticker} "
                    f"(req_id {quote.req_id}) => {key}"
                )
        sub_key = f"{cached.ticker}#{key}"
        return sub_key

    def unsubscribe(self, sub_key: str) -> None:
        """Remove a quote subscription.

        Removes the subscription callback. If no more subscribers remain
        for a quote, the TWS market data request can optionally be cancelled
        (not implemented - quotes remain active for reuse).

        Args:
            sub_key: Subscription key from subscribe()
        """
        if "#" not in sub_key:
            return
        ticker, sub_key = sub_key.split("#", 1)

        with self.tracker_lock:
            req_id = self._requests.get(ticker)
            if req_id is None:
                return
            quote_stream_hooks = self._stream_hooks.get(req_id)
            if quote_stream_hooks is not None:
                quote_stream_hooks.pop(sub_key, None)

        if DEBUG_TWS_DATAFEED:
            logger.info(
                f"Unsubscribing from quote stream for "
                f"{ticker} (req_id {req_id}) => {sub_key}"
            )

        self._debounce_cancel_quote_data(req_id)

    # === Update Methods (reader thread via callbacks) ===

    def update(self, req_id: int, updates: dict[str, int | float | str]) -> None:
        """Apply tick updates to a TrackedQuote.

        Called from reader thread via IBSocket tick callbacks.
        Dispatches updates to the TrackedQuote which notifies its hooks.

        Args:
            req_id: TWS request ID from tick callback
            updates: Dict of field_name -> value from tick data
        """

        # with self.tracker_lock: <- disabled for performance
        quote = self._quotes.get(req_id)

        if quote is None:
            logger.warning(f"Received tick update for unknown req_id {req_id}")
            return
        quote.update(updates)

        quote_snapshot_hooks = list(self._snapshot_hooks.get(req_id, {}).values())
        quote_stream_hooks = list(self._stream_hooks.get(req_id, {}).values())

        # If no longer used, debounce cancel
        if not (quote_snapshot_hooks or quote_stream_hooks):
            logger.warning(
                f"update: Unused quote subscription for req_id "
                f"{req_id} --> {quote.cached_contract.ticker}"
            )
            return

        # Resolve snapshot hooks if ready
        if quote.is_ready:
            for loop, future in quote_snapshot_hooks:
                loop.call_soon_threadsafe(resolve_snapshot, future, quote)

        # Dispatch to stream hooks
        for loop, callback, _ in quote_stream_hooks:
            loop.call_soon_threadsafe(
                loop.create_task,
                dispatch_update(callback, quote),
            )

    def raise_error(self, req_id: int, exception: ProviderException) -> bool:
        """Dispatch error to a TrackedQuote's hooks.

        Called from reader thread when TWS reports an error for a quote request.

        Args:
            req_id: TWS request ID for the failed request
            exception: ProviderException to propagate to hooks
        """
        # with self.tracker_lock:  <- disabled for performance
        quote = self._quotes.get(req_id)

        if quote is None:
            logger.warning(f"Received error for unknown req_id {req_id}")
            return False

        quote_snapshot_hooks = list(self._snapshot_hooks.get(req_id, {}).values())
        quote_stream_hooks = list(self._stream_hooks.get(req_id, {}).values())

        # If no longer used, debounce cancel
        if not (quote_snapshot_hooks or quote_stream_hooks):
            logger.warning(
                f"raise_error: Unused quote subscription for req_id "
                f"{req_id} --> {quote.cached_contract.ticker}"
            )
            return True

        # Dispatch to snapshot hooks
        for loop, future in quote_snapshot_hooks:
            loop.call_soon_threadsafe(reject_snapshot, future, exception)

        # Dispatch to stream hooks
        for loop, _, on_error in quote_stream_hooks:
            loop.call_soon_threadsafe(
                loop.create_task,
                on_error(exception),
            )
        return True

    # === Session Management ===

    def reset(self) -> None:
        """Full reset - clear all quotes and subscriptions.

        Called when connection is lost or tracker needs reinitialization.
        Does not cancel TWS requests (connection may be down).
        """
        self._quotes.clear()
        self._snapshot_hooks.clear()
        self._stream_hooks.clear()
        self._requests.clear()
