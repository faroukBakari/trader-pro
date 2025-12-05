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
from datetime import datetime
from pathlib import Path
from re import sub
from tkinter import N
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
        self._tickers: dict[str, RTMarketData] = {}
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
        symbol: str,
        exchange: str = "SMART",
        sec_type: str = "STK",
        currency: str = "USD",
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
        contract = Contract()
        contract.symbol = symbol
        contract.secType = sec_type
        contract.exchange = exchange
        contract.currency = currency
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
        symbol: str,
        exchange: str = "SMART",
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
        if exchange == "SMART":
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
            smart_exchange = exchange

        # Build TWS Contract for the request
        contract = self._build_contract(symbol, exchange=smart_exchange)

        try:
            # Get contract details via TWSClient (returns list)
            contract_details_list = await self._tws_client.reqContractDetails(
                contract, **kwargs
            )

            if not contract_details_list:
                raise DatafeedError(f"Symbol not found: {symbol}")

            # Use first match (most common case is single result)
            return contract_details_to_symbol_info(contract_details_list[0])

        except DatafeedError:
            raise
        except Exception as e:
            raise DatafeedError(f"Failed to get symbol info for {symbol}: {e}") from e

    async def get_historical_bars(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime,
        resolution: TimeFrame,
        exchange: str = "SMART",
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
        exchanges = [exchange]
        if exchange == "SMART" and resolution > TimeFrame.HOUR_1:
            exchanges.append("OVERNIGHT")  # Add ISLAND for NASDAQ stocks
        try:
            for exch in exchanges:
                # Build TWS contract
                contract = self._build_contract(symbol, exchange=exch)
                # Request historical data via TWSClient (returns list[BarData])
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
                f"Failed to get historical bars for {symbol}: {e}"
            ) from e

    async def get_quotes_snapshot(
        self,
        symbols: list[str],
        exchange: str = "SMART",
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
            for symbol in symbols:
                existing = f"{symbol}:{exchange}" in self._tickers
                ticker = self._get_or_create_ticker(symbol, exchange)
                if existing:
                    await asyncio.sleep(0.2)  # Give time for existing ticker to update
                results.append(tws_ticks_to_quote_data(ticker))

            return results

        except Exception as e:
            raise DatafeedError(f"Failed to get quote snapshot: {e}") from e

    def subscribe_realtime_bars(
        self,
        symbol: str,
        resolution: TimeFrame,
        callback: Callable[[Bar], Awaitable[None]],
        exchange: str = "SMART",
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

        subscription_id = "subscribe_realtime_bars" + "_" + symbol + "_" + exchange

        loop = asyncio.get_event_loop()

        async def bar_callback(rt_data: RTMarketData, fields: list[str] | None) -> None:
            if fields is None or any(f.startswith("bar_") for f in fields):
                logger.info(
                    f"Received real-time bar update for {symbol} with fields: {fields}"
                )
                await callback(tws_ticks_to_bar(rt_data))

        # Get or create unified ticker via helper
        ticker = self._get_or_create_ticker(symbol, exchange, resolution, **kwargs)

        ticker.reqId_callback_map[subscription_id] = (loop, bar_callback)

        logger.info(
            f"Subscribed to real-time bars for {symbol} on exchange {exchange or 'SMART'}"
        )
        return subscription_id

    def subscribe_market_data(
        self,
        symbols: list[str],
        callback: Callable[[QuoteData], Awaitable[None]],
        exchange: str = "SMART",
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

        for symbol in symbols:
            subscription_id = "subscribe_market_data" + "_" + symbol + "_" + exchange
            loop = asyncio.get_event_loop()

            # Register quote callback on the ticker
            async def quote_callback(
                rt_data: RTMarketData, fields: list[str] | None
            ) -> None:
                if fields is not None and any(
                    f in {"bid", "ask", "last"} for f in fields
                ):
                    logger.info(
                        f"Received market data update for {symbol} with fields: {fields}"
                    )
                    await callback(tws_ticks_to_quote_data(rt_data))

            ticker = self._get_or_create_ticker(symbol, exchange, **kwargs)

            ticker.reqId_callback_map[subscription_id] = (loop, quote_callback)

            subscription_ids.append(subscription_id)

        logger.info(
            f"Subscribed to market data for symbols: {symbols} on exchange {exchange or 'SMART'}"
        )
        return subscription_ids

    def unsubscribe_realtime_bars(self, subscription_id: str) -> None:
        """Unsubscribe from real-time bars.

        Args:
            subscription_id: ID from subscribe_realtime_bars

        Raises:
            DatafeedError: If subscription ID not found
        """
        # Lookup symbol/exchange from reverse mapping
        for key, ticker in self._tickers.items():
            if subscription_id in ticker.reqId_callback_map:
                ticker.reqId_callback_map.pop(subscription_id, None)
                logger.info(
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
            for key, ticker in self._tickers.items():
                if subscription_id in ticker.reqId_callback_map:
                    ticker.reqId_callback_map.pop(subscription_id, None)
                    logger.info(
                        f"Unsubscribed from market data with subscription ID: {subscription_id}"
                    )
                    if not ticker.reqId_callback_map:
                        self._remove_ticker(key)
                    break

    def _get_existing_ticker(
        self,
        symbol: str,
        exchange: str = "SMART",
    ) -> RTMarketData | None:
        """Get existing real-time data subscription if it exists.

        Args:
            symbol: Symbol name
            exchange: Exchange name (default: SMART)
        """
        key = f"{symbol}:{exchange}"
        if key in self._tickers:
            return self._tickers[key]
        return None

    def _get_or_create_ticker(
        self,
        symbol: str,
        exchange: str = "SMART",
        resolution: TimeFrame | None = None,
        **kwargs: Any,
    ) -> RTMarketData:
        """Get existing or create new real-time data subscription (sync version).

        Args:
            symbol: Symbol name
            resolution: Time resolution
            exchange: Exchange name (default: SMART)

        Returns:
            RTMarketData ticker instance
        """
        key = f"{symbol}:{exchange}"

        # no need to subscribe again
        if key in self._tickers:
            ticker = self._tickers[key]
            if resolution is not None:
                bar_size = self._map_timeframe_to_tws_bar_size(resolution)
                if bar_size != ticker.barSize_setting:
                    # switch resolution
                    logger.info(
                        f"Switching resolution for {symbol} from {ticker.barSize_setting} to {bar_size}"
                    )
                    self._tws_client.switch_ticker(ticker, bar_size)
            return ticker

        # check max concurrent subscriptions
        while len(self._tickers) >= self._config.max_concurrent_rt_subscriptions:
            stale_ticker_key = next(
                iter([k for k, t in self._tickers.items() if not t.reqId_callback_map]),
                None,
            )
            assert (
                stale_ticker_key is not None
            ), "Max concurrent RT subscriptions reached, but no unsubscribable tickers found."
            stale_ticker = self._tickers.pop(stale_ticker_key)
            self._tws_client.remove_ticker(stale_ticker)
            logger.info(f"remove_ticker {stale_ticker_key}")

        # defautl resolution if not provided (quotes only)
        if resolution is None:
            resolution = TimeFrame.DAY_1  # Default resolution for quotes
        if exchange == "SMART" and resolution <= TimeFrame.HOUR_1:
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
            smart_exchange = exchange

        ticker = self._tws_client.create_ticker(
            self._build_contract(symbol, exchange=smart_exchange),
            self._map_timeframe_to_tws_bar_size(resolution),
            **kwargs,
        )

        logger.info(
            f"Created new ticker for {symbol} on exchange {exchange or 'SMART'} with resolution {ticker.barSize_setting}"
        )

        self._tickers[key] = ticker
        return ticker

    def _remove_ticker(self, ticker_key: str) -> None:
        assert not self._tickers[ticker_key].reqId_callback_map
        logger.info(f"Removing ticker {ticker_key} due to no active subscriptions")
        stale_ticker = self._tickers.pop(ticker_key)
        self._tws_client.remove_ticker(stale_ticker)
        logger.info(f"remove_ticker {ticker_key}")

    def shutdown(self) -> None:
        """Perform any necessary cleanup on provider shutdown.

        Idempotent: safe to call multiple times.
        """
        if not hasattr(self, "_tws_client"):
            return  # Already shutdown

        logger.info("Shutting down TWSProvider...")
        self._tws_client.shutdown()
        logger.info("TWSProvider shutdown complete.")


# Alias for auto-discovery compatibility (provider registry expects TwsProvider)
TwsProvider = TWSProvider

__all__ = ["TWSProvider", "TwsProvider"]
