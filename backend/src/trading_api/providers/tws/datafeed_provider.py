"""TWS provider - Interactive Brokers datafeed integration.

Layer 3 of TWS integration:
- Implements DatafeedCapability interface
- Domain conversion (TWS types ↔ core models) via tws_mappers
- Delegates TWS communication to TWSClient (Layer 2)
- Provider-agnostic error translation

Architecture:
- TWSDatafeedProvider (Layer 3): DatafeedCapability impl, domain conversion
- TWSClient (Layer 2): AsyncIO bridge, EWrapper callbacks
- IBSocket (Layer 1): Raw TCP protocol, message framing
"""

import asyncio
import logging
import os
from collections.abc import Coroutine
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from trading_api.capabilities.datafeed import DatafeedCapability
from trading_api.models.common import CapabilitySpec
from trading_api.models.exceptions import ProviderException, TradingApiException
from trading_api.models.market import (
    Bar,
    QuoteData,
    Resolution,
    SearchSymbolResultItem,
    SymbolInfo,
)
from trading_api.models.providers.tws_configs import TWSDatafeedProviderConfig
from trading_api.shared import Provider

from .tws_connection import TWSClient
from .tws_mappers import (
    calculate_tws_duration,
    contract_details_to_symbol_info,
    map_resolution_to_tws_bar_size,
    tws_ticks_to_bar,
)

logger = logging.getLogger(__name__)

us_eastern = ZoneInfo("US/Eastern")

DEBUG_TWS_PROVIDER = os.environ.get("DEBUG_TWS_PROVIDER") == "true"
debug_log = logger.info

SMART_EXCHANGES = {"SMART", "OVERNIGHT", "NYSE", "NASDAQ"}


class SubStream:
    sub_id: str
    reqIds: list[int]
    callbacks: list[
        tuple[
            asyncio.AbstractEventLoop,
            Callable[
                [dict[str, Any], list[str] | None],
                Coroutine[Any, Any, None],
            ],
        ]
    ]


class TWSDatafeedProvider(Provider, DatafeedCapability):
    """TWS provider - implements DatafeedCapability with AsyncIO bridge.

    [LAYER 2]: AsyncIO interface on top of sync TWS callbacks (Layer 1)
    [CONNECTION-OWNER]: Manages EClient and connection lifecycle
    [THREAD-SAFE]: AsyncIO bridge handles cross-thread communication
    [DOMAIN-ONLY]: All public methods use domain models (no TWS types)
    """

    def __init__(self, config: TWSDatafeedProviderConfig | None = None) -> None:
        """Initialize TWSDatafeedProvider.

        Args:
            config: Provider configuration (auto-loaded from env if None)
        """
        self._config: TWSDatafeedProviderConfig = config or TWSDatafeedProviderConfig()

        self._symbol_info_cache: dict[str, list[SymbolInfo]] = {}

        # Layer 1: TWSConnection (callbacks only)
        self._tws_client = TWSClient(
            self._config.host, self._config.port, self._config.client_id
        )

    @classmethod
    def provider_dir(cls) -> Path:
        """Return provider directory path."""
        return Path(__file__).parent

    @classmethod
    def capabilities(cls) -> list[CapabilitySpec]:
        """Return capabilities provided by this provider."""
        return [CapabilitySpec(name="datafeed")]

    @property
    def config(self) -> TWSDatafeedProviderConfig:
        """Return provider configuration.

        [OVERRIDE]: Returns specific TWSDatafeedProviderConfig (not base ProviderConfig).
        """
        return self._config

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
            ProviderException: If search fails
        """
        result = await self._tws_client.reqMatchingSymbols(pattern, **kwargs)

        return [cd.to_search_result() for cd in result]  # Map to domain models

    async def get_symbol_info(
        self,
        ticker_name: str,
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
            ProviderException: If symbol not found or request fails
        """

        session_details = await self._tws_client.req_ticker_details(ticker_name)

        # Use first match (most common case is single result)
        # FIXME: could improve by matching exchange if multiple results
        return contract_details_to_symbol_info(session_details)

    async def get_historical_bars(
        self,
        ticker_name: str,
        start_time: datetime,
        end_time: datetime,
        resolution: Resolution,
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
            resolution: Bar resolution (Resolution enum)
            exchange: Optional exchange filter (default: "SMART")
            timeout: Request timeout in seconds

        Returns:
            List of historical bars (ascending time order)

        Raises:
            ProviderException: If request fails or symbol invalid
            TimeoutError: If request exceeds timeout
        """
        # Map domain parameters to TWS format
        bar_size = map_resolution_to_tws_bar_size(resolution)
        duration_str = calculate_tws_duration(start_time, end_time, resolution)

        # Format datetime in UTC (works universally for all exchanges)
        # TWS accepts: "yyyymmdd hh:mm:ss UTC" format
        end_time_utc = end_time.astimezone(timezone.utc)
        now_utc = datetime.now(timezone.utc)

        if end_time_utc > now_utc:
            end_dt_str = ""
        else:
            end_dt_str = end_time_utc.strftime("%Y%m%d %H:%M:%S UTC")

        cached = await self._tws_client.req_ticker_details(ticker_name)

        # Build list of exchanges to request - always SMART, plus darkpool if available
        contracts = [cached.build_session_contract()]
        darkpool_contract = cached.build_darkpool_contract()
        if darkpool_contract is not None:
            contracts.append(darkpool_contract)

        # Request bars for each exchange in parallel
        results = await asyncio.gather(
            *[
                self._tws_client.reqHistoricalData(
                    contract, end_dt_str, duration_str, bar_size, **kwargs
                )
                for contract in contracts
            ],
            return_exceptions=True,
        )

        # Flatten results, filter out exceptions
        bars = [bar for r in results if not isinstance(r, BaseException) for bar in r]

        return sorted(bars, key=lambda bar: bar.time)

    async def get_quotes_snapshot(
        self,
        ticker_names: list[str],
        **kwargs: Any,
    ) -> list[QuoteData]:
        """Get current market quotes for multiple symbols (snapshot).

        Args:
            symbols: List of symbol names (e.g., ["AAPL", "GOOGL", "MSFT"])
            exchange: Optional exchange filter (default: "SMART")

        Returns:
            List of QuoteData (one per symbol, same order as input)

        Raises:
            ProviderException: If request fails
            TimeoutError: If snapshot exceeds timeout
        """

        cached_list = await asyncio.gather(
            *[
                self._tws_client.req_ticker_details(ticker_name)
                for ticker_name in ticker_names
            ]
        )

        nb_retreis = 2
        while True:
            try:
                return await asyncio.gather(
                    *[
                        self._tws_client.reqQuoteSnapshot(
                            contract,
                            **kwargs,
                        )
                        for contract in cached_list
                    ]
                )

            except TimeoutError:
                nb_retreis -= 1
                if nb_retreis == 0:
                    raise ProviderException(
                        code="PROVIDER_TWS_QUOTE_SNAPSHOT_TIMEOUT",
                        message="Timeout while getting quotes snapshot from TWS provider",
                        provider="tws",
                        capability="datafeed",
                    )
                await asyncio.sleep(0.5)
                quote_list = ", ".join([f"{c.ticker}" for c in cached_list])
                logger.warning(
                    f"TimeoutError when getting quotes snapshot for "
                    f"{quote_list}. Retrying... ({nb_retreis} retries left)"
                )

    async def subscribe_realtime_bars(
        self,
        ticker_name: str,
        resolution: Resolution,
        callback: Callable[[Bar], Coroutine[Any, Any, None]],
        on_error: Callable[[TradingApiException], Coroutine[Any, Any, None]],
        **kwargs: Any,
    ) -> str:
        """Subscribe to real-time bars.

        Args:
            ticker: Ticker string (e.g., "NASDAQ:AAPL")
            resolution: Bar resolution
            callback: Callback for each new bar
            on_error: Optional callback for streaming errors (ProviderException)
            **kwargs: Provider-specific options

        Returns:
            Subscription ID (for unsubscribe)

        Raises:
            ProviderException: If subscription fails or resolution not supported
        """
        bar_size = map_resolution_to_tws_bar_size(resolution)

        async def bar_callback(
            rt_data: dict[str, Any], fields: list[str] | None
        ) -> None:
            if DEBUG_TWS_PROVIDER:
                debug_log(
                    f"Received real-time bar update for {ticker_name} with fields: {fields}"
                )
            await callback(tws_ticks_to_bar(rt_data))

        details = await self._tws_client.req_ticker_details(ticker_name)
        contract = details.build_best_contract()

        return self._tws_client.reqBarDataStream(
            contract,
            bar_size,
            bar_callback,
            on_error=on_error,
            **kwargs,
        )

    async def subscribe_market_data(
        self,
        ticker_name: str,
        callback: Callable[[QuoteData], Coroutine[Any, Any, None]],
        on_error: Callable[[TradingApiException], Coroutine[Any, Any, None]],
        **kwargs: Any,
    ) -> str:
        """Subscribe to real-time market data.

        Args:
            tickers: List of ticker chains
            callback: Callback for tick updates
            on_error: Optional callback for streaming errors (ProviderException)
            **kwargs: Provider-specific options

        Returns:
            List of subscription IDs (one per symbol)

        Raises:
            ProviderException: If subscription fails
        """

        cached = await self._tws_client.req_ticker_details(ticker_name)

        return self._tws_client.reqMktDataStream(
            cached, callback, on_error=on_error, **kwargs
        )

    def unsubscribe_realtime_bars(self, subscription_id: str) -> None:
        """Unsubscribe from real-time bars.

        Args:
            subscription_id: ID from subscribe_realtime_bars

        Raises:
            ProviderException: If subscription ID not found
        """
        # Lookup symbol/exchange from reverse mapping
        self._tws_client.cancelDataSubscription(subscription_id)

    def unsubscribe_market_data(self, subscription_id: str) -> None:
        """Unsubscribe from market data.

        Args:
            subscription_ids: IDs from subscribe_market_data

        Raises:
            ProviderException: If subscription ID not found
        """
        self._tws_client.cancelDataSubscription(subscription_id)

    def shutdown(self) -> None:
        """Perform any necessary cleanup on provider shutdown.

        Idempotent: safe to call multiple times.
        """
        if not hasattr(self, "_tws_client"):
            return  # Already shutdown

        if DEBUG_TWS_PROVIDER:
            debug_log("Shutting down TWSDatafeedProvider...")
        self._tws_client.shutdown()
        if DEBUG_TWS_PROVIDER:
            debug_log("TWSDatafeedProvider shutdown complete.")


# Alias for auto-discovery compatibility (provider registry expects TWSDatafeedProvider)
TWSDatafeedProvider = TWSDatafeedProvider

__all__ = ["TWSDatafeedProvider", "TWSDatafeedProvider"]
