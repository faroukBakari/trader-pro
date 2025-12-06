"""TWS provider - Interactive Brokers datafeed integration.

Layer 3 of TWS integration:
- Implements DatafeedCapability interface
- Domain conversion (TWS types ↔ core models) via tws_mappers
- Delegates TWS communication to TWSClient (Layer 2)
- Provider-agnostic error translation

Architecture:
- TWSProvider (Layer 3): DatafeedCapability impl, domain conversion
- TWSClient (Layer 2): AsyncIO bridge, EWrapper callbacks
- IBSocket (Layer 1): Raw TCP protocol, message framing
"""

import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable
from zoneinfo import ZoneInfo

from ibapi.common import BarData
from ibapi.contract import Contract

from trading_api.models.common import CapabilitySpec, DatafeedError
from trading_api.models.market import (
    Bar,
    QuoteData,
    SearchSymbolResultItem,
    SymbolInfo,
    TimeFrame,
)
from trading_api.models.providers.tws.tws_configs import TWSProviderConfig
from trading_api.providers.capabilities.datafeed import DatafeedCapability
from trading_api.providers.tws.tws_connection import TWSClient
from trading_api.providers.tws.tws_models import RTMarketData
from trading_api.shared import Provider

from .tws_mappers import (
    contract_description_to_search_result,
    contract_details_to_symbol_info,
    tws_bar_to_domain_bar,
    tws_ticks_to_bar,
    tws_ticks_to_quote_data,
)

logger = logging.getLogger(__name__)

us_eastern = ZoneInfo("US/Eastern")

DEBUG_TWS_PROVIDER = os.environ.get("DEBUG_TWS_PROVIDER") == "true"
debug_log = logger.info

SMART_EXCHANGES = {"SMART", "NYSE", "NASDAQ"}


def _parse_ticker(ticker: str) -> tuple[str, str, str, str]:
    """Parse ticker string into components.
    Args:
        ticker: Ticker string in format "SYMBOL:EXCHANGE:SECTYPE-CONTRACTID"
    Returns:
        Tuple of (symbol_name, exchange, secType, contractId)
    Examples:
        >>> self._parse_ticker('AAPL:NASDAQ:STK-12345')
        ('AAPL', 'NASDAQ', 'STK', '12345')
        >>> self._parse_ticker('GOOGL:NASDAQ')
        ('GOOGL', 'NASDAQ', '', '')
    """

    ticker_parts = ticker.split(":")
    symbol_name = ticker_parts[0].strip()
    exchange = ""
    if len(ticker_parts) > 1:
        exchange = ticker_parts[1].strip()
    secType = ""
    contractId = ""
    if len(ticker_parts) > 2:
        ticker_parts = ticker_parts[2].split("-")
        secType = ticker_parts[0].strip()
        if len(ticker_parts) > 1:
            contractId = ticker_parts[1].strip()
    return symbol_name, exchange, secType, contractId


def _convert_resolution_to_timeframe(resolution: str) -> TimeFrame:
    """Convert TradingView resolution string to TimeFrame enum.

    Args:
        resolution: TradingView resolution string
            - Intraday: "1", "5", "15", "30", "60" (minutes)
            - Daily+: "1D", "1W", "1M"

    Returns:
        TimeFrame enum value

    Raises:
        ValueError: If resolution is not supported

    Examples:
        >>> self._convert_resolution_to_timeframe('1')
        TimeFrame.MIN_1
        >>> self._convert_resolution_to_timeframe('1D')
        TimeFrame.DAY_1
    """
    # Map TradingView resolution strings to TimeFrame enum
    # TradingView uses: "1", "5", "15", "30", "60" for minutes, "D"/"1D", "W"/"1W", "M"/"1M" for larger
    resolution_map: dict[str, TimeFrame] = {
        # Minutes (TradingView sends just the number)
        "1": TimeFrame.MIN_1,
        "5": TimeFrame.MIN_5,
        "15": TimeFrame.MIN_15,
        "30": TimeFrame.MIN_30,
        "60": TimeFrame.HOUR_1,
        # Daily/Weekly/Monthly (TradingView may send with or without "1" prefix)
        "D": TimeFrame.DAY_1,
        "1D": TimeFrame.DAY_1,
        "W": TimeFrame.WEEK_1,
        "1W": TimeFrame.WEEK_1,
        "M": TimeFrame.MONTH_1,
        "1M": TimeFrame.MONTH_1,
    }

    if resolution not in resolution_map:
        raise ValueError(
            f"Unsupported resolution: {resolution}. "
            f"Supported: {list(resolution_map.keys())}"
        )

    return resolution_map[resolution]


class TWSProvider(Provider, DatafeedCapability):
    """TWS provider - implements DatafeedCapability with AsyncIO bridge.

    [LAYER 2]: AsyncIO interface on top of sync TWS callbacks (Layer 1)
    [CONNECTION-OWNER]: Manages EClient and connection lifecycle
    [THREAD-SAFE]: AsyncIO bridge handles cross-thread communication
    [DOMAIN-ONLY]: All public methods use domain models (no TWS types)
    """

    def __init__(self, config: TWSProviderConfig | None = None) -> None:
        """Initialize TWSProvider.

        Args:
            config: Provider configuration (auto-loaded from env if None)
        """
        self._config: TWSProviderConfig = config or TWSProviderConfig()

        # Layer 1: TWSConnection (callbacks only)
        self._tws_client = TWSClient(
            self._config.host, self._config.port, self._config.client_id
        )

        # Unified ticker storage: key = "symbol:exchange" → RTMarketData
        self._ticks: dict[str, RTMarketData] = {}
        # Reverse mapping: subscription_id → (symbol, exchange, callback_type)
        self._subscription_map: dict[str, tuple[str, str, str]] = {}

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

    # === Helper Methods ===

    def _build_contract(
        self,
        ticker: str,
    ) -> Contract:
        """Build TWS Contract object from domain parameters.

        Args:
            symbol: Symbol name (e.g., "AAPL")
            exchange: Exchange name (default: "SMART" for smart routing)
            sec_type: Security type (default: "STK" for stocks)
            currency: Currency code (default: "USD")

        Returns:
            TWS Contract object ready for API calls
        """
        symbol, exchange, sec_type, conId = _parse_ticker(ticker)
        contract = Contract()
        contract.symbol = symbol
        contract.secType = sec_type
        contract.primaryExchange = exchange
        contract.conId = int(conId)
        return contract

    def _map_timeframe_to_tws_bar_size(self, resolution: TimeFrame) -> str:
        """Map domain TimeFrame → TWS barSizeSetting.

        Args:
            resolution: Domain TimeFrame enum

        Returns:
            TWS bar size string ("1 min", "5 mins", "1 hour", "1 day", etc.)

        Raises:
            DatafeedError: If resolution not supported
        """
        # Map TimeFrame enum members directly to TWS bar size strings
        mapping: dict[TimeFrame, str] = {
            TimeFrame.SEC_5: "5 secs",
            TimeFrame.SEC_10: "10 secs",
            TimeFrame.MIN_1: "1 min",
            TimeFrame.MIN_5: "5 mins",
            TimeFrame.MIN_15: "15 mins",
            TimeFrame.MIN_30: "30 mins",
            TimeFrame.HOUR_1: "1 hour",
            TimeFrame.DAY_1: "1 day",
            TimeFrame.WEEK_1: "1 week",
            TimeFrame.MONTH_1: "1 month",
        }

        bar_size = mapping.get(resolution)
        if not bar_size:
            raise DatafeedError(
                f"Unsupported resolution: {resolution}. "
                f"Supported: {[tf.name for tf in mapping.keys()]}"
            )
        return bar_size

    def _calculate_tws_duration(
        self, start_time: datetime, end_time: datetime, resolution: TimeFrame
    ) -> str:
        """Calculate TWS duration string from time range.

        TWS requires duration in format: "n S|D|W|M|Y"
        Maximum durations depend on bar size (e.g., 1 sec bars max 2000 S)

        Args:
            start_time: Start datetime
            end_time: End datetime
            resolution: Bar timeframe (used to select appropriate unit)

        Returns:
            TWS duration string (e.g., "1 D", "2 W", "86400 S")
        """
        delta = end_time - start_time
        total_seconds = int(delta.total_seconds())

        # Select duration unit based on resolution and time range
        # TWS limits: seconds (max 2000 S), days (max 365 D), weeks, months, years

        # Sub-minute bars (5, 10 seconds)
        if resolution in [TimeFrame.SEC_5, TimeFrame.SEC_10]:
            # Use seconds for short durations
            if total_seconds <= 2000:
                return f"{total_seconds} S"
            # Fall back to days for longer ranges
            days = delta.days + 1
            return f"{days} D"

        # Intraday bars (1 min - 1 hour)
        elif resolution in [
            TimeFrame.MIN_1,
            TimeFrame.MIN_5,
            TimeFrame.MIN_15,
            TimeFrame.MIN_30,
            TimeFrame.HOUR_1,
        ]:
            # Use days for intraday bars
            days = delta.days + 1
            if days <= 365:
                return f"{days} D"
            # Use years for very long ranges
            weeks = days // 365 + 1
            return f"{weeks} Y"

        # Daily and above
        else:
            days = delta.days + 1
            if days <= 365:
                return f"{days} D"
            # TWS: durations > 52 weeks must use years
            years = days // 365 + 1
            return f"{years} Y"

    # === DatafeedCapability Implementation ===

    async def search_symbols(
        self,
        pattern: str,
        **kwargs: Any,
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
            DatafeedError: If search fails
        """
        result = await self._tws_client.reqMatchingSymbols(pattern, **kwargs)

        return [contract_description_to_search_result(cd) for cd in result]

    async def get_symbol_info(
        self,
        ticker: str,
        **kwargs: Any,
    ) -> SymbolInfo:
        """Get detailed symbol information.

        [ASYNC-BRIDGE]: Wraps sync TWS callback with async Future.
        [ACCUMULATION]: TWS may return multiple ContractDetails, we use first match.
        [DOMAIN-ONLY]: Returns domain SymbolInfo (no TWS types).

        Args:
            symbol: Symbol name (e.g., "AAPL")
            exchange: Optional exchange filter (default: "SMART" for smart routing)

        Returns:
            Detailed symbol metadata (SymbolInfo)

        Raises:
            DatafeedError: If symbol not found or request fails
        """

        # Build TWS Contract for the request
        contract = self._build_contract(ticker)

        if contract.primaryExchange in SMART_EXCHANGES:
            now_us_eastern = datetime.now(us_eastern)
            smart_exchange = (
                "OVERNIGHT"
                if (
                    now_us_eastern.weekday() < 5
                    and (
                        now_us_eastern.time()
                        >= datetime.strptime("20:00:00", "%H:%M:%S").time()
                        or now_us_eastern.time()
                        < datetime.strptime("4:00:00", "%H:%M:%S").time()
                    )
                )
                else "SMART"
            )
        else:
            smart_exchange = contract.primaryExchange

        contract.exchange = smart_exchange

        try:
            # Get contract details via TWSClient (returns list)
            contract_details_list = await self._tws_client.reqContractDetails(
                contract, **kwargs
            )

            if not contract_details_list:
                raise DatafeedError(f"Symbol not found: {ticker}")

            # Use first match (most common case is single result)
            return contract_details_to_symbol_info(contract_details_list[0])

        except DatafeedError:
            raise
        except Exception as e:
            raise DatafeedError(f"Failed to get symbol info for {ticker}: {e}") from e

    async def get_historical_bars(
        self,
        ticker: str,
        start_time: datetime,
        end_time: datetime,
        resolution: TimeFrame,
        **kwargs: Any,
    ) -> list[Bar]:
        """Get historical OHLCV bars.

        [ASYNC-BRIDGE]: Wraps sync TWS callbacks with async Future.
        [ACCUMULATION]: TWS sends bars one-by-one, we accumulate until end signal.
        [DOMAIN-ONLY]: Returns domain Bar models (no TWS types).

        Args:
            symbol: Symbol name (e.g., "AAPL")
            start_time: Start of time range (inclusive)
            end_time: End of time range (inclusive)
            resolution: Bar timeframe (TimeFrame enum)
            exchange: Optional exchange filter (default: "SMART")
            timeout: Request timeout in seconds

        Returns:
            List of historical bars (ascending time order)

        Raises:
            DatafeedError: If request fails or symbol invalid
            TimeoutError: If request exceeds timeout
        """
        # Map domain parameters to TWS format
        bar_size = self._map_timeframe_to_tws_bar_size(resolution)
        duration_str = self._calculate_tws_duration(start_time, end_time, resolution)

        # Format datetime with timezone (TWS requires explicit timezone)
        # Convert to UTC if naive, otherwise use existing timezone
        if end_time.tzinfo is None:
            end_time_tz = end_time.astimezone()
        end_time_tz = end_time.astimezone(ZoneInfo("US/Eastern"))

        # Format: yyyymmdd-hh:mm:ss UTC (note hyphen separator and timezone suffix)
        if end_time_tz > datetime.now().astimezone(ZoneInfo("US/Eastern")):
            end_dt_str = ""
        else:
            end_dt_str = end_time_tz.strftime("%Y%m%d %H:%M:%S US/Eastern")

        tws_bars: list[BarData] = []
        try:
            contract = self._build_contract(ticker)
            exchanges = [contract.primaryExchange]
            if (
                contract.primaryExchange in SMART_EXCHANGES
                and resolution > TimeFrame.HOUR_1
            ):
                exchanges.append("OVERNIGHT")
            for exch in exchanges:
                contract.exchange = exch
                bars = await self._tws_client.reqHistoricalData(
                    contract,
                    end_dt_str,
                    duration_str,
                    bar_size,
                    **kwargs,
                )
                tws_bars.extend(bars)

            # Convert TWS BarData → domain Bar
            domain_bars = [tws_bar_to_domain_bar(bar) for bar in tws_bars]

            # Sort bars by time (ascending order)
            domain_bars.sort(key=lambda bar: bar.time)

            return domain_bars

        except Exception as e:
            raise DatafeedError(
                f"Failed to get historical bars for {ticker}: {e}"
            ) from e

    async def get_quotes_snapshot(
        self,
        tickers: list[str],
        **kwargs: Any,
    ) -> list[QuoteData]:
        """Get current market quotes for multiple symbols (snapshot).

        [UNIFIED]: Uses RTMarketData subscription, waits for initial data, then converts.
        [DOMAIN-ONLY]: Returns domain QuoteData models (no TWS types).

        Args:
            symbols: List of symbol names (e.g., ["AAPL", "GOOGL", "MSFT"])
            exchange: Optional exchange filter (default: "SMART")

        Returns:
            List of QuoteData (one per symbol, same order as input)

        Raises:
            DatafeedError: If request fails
            TimeoutError: If snapshot exceeds timeout
        """
        results: list[QuoteData] = []

        try:
            # Create or reuse subscriptions for all symbols
            for ticker in tickers:
                existing = ticker in self._ticks
                tick = self._get_or_create_ticker(ticker)
                if existing:
                    await asyncio.sleep(0.5)  # Give time for existing ticker to update
                results.append(tws_ticks_to_quote_data(tick))

            return results

        except Exception as e:
            raise DatafeedError(f"Failed to get quote snapshot: {e}") from e

    def subscribe_realtime_bars(
        self,
        ticker: str,
        resolution: TimeFrame,
        callback: Callable[[Bar], Awaitable[None]],
        **kwargs: Any,
    ) -> str:
        """Subscribe to real-time bars.

        [UNIFIED]: Uses RTMarketData subscription for bar data.
        [ASYNC-CALLBACK]: Callback executes in asyncio event loop.

        Args:
            symbol: Symbol name
            resolution: Bar timeframe
            callback: Callback for each new bar
            exchange: Optional exchange filter

        Returns:
            Subscription ID (for unsubscribe)

        Raises:
            DatafeedError: If subscription fails or resolution not supported
        """

        subscription_id = "subscribe_realtime_bars" + "_" + ticker

        loop = asyncio.get_event_loop()

        async def bar_callback(rt_data: RTMarketData, fields: list[str] | None) -> None:
            if fields is None or any(f.startswith("bar_") for f in fields):
                if DEBUG_TWS_PROVIDER:
                    debug_log(
                        f"Received real-time bar update for {ticker} with fields: {fields}"
                    )
                await callback(tws_ticks_to_bar(rt_data))

        # Get or create unified ticker via helper
        tick = self._get_or_create_ticker(ticker, resolution, **kwargs)

        tick.reqId_callback_map[subscription_id] = (loop, bar_callback)

        if DEBUG_TWS_PROVIDER:
            debug_log(f"Subscribed to real-time bars for {ticker}")
        return subscription_id

    def subscribe_market_data(
        self,
        tickers: list[str],
        callback: Callable[[QuoteData], Awaitable[None]],
        **kwargs: Any,
    ) -> list[str]:
        """Subscribe to real-time market data.

        [UNIFIED]: Uses RTMarketData subscription for quote data.
        [ASYNC-CALLBACK]: Callback executes in asyncio event loop.

        Args:
            symbols: List of symbol names
            callback: Callback for tick updates
            exchange: Optional exchange filter

        Returns:
            List of subscription IDs (one per symbol)

        Raises:
            DatafeedError: If subscription fails
        """
        subscription_ids: list[str] = []

        for ticker in tickers:
            subscription_id = "subscribe_market_data" + "_" + ticker
            loop = asyncio.get_event_loop()

            # Register quote callback on the ticker
            async def quote_callback(
                rt_data: RTMarketData, fields: list[str] | None
            ) -> None:
                if fields is not None and any(
                    f in {"bid", "ask", "last"} for f in fields
                ):
                    if DEBUG_TWS_PROVIDER:
                        debug_log(
                            f"Received market data update for {ticker} with fields: {fields}"
                        )
                    await callback(tws_ticks_to_quote_data(rt_data))

            tick = self._get_or_create_ticker(ticker, **kwargs)

            tick.reqId_callback_map[subscription_id] = (loop, quote_callback)

            subscription_ids.append(subscription_id)

        if DEBUG_TWS_PROVIDER:
            debug_log(f"Subscribed to market data for symbols: {tickers}")
        return subscription_ids

    def unsubscribe_realtime_bars(self, subscription_id: str) -> None:
        """Unsubscribe from real-time bars.

        Args:
            subscription_id: ID from subscribe_realtime_bars

        Raises:
            DatafeedError: If subscription ID not found
        """
        # Lookup symbol/exchange from reverse mapping
        for key, ticker in self._ticks.items():
            if subscription_id in ticker.reqId_callback_map:
                ticker.reqId_callback_map.pop(subscription_id, None)
                if DEBUG_TWS_PROVIDER:
                    debug_log(
                        f"Unsubscribed from real-time bars with subscription ID: {subscription_id}"
                    )
                if not ticker.reqId_callback_map:
                    self._remove_ticker(key)
                return

    def unsubscribe_market_data(self, subscription_ids: list[str]) -> None:
        """Unsubscribe from market data.

        Args:
            subscription_ids: IDs from subscribe_market_data

        Raises:
            DatafeedError: If subscription ID not found
        """
        for subscription_id in subscription_ids:
            for key, ticker in self._ticks.items():
                if subscription_id in ticker.reqId_callback_map:
                    ticker.reqId_callback_map.pop(subscription_id, None)
                    if DEBUG_TWS_PROVIDER:
                        debug_log(
                            f"Unsubscribed from market data with subscription ID: {subscription_id}"
                        )
                    if not ticker.reqId_callback_map:
                        self._remove_ticker(key)
                    break

    def _get_or_create_ticker(
        self,
        ticker: str,
        resolution: TimeFrame | None = None,
        **kwargs: Any,
    ) -> RTMarketData:
        """Get existing or create new real-time data subscription (sync version).

        Args:
            ticker: Ticker name
            resolution: Time resolution
            exchange: Exchange name (default: SMART)

        Returns:
            RTMarketData ticker instance
        """
        # no need to subscribe again
        if ticker in self._ticks:
            tick = self._ticks[ticker]
            if resolution is not None:
                bar_size = self._map_timeframe_to_tws_bar_size(resolution)
                if bar_size != tick.barSize_setting:
                    # switch resolution
                    if DEBUG_TWS_PROVIDER:
                        debug_log(
                            f"Switching resolution for {ticker} from {tick.barSize_setting} to {bar_size}"
                        )
                    self._tws_client.switch_ticker_resolution(tick, bar_size)
            return tick

        # check max concurrent subscriptions
        while len(self._ticks) >= self._config.max_concurrent_rt_subscriptions:
            stale_ticker = next(
                iter([k for k, t in self._ticks.items() if not t.reqId_callback_map]),
                None,
            )
            assert (
                stale_ticker is not None
            ), "Max concurrent RT subscriptions reached, but no unsubscribable tickers found."
            stale_tick = self._ticks.pop(stale_ticker)
            self._tws_client.remove_ticker(stale_tick)
            if DEBUG_TWS_PROVIDER:
                debug_log(f"remove_ticker {stale_ticker}")

        # defautl resolution if not provided (quotes only)
        contract = self._build_contract(ticker)

        if resolution is None:
            resolution = TimeFrame.DAY_1  # Default resolution for quotes

        if (
            contract.primaryExchange in SMART_EXCHANGES
            and resolution <= TimeFrame.HOUR_1
        ):
            now_us_eastern = datetime.now(us_eastern)
            contract.exchange = (
                "OVERNIGHT"
                if (
                    now_us_eastern.weekday() < 5
                    and (
                        now_us_eastern.time()
                        >= datetime.strptime("20:00:00", "%H:%M:%S").time()
                        or now_us_eastern.time()
                        < datetime.strptime("4:00:00", "%H:%M:%S").time()
                    )
                )
                else "SMART"
            )
        else:
            contract.exchange = contract.primaryExchange

        tick = self._tws_client.create_ticker(
            contract,
            self._map_timeframe_to_tws_bar_size(resolution),
            **kwargs,
        )

        if DEBUG_TWS_PROVIDER:
            debug_log(
                f"Created new ticker for {ticker} with resolution {tick.barSize_setting}"
            )

        self._ticks[ticker] = tick
        return tick

    def _remove_ticker(self, ticker_key: str) -> None:
        assert not self._ticks[ticker_key].reqId_callback_map
        if DEBUG_TWS_PROVIDER:
            debug_log(f"Removing ticker {ticker_key} due to no active subscriptions")
        stale_ticker = self._ticks.pop(ticker_key)
        self._tws_client.remove_ticker(stale_ticker)
        if DEBUG_TWS_PROVIDER:
            debug_log(f"remove_ticker {ticker_key}")

    def shutdown(self) -> None:
        """Perform any necessary cleanup on provider shutdown.

        Idempotent: safe to call multiple times.
        """
        if not hasattr(self, "_tws_client"):
            return  # Already shutdown

        if DEBUG_TWS_PROVIDER:
            debug_log("Shutting down TWSProvider...")
        self._tws_client.shutdown()
        if DEBUG_TWS_PROVIDER:
            debug_log("TWSProvider shutdown complete.")


# Alias for auto-discovery compatibility (provider registry expects TwsProvider)
TwsProvider = TWSProvider

__all__ = ["TWSProvider", "TwsProvider"]
