"""TWS provider - Interactive Brokers datafeed integration.

Layer 2 of TWS integration:
- Implements DatafeedCapability with AsyncIO bridge
- Domain conversion (TWS types ↔ core models)
- Thread-safe AsyncIO bridge (main thread ↔ TWS reader thread)
- Provider-agnostic error translation
- Multi-capability ready (broker capability future extension)

Architecture:
- TWSConnection (Layer 1): Pure TWS protocol, sync callbacks, zero-copy
- TWSProvider (Layer 2): AsyncIO bridge, domain conversion, capability impl
"""

import asyncio
import logging
import threading
from concurrent.futures import Future
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

from ibapi.common import BarData
from ibapi.contract import Contract, ContractDescription, ContractDetails

from trading_api.models.common import CapabilitySpec
from trading_api.models.market import (
    Bar,
    QuoteData,
    SearchSymbolResultItem,
    SymbolInfo,
    TimeFrame,
)
from trading_api.models.providers.tws.tws_configs import TWSProviderConfig
from trading_api.providers.base import Provider
from trading_api.providers.capabilities.datafeed import DatafeedCapability
from trading_api.providers.tws.tws_connection import TWSConnection

logger = logging.getLogger(__name__)


class TWSProvider(Provider, DatafeedCapability):
    """TWS provider - implements DatafeedCapability with AsyncIO bridge.

    [LAYER 2]: AsyncIO interface on top of sync TWS callbacks (Layer 1)
    [THREAD-SAFE]: AsyncIO bridge handles cross-thread communication
    [DOMAIN-ONLY]: All public methods use domain models (no TWS types)
    [MULTI-CAPABILITY]: Extensible to broker capability (orders, executions, etc.)
    """

    def __init__(self, config: TWSProviderConfig | None = None) -> None:
        """Initialize TWSProvider.

        Args:
            config: Provider configuration (auto-loaded from env if None)
        """
        self._config = config or TWSProviderConfig()

        # Layer 1: TWSConnection (sync callbacks)
        self.tws = TWSConnection()

        # AsyncIO bridge state
        self._next_req_id = 1
        self._req_id_lock = asyncio.Lock()
        self._pending_requests: dict[int, Future[Any]] = {}
        self._subscriptions: dict[int, Callable[..., None]] = {}

        # Connection thread
        self._connection_thread: threading.Thread | None = None

        # Register callback wrappers
        self._register_callbacks()

    # === Provider Implementation ===

    @classmethod
    def provider_dir(cls) -> Path:
        """Return provider directory path."""
        return Path(__file__).parent

    @property
    def name(self) -> str:
        """Return provider name."""
        return "tws"

    @classmethod
    def capabilities(cls) -> list[CapabilitySpec]:
        """Return capabilities provided by this provider."""
        return [CapabilitySpec(name="datafeed")]

    @property
    def config(self) -> TWSProviderConfig:  # type: ignore[override]
        """Return provider configuration.

        [OVERRIDE]: Returns specific TWSProviderConfig (not base ProviderConfig).
        """
        return self._config

    # === Lifecycle Hooks ===

    async def on_startup(self) -> None:
        """Connect to TWS on provider startup."""
        logger.info(
            f"Starting TWS connection to {self._config.host}:{self._config.port}"
        )

        # Start TWS connection in separate thread
        self._connection_thread = threading.Thread(
            target=self.tws.connect_and_run,
            args=(self._config.host, self._config.port, self._config.client_id),
            daemon=True,
        )
        self._connection_thread.start()

        # Wait for connection ready
        if not self.tws.is_ready.wait(timeout=self._config.connection_timeout):
            raise TimeoutError("TWS connection timeout")

        logger.info("TWS connection ready")

    async def on_shutdown(self) -> None:
        """Disconnect from TWS on provider shutdown."""
        logger.info("Shutting down TWS connection")
        self.tws.disconnect()

        if self._connection_thread:
            self._connection_thread.join(timeout=5.0)

    # === AsyncIO Bridge Internals ===

    async def _get_next_req_id(self) -> int:
        """Thread-safe async request ID generation.

        Returns:
            Unique request ID for TWS API calls
        """
        async with self._req_id_lock:
            req_id = self._next_req_id
            self._next_req_id += 1
            return req_id

    def _register_callbacks(self) -> None:
        """Wrap TWS callbacks to resolve Futures (cross-thread).

        [BRIDGE PATTERN]: TWS callbacks execute in reader thread, but must
        resolve asyncio.Future in main event loop thread.

        Uses loop.call_soon_threadsafe() for thread-safe Future resolution.
        """
        # Save original callbacks (for chaining)
        original_symbol_samples = self.tws.symbolSamples
        original_contract_details = self.tws.contractDetails
        original_contract_details_end = self.tws.contractDetailsEnd
        original_historical_data = self.tws.historicalData
        original_historical_data_end = self.tws.historicalDataEnd

        # Wrap symbolSamples callback (single-response pattern)
        def symbol_samples_wrapper(
            req_id: int, contract_descriptions: list[ContractDescription]
        ) -> None:
            future = self._pending_requests.get(req_id)
            if future and not future.done():
                # Cross-thread Future resolution
                loop = asyncio.get_event_loop()
                loop.call_soon_threadsafe(future.set_result, contract_descriptions)
            # Call original for logging
            original_symbol_samples(req_id, contract_descriptions)

        self.tws.symbolSamples = symbol_samples_wrapper  # type: ignore[method-assign,assignment]

        # Wrap contractDetails callback (multi-response accumulation pattern)
        def contract_details_wrapper(req_id: int, details: ContractDetails) -> None:
            # Accumulate results in future's internal list
            future = self._pending_requests.get(req_id)
            if future:
                # Get or create accumulation list
                if not hasattr(future, "_accumulated"):
                    future._accumulated = []  # type: ignore[attr-defined]
                future._accumulated.append(details)  # type: ignore[attr-defined]
            original_contract_details(req_id, details)

        self.tws.contractDetails = contract_details_wrapper  # type: ignore[method-assign,assignment]

        # Wrap contractDetailsEnd callback (multi-response end signal)
        def contract_details_end_wrapper(req_id: int) -> None:
            future = self._pending_requests.get(req_id)
            if future and not future.done():
                loop = asyncio.get_event_loop()
                accumulated = getattr(future, "_accumulated", [])
                loop.call_soon_threadsafe(future.set_result, accumulated)
            original_contract_details_end(req_id)

        self.tws.contractDetailsEnd = contract_details_end_wrapper  # type: ignore[method-assign,assignment]

        # Wrap historicalData callback (multi-response accumulation pattern)
        def historical_data_wrapper(req_id: int, bar: BarData) -> None:
            future = self._pending_requests.get(req_id)
            if future:
                if not hasattr(future, "_accumulated"):
                    future._accumulated = []  # type: ignore[attr-defined]
                future._accumulated.append(bar)  # type: ignore[attr-defined]
            original_historical_data(req_id, bar)

        self.tws.historicalData = historical_data_wrapper  # type: ignore[method-assign,assignment]

        # Wrap historicalDataEnd callback
        def historical_data_end_wrapper(req_id: int, start: str, end: str) -> None:
            future = self._pending_requests.get(req_id)
            if future and not future.done():
                loop = asyncio.get_event_loop()
                accumulated = getattr(future, "_accumulated", [])
                loop.call_soon_threadsafe(future.set_result, accumulated)
            original_historical_data_end(req_id, start, end)

        self.tws.historicalDataEnd = historical_data_end_wrapper  # type: ignore[method-assign,assignment]

    # === Domain Conversion Helpers (Request: Domain → TWS) ===

    def _build_tws_contract(self, symbol: str, exchange: str = "SMART") -> Contract:
        """Domain → TWS: Build Contract from symbol/exchange.

        Args:
            symbol: Symbol name (e.g., "AAPL")
            exchange: Exchange name (default: SMART routing)

        Returns:
            TWS Contract object
        """
        contract = Contract()
        contract.symbol = symbol
        contract.secType = "STK"  # Stock (extend for options/futures later)
        contract.exchange = exchange
        contract.currency = "USD"
        return contract

    def _map_timeframe_to_tws(self, resolution: TimeFrame) -> str:
        """Domain → TWS: TimeFrame enum → bar size string.

        Args:
            resolution: TimeFrame enum

        Returns:
            TWS bar size string (e.g., "1 min", "1 day")

        Note:
            TimeFrame enum has duplicate values (SEC_5="5", MIN_5="5").
            Python treats them as aliases, so MIN_5 IS SEC_5.
            We only map canonical members (first defined).
        """
        mapping = {
            TimeFrame.SEC_5: "5 secs",  # Note: MIN_5 is alias of SEC_5
            TimeFrame.SEC_10: "10 secs",
            TimeFrame.MIN_1: "1 min",
            # TimeFrame.MIN_5: same as SEC_5, skip
            TimeFrame.MIN_15: "15 mins",
            TimeFrame.MIN_30: "30 mins",
            TimeFrame.HOUR_1: "1 hour",
            TimeFrame.DAY_1: "1 day",
            TimeFrame.WEEK_1: "1 week",
            TimeFrame.MONTH_1: "1 month",
        }
        return mapping.get(resolution, "1 day")

    def _calculate_tws_duration(self, start_time: datetime, end_time: datetime) -> str:
        """Domain → TWS: Time delta → duration string.

        Args:
            start_time: Start of time range
            end_time: End of time range

        Returns:
            TWS duration string (e.g., "30 D", "86400 S")
        """
        delta = end_time - start_time
        total_seconds = int(delta.total_seconds())

        # TWS duration format: "X S" (seconds), "X D" (days), etc.
        if total_seconds < 86400:  # Less than 1 day
            return f"{total_seconds} S"
        else:
            days = total_seconds // 86400
            return f"{days} D"

    # === Domain Conversion Helpers (Response: TWS → Domain) ===

    def _convert_tws_bar_to_domain(self, tws_bar: BarData, symbol: str = "") -> Bar:
        """TWS → Domain: BarData → Bar.

        Args:
            tws_bar: TWS BarData object
            symbol: Optional symbol name to include

        Returns:
            Domain Bar model
        """
        # TWS bar.date can be Unix timestamp (as string) or date string
        if tws_bar.date.isdigit():
            timestamp_ms = int(tws_bar.date) * 1000
        else:
            # Parse date string if needed (future enhancement)
            timestamp_ms = 0

        return Bar(
            time=timestamp_ms,
            open=tws_bar.open,
            high=tws_bar.high,
            low=tws_bar.low,
            close=tws_bar.close,
            volume=int(tws_bar.volume) if tws_bar.volume else 0,
        )

    def _convert_contract_desc_to_search_result(
        self, desc: ContractDescription
    ) -> SearchSymbolResultItem:
        """TWS → Domain: ContractDescription → SearchSymbolResultItem.

        Args:
            desc: TWS ContractDescription object

        Returns:
            Domain SearchSymbolResultItem model
        """
        contract = desc.contract
        primary_exchange = getattr(contract, "primaryExchange", "") or contract.exchange
        return SearchSymbolResultItem(
            symbol=contract.symbol,
            exchange=primary_exchange,
            type=contract.secType.lower() if contract.secType else "unknown",
            description=contract.symbol,  # Limited info in search
            ticker=f"{contract.symbol}:{primary_exchange}",
        )

    def _convert_contract_details_to_symbol_info(
        self, details: ContractDetails
    ) -> SymbolInfo:
        """TWS → Domain: ContractDetails → SymbolInfo.

        Args:
            details: TWS ContractDetails object

        Returns:
            Domain SymbolInfo model
        """
        contract = details.contract
        primary_exchange = getattr(contract, "primaryExchange", "") or contract.exchange
        return SymbolInfo(
            name=contract.symbol,
            description=details.longName or contract.symbol,
            type=contract.secType.lower() if contract.secType else "stock",
            session="0930-1600",  # TODO: Parse from tradingHours
            timezone=details.timeZoneId or "America/New_York",
            ticker=f"{contract.symbol}:{primary_exchange}",
            exchange=primary_exchange,
            listed_exchange=contract.exchange,
            format="price",
            pricescale=100,  # TODO: Calculate from minTick
            minmov=1,  # TODO: Extract from priceMagnifier
            has_intraday=True,
            has_daily=True,
            supported_resolutions=[
                "1",
                "5",
                "15",
                "30",
                "60",
                "1D",
                "1W",
                "1M",
            ],
            volume_precision=0,
            data_status="streaming",
        )

    # === DatafeedCapability Implementation ===

    async def search_symbols(
        self,
        pattern: str,
        timeout: float = 5.0,
    ) -> list[SearchSymbolResultItem]:
        """Search for symbols matching pattern.

        [ASYNC-BRIDGE]: Wraps sync TWS callback with async Future.
        [DOMAIN-ONLY]: Returns domain models (no TWS types).

        Args:
            pattern: Search pattern
            timeout: Request timeout in seconds

        Returns:
            List of matching symbols

        Raises:
            TimeoutError: If request exceeds timeout
        """
        req_id = await self._get_next_req_id()
        future: Future[list[ContractDescription]] = Future()
        self._pending_requests[req_id] = future

        try:
            # Make TWS request
            self.tws.reqMatchingSymbols(req_id, pattern)

            # Wait for response (with timeout)
            tws_results = await asyncio.wait_for(
                asyncio.wrap_future(future), timeout=timeout
            )

            # Convert TWS → domain
            return [
                self._convert_contract_desc_to_search_result(desc)
                for desc in tws_results
            ]
        except asyncio.TimeoutError as e:
            raise TimeoutError(f"Symbol search timeout: {pattern}") from e
        finally:
            self._pending_requests.pop(req_id, None)

    async def get_symbol_info(
        self,
        symbol: str,
        exchange: str | None = None,
        timeout: float = 5.0,
    ) -> SymbolInfo:
        """Get detailed symbol information.

        Args:
            symbol: Symbol name
            exchange: Optional exchange filter
            timeout: Request timeout in seconds

        Returns:
            Detailed symbol metadata

        Raises:
            TimeoutError: If request exceeds timeout
            ValueError: If symbol not found or multiple matches
        """
        req_id = await self._get_next_req_id()
        future: Future[list[ContractDetails]] = Future()
        self._pending_requests[req_id] = future

        try:
            # Build contract
            contract = self._build_tws_contract(symbol, exchange or "SMART")

            # Make TWS request
            self.tws.reqContractDetails(req_id, contract)

            # Wait for response
            tws_results = await asyncio.wait_for(
                asyncio.wrap_future(future), timeout=timeout
            )

            if not tws_results:
                raise ValueError(f"Symbol not found: {symbol}")
            if len(tws_results) > 1:
                raise ValueError(
                    f"Multiple matches for symbol: {symbol} (specify exchange)"
                )

            # Convert TWS → domain
            return self._convert_contract_details_to_symbol_info(tws_results[0])
        except asyncio.TimeoutError as e:
            raise TimeoutError(f"Symbol info timeout: {symbol}") from e
        finally:
            self._pending_requests.pop(req_id, None)

    async def get_historical_bars(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime,
        resolution: TimeFrame,
        exchange: str | None = None,
        timeout: float = 30.0,
    ) -> list[Bar]:
        """Get historical OHLCV bars.

        [ACCUMULATION]: TWS sends bars one-by-one, we accumulate until end signal.

        Args:
            symbol: Symbol name
            start_time: Start of time range
            end_time: End of time range
            resolution: Bar timeframe
            exchange: Optional exchange filter
            timeout: Request timeout in seconds

        Returns:
            List of historical bars (ascending time order)

        Raises:
            TimeoutError: If request exceeds timeout
        """
        req_id = await self._get_next_req_id()
        future: Future[list[BarData]] = Future()
        self._pending_requests[req_id] = future

        try:
            # Build contract
            contract = self._build_tws_contract(symbol, exchange or "SMART")

            # Convert parameters
            bar_size = self._map_timeframe_to_tws(resolution)
            duration = self._calculate_tws_duration(start_time, end_time)
            end_date_str = end_time.strftime("%Y%m%d %H:%M:%S")

            # Make TWS request
            self.tws.reqHistoricalData(
                req_id,
                contract,
                end_date_str,
                duration,
                bar_size,
                "TRADES",  # Data type
                1,  # Use RTH (regular trading hours)
                1,  # Format date as Unix timestamp
                False,  # Keep up to date = False
                [],  # Chart options
            )

            # Wait for all bars
            tws_bars = await asyncio.wait_for(
                asyncio.wrap_future(future), timeout=timeout
            )

            # Convert TWS → domain
            return [self._convert_tws_bar_to_domain(bar, symbol) for bar in tws_bars]
        except asyncio.TimeoutError as e:
            raise TimeoutError(f"Historical bars timeout: {symbol}") from e
        finally:
            self._pending_requests.pop(req_id, None)

    def subscribe_realtime_bars(
        self,
        symbol: str,
        callback: Callable[[Bar], None],
        exchange: str | None = None,
        resolution: TimeFrame = TimeFrame.SEC_5,
    ) -> int:
        """Subscribe to real-time bars.

        [CONTINUOUS]: Callback invoked continuously until unsubscribe.
        [SYNC-CALLBACK]: Callback executes in TWS reader thread.

        Args:
            symbol: Symbol name
            callback: Callback for each new bar
            exchange: Optional exchange filter
            resolution: Bar timeframe (TWS only supports 5-second bars)

        Returns:
            Subscription ID (for unsubscribe)

        Raises:
            ValueError: If resolution is not 5 seconds
        """
        if resolution != TimeFrame.SEC_5:
            raise ValueError("TWS real-time bars only support 5-second resolution")

        # Build contract
        contract = self._build_tws_contract(symbol, exchange or "SMART")

        # Get request ID (sync version for subscriptions)
        req_id = self.tws.get_req_id()

        # Wrap callback to convert TWS → domain
        def tws_callback(
            time: int,
            open_: float,
            high: float,
            low: float,
            close: float,
            volume: Decimal,
            wap: Decimal,
            count: int,
        ) -> None:
            bar = Bar(
                time=time * 1000,  # Convert to milliseconds
                open=open_,
                high=high,
                low=low,
                close=close,
                volume=int(volume),
            )
            callback(bar)

        # Register callback
        self._subscriptions[req_id] = tws_callback
        self.tws.callbacks[req_id] = tws_callback

        # Make TWS request
        self.tws.reqRealTimeBars(
            req_id,
            contract,
            5,  # Bar size (5 seconds)
            "TRADES",  # Data type
            False,  # Use RTH
            [],  # Real-time bars options
        )

        return req_id

    def subscribe_market_data(
        self,
        symbol: str,
        callback: Callable[[QuoteData], None],
        exchange: str | None = None,
    ) -> int:
        """Subscribe to real-time market data.

        [NOT-IMPLEMENTED]: Placeholder for future implementation.

        Args:
            symbol: Symbol name
            callback: Callback for tick updates
            exchange: Optional exchange filter

        Returns:
            Subscription ID

        Raises:
            NotImplementedError: Not yet implemented
        """
        raise NotImplementedError("Market data subscriptions not yet implemented")

    def unsubscribe_realtime_bars(self, subscription_id: int) -> None:
        """Unsubscribe from real-time bars.

        Args:
            subscription_id: ID from subscribe_realtime_bars

        Raises:
            ValueError: If subscription ID not found
        """
        if subscription_id not in self._subscriptions:
            raise ValueError(f"Subscription ID not found: {subscription_id}")

        # Cancel TWS subscription
        self.tws.cancelRealTimeBars(subscription_id)

        # Cleanup
        self._subscriptions.pop(subscription_id, None)
        self.tws.callbacks.pop(subscription_id, None)

    def unsubscribe_market_data(self, subscription_id: int) -> None:
        """Unsubscribe from market data.

        [NOT-IMPLEMENTED]: Placeholder for future implementation.

        Args:
            subscription_id: ID from subscribe_market_data

        Raises:
            NotImplementedError: Not yet implemented
        """
        raise NotImplementedError("Market data unsubscribe not yet implemented")


__all__ = ["TWSProvider"]
