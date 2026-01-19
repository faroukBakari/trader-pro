"""Bar tracking for TWS datafeed integration.

Tracks historical and real-time bar data (OHLCV) from TWS historicalData callbacks.
Provides both snapshot and streaming patterns for bar data consumption.

Thread Safety:
    - BarsRequest objects are updated from the reader thread via IBSocket callbacks
    - Snapshot/stream hooks are dispatched to the main thread via asyncio event loops
    - Main thread consumers register hooks and receive updates asynchronously
"""

import asyncio
import logging
import os
import re
import threading
import time as time_
import uuid
from collections.abc import Callable, Coroutine
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from ibapi.common import BarData
from ibapi.contract import Contract

from trading_api.models.exceptions import ProviderException
from trading_api.models.market import Bar

logger = logging.getLogger(__name__)

DEBUG_TWS_DATAFEED = os.environ.get("DEBUG_TWS_DATAFEED") == "true"

# Default cache location
DEFAULT_CACHE_PATH = ".cache/bars.db"

# Bar finalization threshold - bars older than this are considered finalized
BAR_FINALIZATION_THRESHOLD_SECONDS = 120.0


# ============================================================================
# Date Parsing Utilities
# ============================================================================

# Regex: "YYYYMMDD<1-2 spaces>HH:MM:SS <timezone>"
_TWS_DATE_TZ_PATTERN = re.compile(r"^(\d{8})\s{1,2}(\d{2}:\d{2}:\d{2})\s+(.+)$")


def parse_tws_bar_date_as_datetime(date_str: str) -> datetime:
    """Parse TWS bar date string to timezone-aware datetime.

    Handles multiple TWS date formats:
    - "yyyyMMdd  HH:mm:ss <timezone>" (1-2 spaces, any timezone like US/Eastern)
    - "yyyyMMdd" (daily bars, date only - returns UTC midnight)
    - epoch string (if formatDate=2 was used - returns UTC)

    Args:
        date_str: TWS date string

    Returns:
        Timezone-aware datetime

    Raises:
        ProviderException: If date format is unrecognized
    """
    date_str = date_str.strip()

    # 1. Try datetime with timezone (US/Eastern, US/Central, UTC, etc.)
    if match := _TWS_DATE_TZ_PATTERN.match(date_str):
        date_part, time_part, tz_name = match.groups()
        dt_naive = datetime.strptime(f"{date_part} {time_part}", "%Y%m%d %H:%M:%S")
        return dt_naive.replace(tzinfo=ZoneInfo(tz_name))

    # 2. Try daily bar format (date only, 8 digits) - assume UTC
    if len(date_str) == 8 and date_str.isdigit():
        dt_naive = datetime.strptime(date_str, "%Y%m%d")
        return dt_naive.replace(tzinfo=ZoneInfo("UTC"))

    # 3. Try epoch format (formatDate=2) - interpret as UTC
    if date_str.isdigit():
        return datetime.fromtimestamp(int(date_str), tz=ZoneInfo("UTC"))

    # 4. Unrecognized format
    raise ProviderException(
        provider="tws",
        capability="datafeed",
        code="PROVIDER_TWS_INVALID_DATE_FORMAT",
        message=f"Cannot parse TWS bar date: '{date_str}'",
    )


# ============================================================================
# Bar Size String Parsing
# ============================================================================

_BAR_SIZE_PATTERN = re.compile(
    r"^(\d+)\s+(sec|secs|min|mins|hour|hours|day|week|month)s?$", re.IGNORECASE
)

_UNIT_TO_KWARG = {
    "sec": "seconds",
    "secs": "seconds",
    "min": "minutes",
    "mins": "minutes",
    "hour": "hours",
    "hours": "hours",
    "day": "days",
    "week": "weeks",
    "month": "days",  # months → days * 30 (approximation)
}


def bar_size_str_to_timedelta(bar_size_str: str) -> timedelta:
    """Parse TWS bar size string to timedelta.

    Examples: "1 min", "5 mins", "1 hour", "1 day", "1 month"

    Args:
        bar_size_str: TWS bar size string (e.g., "5 mins", "1 hour")

    Returns:
        timedelta representing the bar duration

    Raises:
        ValueError: If bar size format is invalid
    """
    match = _BAR_SIZE_PATTERN.match(bar_size_str.strip())
    if not match:
        raise ValueError(f"Invalid bar size format: '{bar_size_str}'")

    value, unit = int(match.group(1)), match.group(2).lower()
    kwarg = _UNIT_TO_KWARG[unit]

    # Special case: month approximation (30 days)
    if unit == "month":
        value *= 30

    return timedelta(**{kwarg: value})


class SmartTwsBar:
    """In-memory bar representation with timezone-aware datetime.

    Provides:
    - to_domain() → converts to Bar (int ms for TradingView compatibility)
    - to_dict() / from_dict() → SQLite serialization (unix seconds)
    - update_from_bardata() → live bar updates with OHLCV merge logic
    - is_finalized() → checks if bar is no longer being updated
    """

    __slots__ = ("time", "open", "high", "low", "close", "volume", "_updated_at")

    def __init__(
        self,
        time: datetime,
        open: float,
        high: float,
        low: float,
        close: float,
        volume: float,
    ) -> None:
        """Initialize a SmartTwsBar.

        Args:
            time: Timezone-aware datetime for the bar
            open: Open price
            high: High price
            low: Low price
            close: Close price
            volume: Volume traded
        """
        self.time: datetime = time
        self.open: float = open
        self.high: float = high
        self.low: float = low
        self.close: float = close
        self.volume: float = volume
        self._updated_at: float = time_.time()

    @classmethod
    def from_bar_data(cls, bar_data: BarData) -> "SmartTwsBar":
        """Create SmartTwsBar from TWS BarData.

        Args:
            bar_data: TWS BarData object

        Returns:
            SmartTwsBar instance
        """
        return cls(
            time=parse_tws_bar_date_as_datetime(bar_data.date),
            open=float(bar_data.open),
            high=float(bar_data.high),
            low=float(bar_data.low),
            close=float(bar_data.close),
            volume=float(bar_data.volume),
        )

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"SmartTwsBar(time={self.time.isoformat()}, "
            f"O={self.open:.2f}, H={self.high:.2f}, L={self.low:.2f}, "
            f"C={self.close:.2f}, V={int(self.volume)})"
        )

    def __eq__(self, other: object) -> bool:
        """Equality based on time and OHLCV values."""
        if not isinstance(other, SmartTwsBar):
            return NotImplemented
        return (
            self.time == other.time
            and self.open == other.open
            and self.high == other.high
            and self.low == other.low
            and self.close == other.close
            and self.volume == other.volume
        )

    def to_domain(self) -> Bar:
        """Convert to domain Bar model.

        Returns:
            Bar with time as milliseconds timestamp (TradingView format)
        """
        return Bar(
            time=int(self.time.timestamp() * 1000),
            open=self.open,
            high=self.high,
            low=self.low,
            close=self.close,
            volume=int(self.volume),
            count=None,  # TWS doesn't provide count in historical bars
        )

    def to_dict(self) -> dict[str, int | float]:
        """Serialize to dict for SQLite storage.

        Returns:
            Dict with time as unix seconds and OHLCV values
        """
        return {
            "time": int(self.time.timestamp()),  # Unix seconds
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": int(self.volume),
        }

    @classmethod
    def from_dict(
        cls, data: dict[str, int | float], tz: ZoneInfo | None = None
    ) -> "SmartTwsBar":
        """Deserialize from SQLite row dict.

        Args:
            data: Dict with time (unix seconds) and OHLCV values
            tz: Timezone to apply (defaults to UTC)

        Returns:
            SmartTwsBar instance
        """
        tz = tz or ZoneInfo("UTC")
        return cls(
            time=datetime.fromtimestamp(int(data["time"]), tz=tz),
            open=float(data["open"]),
            high=float(data["high"]),
            low=float(data["low"]),
            close=float(data["close"]),
            volume=float(data["volume"]),
        )

    def update_from_bardata(self, bar_data: BarData) -> None:
        """Update bar from live BarData (streaming updates).

        Merge logic:
        - Open: kept from original bar
        - High: max of current and new
        - Low: min of current and new
        - Close: always replaced with latest
        - Volume: replaced with latest (TWS sends cumulative)

        Args:
            bar_data: New bar data from TWS live update
        """
        self.high = max(self.high, float(bar_data.high))
        self.low = min(self.low, float(bar_data.low))
        self.close = float(bar_data.close)
        self.volume = float(bar_data.volume)
        self._updated_at = time_.time()

    def is_final(self) -> bool:
        """Check if bar is finalized (no longer being updated).

        A bar is considered finalized if it hasn't been updated
        for BAR_FINALIZATION_THRESHOLD_SECONDS (e.g., 2 minutes).

        Returns:
            True if bar is finalized
        """
        return (time_.time() - self._updated_at) > BAR_FINALIZATION_THRESHOLD_SECONDS


def compute_description(
    contract: Contract,
    bar_size: str,
    end_date_time: str | None,
    duration_str: str | None,
) -> str:
    """Compute human-readable description for a bar request.

    Args:
        contract: Contract to fetch bars for
        bar_size: TWS bar size string (e.g., "5 mins")
        end_date_time: End datetime for historical request
        duration_str: Duration string (e.g., "1 D")

    Returns:
        Description string
    """
    return (
        f"{contract.exchange}>{contract.symbol}:"
        f"{contract.primaryExchange or contract.exchange}@{bar_size} "
        f"{duration_str or ''}-{end_date_time or ''}"
    )


class BarsRequest:
    """Single bar data request lifecycle.

    Tracks one TWS historical data request from creation through completion/failure.
    Accumulates bars via upsert() and resolves when flag_request_complete() is called.

    Thread Safety:
        - upsert() called from reader thread
        - flag_request_complete/flag_request_failed called from reader thread
        - to_domain() called from main thread via hooks
    """

    def __init__(
        self,
        req_id: int,
        contract: Contract,
        bar_size: str,
        end_date_time: str | None,
        duration_str: str | None,
    ) -> None:
        """Initialize a bar request.

        Args:
            req_id: TWS request ID for this request
            contract: Contract to fetch bars for
            bar_size: TWS bar size string (e.g., "5 mins")
            end_date_time: End datetime for historical request
            duration_str: Duration string (e.g., "1 D")
        """
        self.contract: Contract = contract
        self.req_id: int = req_id
        self.__bar_size: str = bar_size
        self.__end_date_time: str | None = end_date_time
        self.__duration_str: str | None = duration_str

        # Temporary storage for bars before history complete
        self.__bars: dict[datetime, SmartTwsBar] = {}

        # Live subscription tracking
        self.__last_update_time: float | None = None
        self.__last_index: datetime | None = None

        # Request state events
        self.__request_complete: threading.Event = threading.Event()
        self.__request_failed: threading.Event = threading.Event()

        self.__start_time: datetime | None = None
        self.__end_time: datetime | None = None

    @property
    def bar_size(self) -> str:
        """TWS bar size string (e.g., '5 mins')."""
        return self.__bar_size

    @property
    def end_date_time(self) -> str:
        """End datetime string for the request."""
        return self.__end_date_time or ""

    @property
    def duration_str(self) -> str:
        """Duration string (e.g., '1 D')."""
        return self.__duration_str or ""

    @property
    def start_time(self) -> datetime | None:
        """Parsed start time (set after request completes)."""
        return self.__start_time

    @property
    def end_time(self) -> datetime | None:
        """Parsed end time (set after request completes)."""
        return self.__end_time

    @property
    def is_live(self) -> bool:
        """Whether stream is actively receiving updates."""
        if self.__last_update_time is None:
            return False
        if self.__request_failed.is_set():
            return False
        # Consider live if updated within last 10 seconds
        return (time_.time() - self.__last_update_time) < 10.0

    @property
    def description(self) -> str:
        """Human-readable description for logging and keying."""
        return compute_description(
            self.contract,
            self.__bar_size,
            self.__end_date_time,
            self.__duration_str,
        )

    @property
    def is_ready(self) -> bool:
        """Whether the request has completed successfully."""
        return self.__request_complete.is_set()

    @property
    def last(self) -> SmartTwsBar | None:
        """Get the most recent bar, if any."""
        if not self.__bars or self.__last_index is None:
            return None
        return self.__bars.get(self.__last_index)

    def upsert(self, bar: BarData) -> None:
        """Insert or update a bar from TWS callback.

        If a bar with the same timestamp exists, updates it with merge logic.
        Otherwise, inserts a new bar.

        Args:
            bar: TWS BarData object
        """
        self.__last_index = parse_tws_bar_date_as_datetime(bar.date)

        if self.__last_index in self.__bars:
            self.__bars[self.__last_index].update_from_bardata(bar)
            self.__last_update_time = time_.time()
        else:
            # New bar in live stream - insert it
            smart_bar = SmartTwsBar.from_bar_data(bar)
            self.__bars[self.__last_index] = smart_bar
            self.__last_update_time = time_.time()

    def flag_request_complete(self, start: str, end: str) -> None:
        """Mark request as successfully completed.

        Called by historicalDataEnd callback.

        Args:
            start: Start time string from TWS
            end: End time string from TWS
        """
        self.__start_time = parse_tws_bar_date_as_datetime(start)
        self.__end_time = parse_tws_bar_date_as_datetime(end)

        self.__request_complete.set()

        if DEBUG_TWS_DATAFEED:
            logger.info(
                f"History complete for {self.description}: "
                f"{len(self.__bars)} bars from {start} to {end}"
            )

    def flag_request_failed(self, exception: ProviderException) -> None:
        """Mark request as failed.

        Args:
            exception: The error that caused the failure
        """
        self.__request_failed.set()

        logger.warning(
            f"Bar request failed for {self.description}: {exception.message}"
        )

    def to_domain(self) -> list[Bar]:
        """Convert accumulated bars to domain model list.

        Returns:
            List of Bar objects sorted by time ascending
        """
        return [
            bar.to_domain()
            for bar in sorted(self.__bars.values(), key=lambda b: b.time)
        ]


def resolve_snapshot(fut: asyncio.Future[list[Bar]], bars: BarsRequest) -> None:
    if not fut.done():
        fut.set_result(bars.to_domain())


def reject_snapshot(fut: asyncio.Future[list[Bar]], exc: ProviderException) -> None:
    if not fut.done():
        fut.set_exception(exc)


async def dispatch_update(
    callback: Callable[[Bar], Coroutine[Any, Any, None]],
    bars: BarsRequest,
) -> None:
    last = bars.last
    assert last is not None, "dispatch_update called with no last bar"
    await callback(last.to_domain())


class BarsTracker:
    """Manages bar subscriptions and dispatches bar updates to BarsRequests.

    Provides a unified interface for bar data access:
    - Snapshot pattern: Get historical bars, waiting for completion
    - Streaming pattern: Subscribe to continuous bar updates

    The tracker maintains a mapping from request descriptions to BarsRequests
    and handles TWS request ID allocation for new bar subscriptions.

    Thread Safety:
        - Lookup methods (request, subscribe): main thread
        - Update methods (update, raise_error): reader thread via IBSocket callbacks
    """

    def __init__(
        self,
        bars_request_hook: Callable[[Contract, str, str | None, str | None], int],
        bars_cancel_hook: Callable[[int], None],
        timeout: float = 11.0,
    ) -> None:
        """Initialize BarsTracker.

        Args:
            bars_request_hook: Callable to request bars given a Contract and params
            bars_cancel_hook: Callable to cancel a bar request given a request ID
            timeout: Default timeout in seconds for snapshot requests
        """
        self.tracker_lock = threading.Lock()
        self._bars_request_hook = bars_request_hook
        self._bars_cancel_hook = bars_cancel_hook
        self._timeout = timeout

        # Bar request storage
        self._bar_requests: dict[int, BarsRequest] = {}  # req_id -> BarsRequest
        self._requests: dict[str, int] = {}  # description -> req_id

        # Hook storage
        self._snapshot_hooks: dict[
            int, dict[str, tuple[asyncio.AbstractEventLoop, asyncio.Future[list[Bar]]]]
        ] = {}
        self._stream_hooks: dict[
            int,
            dict[
                str,
                tuple[
                    asyncio.AbstractEventLoop,
                    Callable[[Bar], Coroutine[Any, Any, None]],
                    Callable[[ProviderException], Coroutine[Any, Any, None]],
                ],
            ],
        ] = {}

    def _bar_req_in_use(self, req_id: int) -> bool:
        """Check if a BarsRequest has any active snapshot or stream hooks."""
        in_use = bool(
            self._snapshot_hooks.get(req_id, {}) or self._stream_hooks.get(req_id, {})
        )
        return in_use

    def _get_or_create_bar_req(
        self,
        contract: Contract,
        bar_size: str,
        end_date_time: str | None = None,
        duration_str: str | None = None,
    ) -> BarsRequest:
        """Get existing bar request or create new TWS subscription.

        If a request for this ticker already exists, returns it.
        Otherwise, allocates a new request ID, creates a BarsRequest,
        and initiates a TWS historical data request.

        Args:
            contract: Contract with ticker name and resolved contract
            bar_size: TWS bar size string (e.g., "5 mins")
            end_date_time: End datetime for historical request
            duration_str: Duration string (e.g., "1 D")
            exchange: Optional exchange override ("SMART", "OVERNIGHT", etc.)
                      If None, uses build_best_contract() auto-selection

        Returns:
            BarsRequest for the ticker (existing or newly created)
        """
        # Select contract based on exchange parameter
        # Fallback to best contract if specific exchange not available
        description = compute_description(
            contract,
            bar_size,
            end_date_time,
            duration_str,
        )
        req_id = self._requests.get(description)
        if req_id is None:
            if DEBUG_TWS_DATAFEED:
                logger.info(f"Requesting new bars for {description}")
            req_id = self._bars_request_hook(
                contract, bar_size, end_date_time, duration_str
            )

            self._bar_requests[req_id] = BarsRequest(
                req_id, contract, bar_size, end_date_time, duration_str
            )

            self._requests[description] = req_id

            if DEBUG_TWS_DATAFEED:
                logger.info(f"Active bar requests: [{list(self._requests.keys())}]")

        bar_request = self._bar_requests.get(req_id)
        assert bar_request is not None, "bars should exist after requesting bars"
        return bar_request

    def _debounce_cancel_bar_request(self, req_id: int) -> None:
        """Debounce unsubscribe - remove bar request if no active hooks."""

        def debounce_cancel(req_id: int) -> None:
            with self.tracker_lock:
                bar_request = self._bar_requests.get(req_id)
                if bar_request is None:
                    if DEBUG_TWS_DATAFEED:
                        logger.info(
                            f"debounce_cancel: No bar_request found for req_id {req_id}"
                        )
                    return
                if not self._bar_req_in_use(req_id):
                    self._requests.pop(bar_request.description, None)
                    self._bars_cancel_hook(req_id)
                    self._bar_requests.pop(req_id, None)
                elif DEBUG_TWS_DATAFEED:
                    logger.info(
                        f"debounce_cancel: Bar request {req_id} still in use {bar_request.description}, "
                        f"snapshot_hooks={[key[-12:] for key in self._snapshot_hooks.get(req_id, {}).keys()]}, "
                        f"stream_hooks={[key[-12:] for key in self._stream_hooks.get(req_id, {}).keys()]}"
                    )
                if DEBUG_TWS_DATAFEED:
                    logger.info(
                        f"Remaining bar requests: {list(self._requests.keys())}"
                    )

        asyncio.get_running_loop().call_later(1.0, debounce_cancel, req_id)

    # === Lookup Methods (main thread) ===

    async def request(
        self,
        contract: Contract,
        bar_size: str,
        end_date_time: str,
        duration_str: str,
        timeout: float | None = None,
    ) -> list[Bar]:
        """Request historical bars, waiting for completion.

        Creates a TWS subscription if needed, waits for historicalDataEnd,
        and returns the bars as domain models.

        Args:
            contract: Contract with ticker name and resolved contract
            bar_size: TWS bar size string (e.g., "5 mins")
            end_date_time: End datetime for historical request
            duration_str: Duration string (e.g., "1 D")
            timeout: Optional timeout override (uses default if not specified)
            exchange: Optional exchange override ("SMART", "OVERNIGHT", etc.)
                      If None, uses build_best_contract() auto-selection

        Returns:
            List of Bar domain models sorted by time

        Raises:
            asyncio.TimeoutError: If bars not received within timeout
            ProviderException: If TWS returns an error for this request
        """

        assert contract.exchange, "contract must have exchange set"
        key = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        future: asyncio.Future[list[Bar]] = loop.create_future()

        with self.tracker_lock:
            bar_request = self._get_or_create_bar_req(
                contract, bar_size, end_date_time, duration_str
            )
            bar_snapshot_hooks = self._snapshot_hooks.setdefault(bar_request.req_id, {})
            bar_snapshot_hooks[key] = (loop, future)
            if DEBUG_TWS_DATAFEED:
                logger.info(
                    f"Registered snapshot hook for {bar_request.description} "
                    f"(req_id {bar_request.req_id}) => {key}"
                )

        # Resolve immediately if already ready
        if bar_request.is_ready:
            future.set_result(bar_request.to_domain())

        try:
            return await asyncio.wait_for(future, timeout=timeout or self._timeout)
        finally:
            with self.tracker_lock:
                bar_snapshot_hooks = self._snapshot_hooks.setdefault(
                    bar_request.req_id, {}
                )
                bar_snapshot_hooks.pop(key, None)
            if DEBUG_TWS_DATAFEED:
                logger.info(
                    f"Unregistered snapshot hook for {bar_request.description} "
                    f"(req_id {bar_request.req_id}) => {key}"
                )
            self._debounce_cancel_bar_request(bar_request.req_id)

    # === Subscription Methods (main thread) ===

    def subscribe(
        self,
        contract: Contract,
        bar_size: str,
        on_update: Callable[[Bar], Coroutine[Any, Any, None]],
        on_error: Callable[[ProviderException], Coroutine[Any, Any, None]],
    ) -> str:
        """Subscribe to streaming bar updates for a contract.

        Creates a TWS subscription if needed and registers callbacks
        for continuous bar updates.

        Args:
            contract: Contract with ticker name and resolved contract
            bar_size: TWS bar size string (e.g., "5 mins")
            on_update: Async callback invoked on each bar update
            on_error: Async callback invoked on error

        Returns:
            Subscription key for unsubscribe()
        """
        assert contract.exchange, "contract must have exchange set"
        key = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        with self.tracker_lock:
            bar_request = self._get_or_create_bar_req(contract, bar_size)
            bar_request_stream_hooks = self._stream_hooks.setdefault(
                bar_request.req_id, {}
            )
            bar_request_stream_hooks[key] = (loop, on_update, on_error)
            if DEBUG_TWS_DATAFEED:
                logger.info(
                    f"Registered stream hook for {bar_request.description} "
                    f"(req_id {bar_request.req_id}) => {key}"
                )
        sub_key = f"{bar_request.description}#{key}"
        return sub_key

    def unsubscribe(self, sub_key: str) -> None:
        """Remove a bar subscription.

        Removes the subscription callback. If no more subscribers remain,
        the TWS request will be cancelled after a debounce period.

        Args:
            sub_key: Subscription key from subscribe()
        """
        if "#" not in sub_key:
            logger.warning(f"Invalid unsubscribe sub_key: {sub_key}")
            return
        description, sub_key = sub_key.split("#", 1)

        with self.tracker_lock:
            req_id = self._requests.get(description)
            if req_id is None:
                return
            bar_request_stream_hooks = self._stream_hooks.get(req_id)
            if bar_request_stream_hooks is not None:
                bar_request_stream_hooks.pop(sub_key, None)

        if DEBUG_TWS_DATAFEED:
            logger.info(
                f"Unsubscribing from bar_request stream for "
                f"{description} (req_id {req_id}) => {sub_key}"
            )

        self._debounce_cancel_bar_request(req_id)

    # === Update Methods (reader thread via callbacks) ===

    def update(self, req_id: int, bar_data: BarData) -> None:
        """Apply bar update to a BarsRequest.

        Called from reader thread via IBSocket historicalData callback.
        Dispatches updates to snapshot/stream hooks.

        Args:
            req_id: TWS request ID from callback
            bar_data: BarData from TWS
        """

        with self.tracker_lock:
            bar_request = self._bar_requests.get(req_id)

            if bar_request is None:
                logger.warning(f"Received bar update for unknown req_id {req_id}")
                return
            bar_request.upsert(bar_data)

            bar_request_snapshot_hooks = list(
                self._snapshot_hooks.get(req_id, {}).values()
            )
            bar_request_stream_hooks = list(self._stream_hooks.get(req_id, {}).values())

            # If no longer used, debounce cancel
            if not (bar_request_snapshot_hooks or bar_request_stream_hooks):
                logger.warning(
                    f"update: Unused bar_request subscription for req_id "
                    f"{req_id} --> {bar_request.description}"
                )
                return

            # Resolve snapshot hooks if ready
            if bar_request.is_ready:
                for loop, future in bar_request_snapshot_hooks:
                    loop.call_soon_threadsafe(resolve_snapshot, future, bar_request)

            # Dispatch to stream hooks
            for loop, callback, _ in bar_request_stream_hooks:
                loop.call_soon_threadsafe(
                    loop.create_task,
                    dispatch_update(callback, bar_request),
                )

    def raise_error(self, req_id: int, exception: ProviderException) -> bool:
        """Dispatch error to a BarsRequest's hooks.

        Called from reader thread when TWS reports an error for a bar request.

        Args:
            req_id: TWS request ID for the failed request
            exception: ProviderException to propagate to hooks

        Returns:
            True if error was handled, False if no matching request
        """
        with self.tracker_lock:
            bar_request = self._bar_requests.get(req_id)

            if bar_request is None:
                return False

            bar_request.flag_request_failed(exception)

            bar_request_snapshot_hooks = list(
                self._snapshot_hooks.get(req_id, {}).values()
            )
            bar_request_stream_hooks = list(self._stream_hooks.get(req_id, {}).values())

            # If no longer used, debounce cancel
            if not (bar_request_snapshot_hooks or bar_request_stream_hooks):
                logger.warning(
                    f"raise_error: Unused bar_request subscription for req_id "
                    f"{req_id} --> {bar_request.description}"
                )
                return True

            # Dispatch to snapshot hooks
            for loop, future in bar_request_snapshot_hooks:
                loop.call_soon_threadsafe(reject_snapshot, future, exception)

            # Dispatch to stream hooks
            for loop, _, on_error in bar_request_stream_hooks:
                loop.call_soon_threadsafe(
                    loop.create_task,
                    on_error(exception),
                )
            return True

    def flag_complete(self, req_id: int, start: str, end: str) -> None:
        """Mark a bar request as complete and dispatch to hooks.

        Called from reader thread via IBSocket historicalDataEnd callback.

        Args:
            req_id: TWS request ID for the completed request
            start: Start time string from TWS
            end: End time string from TWS
        """
        with self.tracker_lock:
            bar_request = self._bar_requests.get(req_id)

            if bar_request is None:
                logger.warning(
                    f"Received historicalDataEnd for unknown req_id {req_id}"
                )
                return

            bar_request.flag_request_complete(start, end)

            bar_request_snapshot_hooks = list(
                self._snapshot_hooks.get(req_id, {}).values()
            )

            # Resolve snapshot hooks now that data is complete
            for loop, future in bar_request_snapshot_hooks:
                loop.call_soon_threadsafe(resolve_snapshot, future, bar_request)

    # === Session Management ===

    def reset(self) -> None:
        """Full reset - clear all bar requests and subscriptions.

        Called when connection is lost or tracker needs reinitialization.
        Does not cancel TWS requests (connection may be down).
        """
        self._bar_requests.clear()
        self._snapshot_hooks.clear()
        self._stream_hooks.clear()
        self._requests.clear()
