"""
Datafeed service for handling market data operations
"""

import asyncio
import json
import logging
import os
from collections.abc import Callable, Coroutine
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional
from zoneinfo import ZoneInfo

from trading_api.capabilities.datafeed import DatafeedCapability
from trading_api.models import (
    Bar,
    BarsSubscriptionRequest,
    DatafeedConfiguration,
    QuoteData,
    QuoteDataSubscriptionRequest,
    SearchSymbolResultItem,
    SymbolInfo,
)
from trading_api.models.common import DatastoreCapabilitySpec, ProviderCapabilitySpec
from trading_api.models.exceptions import ServiceException, TradingApiException
from trading_api.models.market import Resolution, TimeRange
from trading_api.models.market.quotes import QuoteValues
from trading_api.modules.datafeed.bar_cache_manager import BarCacheManager
from trading_api.modules.datafeed.repository import BarRepository
from trading_api.shared.config import settings
from trading_api.shared.ws.ws_router import (
    ProviderUpdateCallback,
    TopicErrorCallback,
    WsRouteService,
)
from trading_api.types import StorageType

logger = logging.getLogger(__name__)

DEBUG_TWS_DATAFEED = os.environ.get("DEBUG_TWS_DATAFEED") == "true"
DEBUG_TWS_CACHE = os.environ.get("DEBUG_TWS_CACHE") == "true"

us_eastern = ZoneInfo("US/Eastern")


# ============================================================================
# Recoverable Error Configuration
# ============================================================================
# Default behavior: ALL errors are non-recoverable (connection closes)
# Only exceptions in this set will keep the connection open and broadcast
# a SubscriptionError message instead.

_RECOVERABLE_ERROR_CODES: frozenset[str] = frozenset(
    {
        "PROVIDER_DATAFEED_TIMEOUT",
        "PROVIDER_DATAFEED_CONNECTION_LOST",
        "PROVIDER_DATAFEED_RATE_LIMIT",
        "PROVIDER_DATAFEED_DATA_GAP",
    }
)

_DEFAULT_RETRY_AFTER_MS = 5000

# ============================================================================
# Read-Through Cache Configuration
# ============================================================================
# Concurrent wait strategy: When another request owns a pending range,
# we poll until the range is covered or timeout is reached.
_CONCURRENT_WAIT_POLL_INTERVAL_MS = 100  # Poll every 100ms
_CONCURRENT_WAIT_TIMEOUT_MS = 10_000  # Give up after 10s, fetch directly


ProviderErrorCallback = Callable[[TradingApiException], Coroutine[Any, Any, None]]


class DatafeedService(WsRouteService):
    """Service for handling datafeed operations"""

    @classmethod
    def provider_capabilities(cls) -> list[ProviderCapabilitySpec]:
        """Return required provider capabilities for datafeed service.

        Requires datafeed capability from provider (e.g., TWSDatafeedProvider).

        Returns:
            List with datafeed capability requirement
        """
        return [ProviderCapabilitySpec(name="datafeed")]

    @classmethod
    def datastore_capabilities(cls) -> list[DatastoreCapabilitySpec]:
        """Return required datastore capabilities for datafeed service.

        Requires:
        - timeseries: Efficient bar storage/retrieval (time-range queries)
        - rangequery: Gap detection via PostgreSQL multirange operations
        - exclusion: Concurrent request deduplication (exclusion constraints)
        - transactions: Atomic mark_covered operations

        All capabilities are optional for MVP - service falls back to
        provider-only mode when PostgresDatastore not available.

        Returns:
            List of datastore capability requirements
        """
        return [
            DatastoreCapabilitySpec(name="timeseries", optional=True),
            DatastoreCapabilitySpec(name="rangequery", optional=True),
            DatastoreCapabilitySpec(name="exclusion", optional=True),
            DatastoreCapabilitySpec(name="transactions", optional=True),
        ]

    @property
    def datafeed_provider(self) -> DatafeedCapability:
        """Cached O(1) lookup - type-safe provider access.

        Returns:
            DatafeedCapability provider instance

        Raises:
            RuntimeError: If datafeed provider not available
        """
        provider = self.get_capability_provider("datafeed")
        # Type assertion: provider must implement DatafeedCapability (validated at init)
        assert isinstance(provider, DatafeedCapability)
        return provider

    def __init__(
        self,
        module_dir: Path,
        *args: Any,
        **kwargs: Any,
    ):
        """Initialize the datafeed service

        Args:
            module_dir: Path to the module directory
            providers: Provider instances for capabilities (unused, for interface compatibility)
            datastores: Datastore instances for capabilities (unused, for interface compatibility)
        """
        super().__init__(module_dir, *args, **kwargs)
        self.configuration = DatafeedConfiguration()
        # Track provider subscription IDs for each topic (for cleanup)
        self._topic_to_subs: dict[str, list[str]] = {}
        self._last_bars: dict[str, Bar] = {}

        # Initialize repository and cache manager
        # Use capability-based selection: prefer feature-rich datastore
        self._bar_repository: BarRepository | None = None
        self._cache_manager: BarCacheManager | None = None

        # Attempt to get featured datastore for bar storage
        try:
            bar_datastore = self.get_featured_datastore("timeseries")
            self._bar_repository = BarRepository(bar_datastore)

            # Check if datastore supports all cache manager requirements
            has_cache_support = all(
                bar_datastore.has_capability(cap)
                for cap in ["exclusion", "transactions", "rangequery"]
            )
            if has_cache_support:
                self._cache_manager = BarCacheManager(
                    datastore=bar_datastore,
                    pending_ttl_ms=settings.BAR_CACHE_PENDING_TTL_MS,
                )
                logger.info(
                    "DatafeedService: Read-through cache enabled (PostgresDatastore)"
                )
            else:
                logger.info(
                    "DatafeedService: Cache manager disabled - "
                    "datastore missing required capabilities"
                )
        except Exception:
            # Fallback to first available datastore (timeseries is optional)
            fallback_datastore = next(iter(self.datastores))
            self._bar_repository = BarRepository(fallback_datastore)
            logger.info("DatafeedService: Using fallback datastore without caching")

    def get_configuration(self) -> DatafeedConfiguration:
        """Get datafeed configuration.

        Returns:
            DatafeedConfiguration with supported resolutions, exchanges, etc.
        """
        return self.configuration

    async def create_topic(
        self,
        topic: str,
        topic_update: ProviderUpdateCallback,
        topic_error: TopicErrorCallback,
        user_id: str,
    ) -> None:
        """Parse topic and create appropriate subscription task.

        Topic formats:
            - bars:{"resolution":"1D","symbol":"AAPL"}
            - quotes:{"symbols":["AAPL","GOOGL"],"fast_symbols":["MSFT"]}

        Args:
            topic: Topic string in format "topic_type:{json_params}"
            topic_update: Callback to broadcast data updates to subscribers
            topic_error: Callback to broadcast errors to subscribers.
                        Service wraps this to determine recoverable/retry_after_ms.
            user_id: Authenticated user ID (unused - datafeed is not user-scoped).

        Raises:
            ValueError: If topic format is invalid or unknown topic type
            json.JSONDecodeError: If JSON params cannot be parsed
        """

        if topic in self._topic_to_subs:
            raise ServiceException(
                code="SERVICE_DATAFEED_TOPIC_EXISTS",
                message=f"Topic already exists in DatafeedService: {topic}",
                module="datafeed",
            )

        # Parse topic format: "topic_type:{json_params}"
        if ":" not in topic:
            raise ServiceException(
                code="SERVICE_DATAFEED_INVALID_TOPIC_FORMAT",
                message=f"Invalid topic format: {topic}",
                module="datafeed",
            )

        topic_type, params_json = topic.split(":", 1)

        # TODO: need to validate create_topic params/types against provider capabilities at runtime

        if topic_type == "bars":
            # Parse the JSON params part / Validate model
            params_dict = json.loads(params_json)
            subscription_request = BarsSubscriptionRequest.model_validate(params_dict)

            if DEBUG_TWS_DATAFEED:
                logger.info(f"creating new topic : {topic}")

            # Wrap error callback to compute recoverable/retry at service level
            async def on_sub_error(exc: TradingApiException) -> None:
                """Handle provider errors - determine recoverable status and forward."""
                recoverable = self._is_error_recoverable(exc)
                if not recoverable:
                    logger.error(f"Non-recoverable error on topic {topic} : {exc!r}")
                    self._topic_to_subs.pop(topic, None)

                retry_after_ms = _DEFAULT_RETRY_AFTER_MS if recoverable else None
                await topic_error(exc, recoverable, retry_after_ms)

            subscription_id = await self.datafeed_provider.subscribe_realtime_bars(
                ticker_name=subscription_request.symbol,
                resolution=subscription_request.resolution,
                callback=topic_update,
                on_error=on_sub_error,
            )

            # Track subscription ID for cleanup
            self._topic_to_subs[topic] = [subscription_id]
        elif topic_type == "quotes":
            # Parse the JSON params part / Validate model
            params_dict = json.loads(params_json)
            quote_subscription_request = QuoteDataSubscriptionRequest.model_validate(
                params_dict
            )

            # Combine all symbols (both slow and fast)
            all_symbols = list(
                set(
                    quote_subscription_request.symbols
                    + quote_subscription_request.fast_symbols
                )
            )

            if not all_symbols:
                raise ServiceException(
                    code="SERVICE_DATAFEED_NO_SYMBOLS",
                    message="No symbols provided for quote subscription",
                    module="datafeed",
                )

            if DEBUG_TWS_DATAFEED:
                logger.info(f"creating new topic : {topic}")

            # Subscribe to market data for all symbols via provider
            # Note: Symbol mutualization is handled at the provider/tracker level
            subscription_ids = self._topic_to_subs.setdefault(topic, [])
            for symbol in all_symbols:
                # Wrap error callback to compute recoverable/retry at service level
                async def on_sub_error(exc: TradingApiException) -> None:
                    """Handle provider errors - determine recoverable status and forward."""
                    recoverable = self._is_error_recoverable(exc)
                    if not recoverable:
                        logger.error(
                            f"Non-recoverable error on topic {topic} : {exc!r}"
                        )
                        self._topic_to_subs.pop(topic, None)

                    retry_after_ms = _DEFAULT_RETRY_AFTER_MS if recoverable else None
                    await topic_error(exc, recoverable, retry_after_ms)

                subscription_id = await self.datafeed_provider.subscribe_market_data(
                    ticker_name=symbol,
                    callback=topic_update,
                    on_error=on_sub_error,
                )
                subscription_ids.append(subscription_id)
        else:
            raise ServiceException(
                code="SERVICE_DATAFEED_UNKNOWN_TOPIC_TYPE",
                message=f"Unknown topic type: {topic_type}",
                module="datafeed",
            )

    def _is_error_recoverable(self, exc: TradingApiException) -> bool:
        """Determine if error is transient and streaming should continue.

        Default: ALL errors are non-recoverable (strict approach).
        Only errors in _RECOVERABLE_ERROR_CODES will keep the connection open.

        PROVIDER_TWS errors use suffix-based classification:
        - Codes ending in _NON_RECOVERABLE are not recoverable
        - Other PROVIDER_TWS_API codes are recoverable by default

        Args:
            exc: The exception to check

        Returns:
            True if error is recoverable, False otherwise
        """
        code = exc.code

        # Check explicit recoverable codes first
        if code in _RECOVERABLE_ERROR_CODES:
            return True

        # Handle PROVIDER_TWS_API error codes with suffix-based classification
        # Format: PROVIDER_TWS_API_{CATEGORY}_{CODE}[_NON_RECOVERABLE]
        if code.startswith("PROVIDER_TWS_API_"):
            # Non-recoverable if suffix indicates so
            if code.endswith("_NON_RECOVERABLE"):
                return False
            # All other PROVIDER_TWS_API errors are recoverable
            return True

        # Default: non-recoverable for unknown error codes
        return False

    def remove_topic(self, topic: str) -> None:
        """Remove topic and cleanup subscriptions.

        Handles both legacy asyncio tasks and provider subscriptions.
        """
        if DEBUG_TWS_DATAFEED:
            logger.info(f"removing topic: {topic}")
        subscription_ids = self._topic_to_subs.pop(topic, [])

        topic_type, _ = topic.split(":", 1)
        if topic_type == "bars":
            for subscription_id in subscription_ids:
                if DEBUG_TWS_DATAFEED:
                    logger.info(
                        f"Unsubscribing from bars: subscription ID {subscription_id}"
                    )
                self.datafeed_provider.unsubscribe_realtime_bars(subscription_id)
            if DEBUG_TWS_DATAFEED:
                logger.info("remaining bar subs: ")
                for topic, sub_ids in self._topic_to_subs.items():
                    logger.info(f"  topic: {topic}, sub_ids: {sub_ids}")
        elif topic_type == "quotes":
            for subscription_id in subscription_ids:
                if DEBUG_TWS_DATAFEED:
                    logger.info(
                        f"Unsubscribing from quotes: subscription ID {subscription_id}"
                    )
                self.datafeed_provider.unsubscribe_market_data(subscription_id)
            if DEBUG_TWS_DATAFEED:
                logger.info("remaining quotes subs: ")
                for topic, sub_ids in self._topic_to_subs.items():
                    logger.info(f"  topic: {topic}, sub_ids: {sub_ids}")
        else:
            raise ServiceException(
                code="SERVICE_DATAFEED_UNKNOWN_TOPIC_TYPE",
                message=f"Unknown topic type during removal: {topic_type}",
                module="datafeed",
            )

    async def search_symbols(
        self,
        user_input: str,
        exchange: str = "",
        symbol_type: str = "",
        max_results: int = 50,
    ) -> List[SearchSymbolResultItem]:
        """Search symbols based on user input and filters.

        Delegates to datafeed provider and applies business logic filters.

        Args:
            user_input: Search pattern (symbol, description, ticker)
            exchange: Optional exchange filter (applied after provider search)
            symbol_type: Optional symbol type filter (applied after provider search)
            max_results: Maximum results to return (applied after filtering)

        Returns:
            List of matching symbols with business filters applied
        """
        # Delegate to provider for raw search results
        provider_results = await self.datafeed_provider.search_symbols(
            pattern=user_input if user_input.strip() else "*",
            timeout=10.0,
        )

        # Apply business logic filters on provider results
        filtered_results = provider_results

        # Filter by exchange (case-insensitive)
        if exchange:
            filtered_results = [
                result
                for result in filtered_results
                if result.exchange.lower() == exchange.lower()
            ]

        # Filter by symbol type (case-insensitive)
        if symbol_type:
            filtered_results = [
                result
                for result in filtered_results
                if result.type.lower() == symbol_type.lower()
            ]

        # Limit results
        return filtered_results[:max_results]

    async def resolve_ticker(self, ticker: str) -> Optional[SymbolInfo]:
        """Resolve symbol information via datafeed provider."""
        return await self.datafeed_provider.get_symbol_info(
            ticker_name=ticker,
            timeout=5.0,
        )

    async def get_bars(
        self,
        ticker: str,
        resolution: Resolution,
        from_time: int,
        to_time: int,
        count_back: Optional[int] = None,
    ) -> List[Bar]:
        """Get historical bars for a symbol with read-through caching.

        Orchestration flow:
        1. Find gaps in cached coverage
        2. For each gap, try to acquire pending lock
        3. If owned, fetch from provider and store
        4. If not owned (concurrent request), wait for coverage
        5. Mark covered ranges after successful fetch
        6. Return full range from repository

        Falls back to provider-only mode when cache manager unavailable.

        Args:
            ticker: Symbol ticker (format: "SYMBOL" or "SYMBOL:EXCHANGE")
            resolution: Resolution enum (type-safe TradingView resolution)
            from_time: Start time (Unix milliseconds)
            to_time: End time (Unix milliseconds)
            count_back: Optional limit on number of bars to return

        Returns:
            List of bars in ascending time order
        """
        # Fallback: provider-only mode (no caching)
        if self._cache_manager is None:
            if DEBUG_TWS_CACHE:
                logger.info(
                    f"[CACHE BYPASS] {ticker}/{resolution.value} - no cache manager"
                )
            return await self._fetch_bars_from_provider(
                ticker, resolution, from_time, to_time, count_back
            )

        # Read-through cache orchestration
        assert self._bar_repository is not None

        # Step 1: Find gaps in coverage
        gaps = await self._cache_manager.find_missing_ranges(
            symbol=ticker,
            resolution=resolution,
            from_time=from_time,
            to_time=to_time,
        )

        if DEBUG_TWS_CACHE:
            if gaps:
                gap_ranges = ", ".join(f"[{g.start}-{g.end}]" for g in gaps)
                logger.info(
                    f"[CACHE MISS] {ticker}/{resolution.value} - {len(gaps)} gap(s): {gap_ranges}"
                )
            else:
                logger.info(
                    f"[CACHE HIT] {ticker}/{resolution.value} [{from_time}-{to_time}]"
                )

        # Step 2-5: Process each gap
        for gap in gaps:
            await self._process_gap(
                ticker=ticker,
                resolution=resolution,
                gap=gap,
            )

        # Step 6: Return full range from repository
        bars = await self._bar_repository.get_bars(
            symbol=ticker,
            resolution=resolution,
            from_time=from_time,
            to_time=to_time,
        )

        # Apply count_back filter if specified
        if count_back and count_back > 0:
            bars = bars[-count_back:]

        # Update last bar cache for fallback quotes
        if bars and (
            ticker not in self._last_bars
            or self._last_bars[ticker].time < bars[-1].time
        ):
            self._last_bars[ticker] = bars[-1]

        return bars

    async def _process_gap(
        self,
        ticker: str,
        resolution: Resolution,
        gap: TimeRange,
    ) -> None:
        """Process a single cache gap with concurrent request handling.

        Strategy:
        - Try to acquire pending lock (exclusion constraint)
        - If acquired: fetch, store, mark covered
        - If blocked: wait for other request to complete, with timeout

        On timeout, fetch directly (stale pending will TTL-expire).
        """
        assert self._cache_manager is not None
        assert self._bar_repository is not None

        # Try to acquire pending lock
        pending = await self._cache_manager.try_add_pending(
            symbol=ticker,
            resolution=resolution,
            time_range=gap,
        )

        if pending is not None:
            # We own this range - fetch and cache
            if DEBUG_TWS_DATAFEED:
                logger.info(
                    f"[PENDING ACQUIRED] {ticker}/{resolution.value} [{gap.start}-{gap.end}]"
                )
            await self._fetch_and_cache_gap(
                ticker=ticker,
                resolution=resolution,
                gap=gap,
            )
        else:
            # Another request owns this range - wait for completion
            if DEBUG_TWS_DATAFEED:
                logger.info(
                    f"[PENDING BLOCKED] {ticker}/{resolution.value} [{gap.start}-{gap.end}] - waiting"
                )
            await self._wait_for_gap_coverage(
                ticker=ticker,
                resolution=resolution,
                gap=gap,
            )

    async def _fetch_and_cache_gap(
        self,
        ticker: str,
        resolution: Resolution,
        gap: TimeRange,
    ) -> None:
        """Fetch bars from provider and store in cache.

        Called when we successfully acquired the pending lock.
        """
        assert self._cache_manager is not None
        assert self._bar_repository is not None

        try:
            # Fetch from provider
            start_time = datetime.fromtimestamp(gap.start / 1000)
            end_time = datetime.fromtimestamp(gap.end / 1000)

            bars = await self.datafeed_provider.get_historical_bars(
                ticker_name=ticker,
                start_time=start_time,
                end_time=end_time,
                resolution=resolution,
                timeout=10.0,  # 10s provider + ~1s overhead = 11s frontend timeout
            )

            # Store in repository
            bar_count = await self._bar_repository.store_bars(
                symbol=ticker,
                resolution=resolution,
                bars=bars,
            )

            # Mark as covered (atomically removes pending)
            await self._cache_manager.mark_covered(
                symbol=ticker,
                resolution=resolution,
                time_range=gap,
                storage_type=StorageType.DATABASE,
                bar_count=bar_count,
            )

            if DEBUG_TWS_DATAFEED:
                logger.info(
                    f"Cached {bar_count} bars for {ticker}/{resolution.value} "
                    f"[{gap.start}-{gap.end}]"
                )

        except Exception as e:
            # On error, pending range will TTL-expire automatically
            logger.error(
                f"Failed to fetch/cache bars for {ticker}/{resolution.value} "
                f"[{gap.start}-{gap.end}]: {e}"
            )
            raise

    async def _wait_for_gap_coverage(
        self,
        ticker: str,
        resolution: Resolution,
        gap: TimeRange,
    ) -> None:
        """Wait for another request to complete coverage of a gap.

        Polls find_missing_ranges() until gap is covered or timeout.
        On timeout, fetches directly (stale pending will TTL-expire).
        """
        assert self._cache_manager is not None

        elapsed_ms = 0

        while elapsed_ms < _CONCURRENT_WAIT_TIMEOUT_MS:
            await asyncio.sleep(_CONCURRENT_WAIT_POLL_INTERVAL_MS / 1000)
            elapsed_ms += _CONCURRENT_WAIT_POLL_INTERVAL_MS

            # Check if gap is now covered
            remaining_gaps = await self._cache_manager.find_missing_ranges(
                symbol=ticker,
                resolution=resolution,
                from_time=gap.start,
                to_time=gap.end,
            )

            if not remaining_gaps:
                # Gap is fully covered by other request
                if DEBUG_TWS_DATAFEED:
                    logger.info(
                        f"Gap covered by concurrent request: {ticker}/{resolution.value} "
                        f"[{gap.start}-{gap.end}] after {elapsed_ms}ms"
                    )
                return

        # Timeout - fetch directly (owner may have failed)
        logger.warning(
            f"Concurrent wait timeout for {ticker}/{resolution.value} "
            f"[{gap.start}-{gap.end}] - fetching directly"
        )
        # Try to acquire pending (may succeed if original TTL-expired)
        pending = await self._cache_manager.try_add_pending(
            symbol=ticker,
            resolution=resolution,
            time_range=gap,
        )
        if pending is not None:
            await self._fetch_and_cache_gap(ticker, resolution, gap)
        # If still blocked, we'll just read partial data from repo

    async def _fetch_bars_from_provider(
        self,
        ticker: str,
        resolution: Resolution,
        from_time: int,
        to_time: int,
        count_back: Optional[int] = None,
    ) -> List[Bar]:
        """Fallback: Fetch bars directly from provider without caching.

        Used when cache manager is not available (no PostgresDatastore).
        """
        start_time = datetime.fromtimestamp(from_time / 1000)
        end_time = datetime.fromtimestamp(to_time / 1000)

        bars = await self.datafeed_provider.get_historical_bars(
            ticker_name=ticker,
            start_time=start_time,
            end_time=end_time,
            resolution=resolution,
            timeout=10.0,  # 10s provider + ~1s overhead = 11s frontend timeout
        )

        # Apply count_back filter if specified
        if count_back and count_back > 0:
            bars = bars[-count_back:]

        # Update last bar cache for fallback quotes
        if bars and (
            ticker not in self._last_bars
            or self._last_bars[ticker].time < bars[-1].time
        ):
            self._last_bars[ticker] = bars[-1]

        return bars

    async def get_quotes(self, tickers: List[str]) -> List[QuoteData]:
        """Get quotes for multiple symbols"""

        try:
            # Delegate to provider for real quote snapshots
            return await self.datafeed_provider.get_quotes_snapshot(
                ticker_names=tickers,
                timeout=1.0,
            )
        except Exception as e:
            # Fallback: use last cached bar as quote (if available) for debugging
            if any(ticker not in self._last_bars for ticker in tickers):
                raise e  # Reraise if we have no cached data for any ticker
            # logger.exception(e)
            quotes_result: list[QuoteData] = []
            for ticker in tickers:
                last_bar: Optional[Bar] = self._last_bars.get(ticker)
                quotes_result.append(
                    QuoteData(
                        s="ok",
                        n=ticker,
                        v=QuoteValues(
                            lp=last_bar.close if last_bar else 0.0,
                            ask=last_bar.close + 0.01 if last_bar else 0.0,
                            bid=last_bar.close - 0.01 if last_bar else 0.0,
                            spread=0.2,
                            open_price=last_bar.open if last_bar else 0.0,
                            high_price=last_bar.high if last_bar else 0.0,
                            low_price=last_bar.low if last_bar else 0.0,
                            prev_close_price=last_bar.close if last_bar else 0.0,
                            volume=last_bar.volume if last_bar else 0,
                            ch=0.0,
                            chp=0.0,
                            short_name=ticker,
                            exchange="",
                            description=f"Quote for {ticker}",
                            original_name=ticker,
                        ),
                    )
                )
            return quotes_result
