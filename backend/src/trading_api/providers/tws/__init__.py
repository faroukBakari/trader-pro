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
from itertools import count
from pathlib import Path
from typing import Any, Awaitable, Callable
from zoneinfo import ZoneInfo

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
from trading_api.providers.base import Provider
from trading_api.providers.capabilities.datafeed import DatafeedCapability
from trading_api.providers.tws.tws_connection import TWSClient

from .tws_mappers import (
    contract_description_to_search_result,
    contract_details_to_symbol_info,
    tws_bar_to_domain_bar,
    tws_rt_bar_to_domain_bar,
    tws_ticks_to_quote_data,
)

logger = logging.getLogger(__name__)


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

        # Subscription tracking: reqId → asyncio.Task (consumer coroutine)
        self._reqIdAgreggators: dict[int, list[int]] = {}
        self._reqIdAgreggatorsCounter = count()

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

    @property
    def nextReqIdAgreggator(self) -> int:
        return next(self._reqIdAgreggatorsCounter)

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
        # TimeFrame enum values: SEC_5="5", MIN_1="1", HOUR_1="60", DAY_1="1D"
        # Use TimeFrame enum members to avoid duplicate keys
        mapping: dict[str, str] = {
            TimeFrame.SEC_5.value: "5 secs",  # 5 seconds
            TimeFrame.SEC_10.value: "10 secs",  # 10 seconds
            TimeFrame.MIN_1.value: "1 min",  # 1 minute
            TimeFrame.MIN_5.value: "5 mins",  # 5 minutes
            TimeFrame.MIN_15.value: "15 mins",  # 15 minutes
            TimeFrame.MIN_30.value: "30 mins",  # 30 minutes
            TimeFrame.HOUR_1.value: "1 hour",  # 1 hour
            TimeFrame.DAY_1.value: "1 day",  # 1 day
            TimeFrame.WEEK_1.value: "1 week",  # 1 week
            TimeFrame.MONTH_1.value: "1 month",  # 1 month
        }

        bar_size = mapping.get(resolution.value)
        if not bar_size:
            raise DatafeedError(
                f"Unsupported resolution: {resolution.value}. "
                f"Supported: {list(mapping.keys())}"
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
        exchange: str | None = None,
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
        contract = self._build_contract(symbol, exchange=exchange or "SMART")

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
        exchange: str | None = None,
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
        # Build TWS contract
        contract = self._build_contract(symbol, exchange=exchange or "SMART")

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

        try:
            # Request historical data via TWSClient (returns list[BarData])
            tws_bars = await self._tws_client.reqHistoricalData(
                contract,
                end_dt_str,
                duration_str,
                bar_size,
                **kwargs,
            )

            # Convert TWS BarData → domain Bar
            domain_bars = [tws_bar_to_domain_bar(bar) for bar in tws_bars]

            return domain_bars

        except Exception as e:
            raise DatafeedError(
                f"Failed to get historical bars for {symbol}: {e}"
            ) from e

    async def get_quotes_snapshot(
        self,
        symbols: list[str],
        exchange: str | None = None,
        **kwargs: Any,
    ) -> list[QuoteData]:
        """Get current market quotes for multiple symbols (snapshot).

        [ASYNC-BRIDGE]: Wraps sync TWS callbacks with async Future.
        [ACCUMULATION]: TWS sends multiple tickPrice/tickSize callbacks, accumulates until tickSnapshotEnd.
        [DOMAIN-ONLY]: Returns domain QuoteData models (no TWS types).

        Args:
            symbols: List of symbol names (e.g., ["AAPL", "GOOGL", "MSFT"])
            exchange: Optional exchange filter (default: "SMART")
            timeout: Request timeout in seconds (default: 15s for snapshot completion)

        Returns:
            List of QuoteData (one per symbol, same order as input)

        Raises:
            DatafeedError: If request fails
            TimeoutError: If snapshot exceeds timeout
        """

        # Request quotes for all symbols concurrently
        tasks = [
            self._tws_client.reqMktDataSnapshot(
                self._build_contract(symbol, exchange=exchange or "SMART"),
                **kwargs,
            )
            for symbol in symbols
        ]

        results_raw = await asyncio.gather(*tasks)

        # Await all snapshots with timeout
        try:
            results: list[QuoteData] = [
                tws_ticks_to_quote_data(symbol, ticks)
                for symbol, ticks in zip(symbols, results_raw)
                if isinstance(ticks, dict)
            ]

            return results

        except asyncio.TimeoutError:
            raise DatafeedError("Quote snapshot timed out")
        except Exception as e:
            raise DatafeedError(f"Failed to get quote snapshot: {e}") from e

    def subscribe_realtime_bars(
        self,
        symbol: str,
        callback: Callable[[Bar], Awaitable[None]],
        exchange: str | None = None,
        **kwargs: Any,
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
            DatafeedError: If subscription fails or resolution not supported
        """

        contract = self._build_contract(symbol, exchange=exchange or "SMART")

        async def maped_callback(*args: Any) -> None:
            await callback(tws_rt_bar_to_domain_bar(*args))

        return self._tws_client.reqRealTimeBars(
            contract,
            maped_callback,
            **kwargs,
        )

    def subscribe_market_data(
        self,
        symbols: list[str],
        callback: Callable[[QuoteData], Awaitable[None]],
        exchange: str | None = None,
        **kwargs: Any,
    ) -> list[int]:
        """Subscribe to real-time market data.

        [NOT-IMPLEMENTED]: Placeholder for future implementation.

        Args:
            symbols: Symbol name
            callback: Callback for tick updates
            exchange: Optional exchange filter

        Returns:
            Subscription ID

        Raises:
            DatafeedError: Not yet implemented
        """

        def mapped_callback_factory(
            symbol: str,
        ) -> Callable[[dict[str, float]], Awaitable[None]]:
            async def mapped_callback(ticks: dict[str, float]) -> None:
                await callback(tws_ticks_to_quote_data(symbol, ticks))

            return mapped_callback

        reqIds = [
            self._tws_client.reqMktData(
                self._build_contract(symbol, exchange=exchange or "SMART"),
                mapped_callback_factory(symbol),
                **kwargs,
            )
            for symbol in symbols
        ]

        return reqIds

    def unsubscribe_realtime_bars(self, subscription_id: int) -> None:
        """Unsubscribe from real-time bars.

        Args:
            subscription_id: ID from subscribe_realtime_bars

        Raises:
            DatafeedError: If subscription ID not found
        """
        self._tws_client.cancelRealTimeBars(subscription_id)

    def unsubscribe_market_data(self, subscription_ids: list[int]) -> None:
        """Unsubscribe from market data.

        [NOT-IMPLEMENTED]: Placeholder for future implementation.

        Args:
            subscription_id: ID from subscribe_market_data

        Raises:
            DatafeedError: Not yet implemented
        """
        for reqId in subscription_ids:
            self._tws_client.cancelMktData(reqId)

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
