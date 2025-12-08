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
    Resolution,
    SearchSymbolResultItem,
    SymbolInfo,
)
from trading_api.models.providers.tws.tws_configs import TWSProviderConfig
from trading_api.providers.capabilities.datafeed import DatafeedCapability
from trading_api.providers.tws.tws_connection import TWSClient
from trading_api.shared import Provider

from .tws_mappers import (
    build_contract,
    calculate_tws_duration,
    contract_description_to_search_result,
    contract_details_to_symbol_info,
    map_resolution_to_tws_bar_size,
    ticker_name,
    tws_bar_to_domain_bar,
    tws_ticks_to_bar,
    tws_ticks_to_quote_data,
)

logger = logging.getLogger(__name__)

us_eastern = ZoneInfo("US/Eastern")

DEBUG_TWS_PROVIDER = os.environ.get("DEBUG_TWS_PROVIDER") == "true"
debug_log = logger.info

SMART_EXCHANGES = {"SMART", "NYSE", "NASDAQ"}


class SubStream:
    sub_id: str
    reqIds: list[int]
    callbacks: list[
        tuple[
            asyncio.AbstractEventLoop,
            Callable[
                [dict[str, Any], list[str] | None],
                Awaitable[None],
            ],
        ]
    ]


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

        # Reverse mapping: subscription_id → (symbol, exchange, callback_type)
        self._subscriptions: dict[str, list[int]] = {}
        self._callbacks: dict[
            str,
            tuple[
                asyncio.AbstractEventLoop,
                Callable[
                    [dict[str, Any], list[str] | None],
                    Awaitable[None],
                ],
            ],
        ] = {}

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
        contract = build_contract(ticker)

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
            DatafeedError: If request fails or symbol invalid
            TimeoutError: If request exceeds timeout
        """
        # Map domain parameters to TWS format
        bar_size = map_resolution_to_tws_bar_size(resolution)
        duration_str = calculate_tws_duration(start_time, end_time, resolution)

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
            contract = build_contract(ticker)
            exchanges = [contract.primaryExchange]
            if contract.primaryExchange in SMART_EXCHANGES and resolution in [
                Resolution.MIN_1,
                Resolution.MIN_5,
                Resolution.MIN_15,
                Resolution.MIN_30,
                Resolution.HOUR_1,
                Resolution.HOUR_2,
                Resolution.HOUR_4,
            ]:
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
        timeout: float = 1.0,
        **kwargs: Any,
    ) -> list[QuoteData]:
        """Get current market quotes for multiple symbols (snapshot).

        Args:
            symbols: List of symbol names (e.g., ["AAPL", "GOOGL", "MSFT"])
            exchange: Optional exchange filter (default: "SMART")

        Returns:
            List of QuoteData (one per symbol, same order as input)

        Raises:
            DatafeedError: If request fails
            TimeoutError: If snapshot exceeds timeout
        """

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

        contracts: list[Contract] = []
        for ticker in tickers:
            contract = build_contract(ticker)
            if contract.primaryExchange in SMART_EXCHANGES:
                contract.exchange = smart_exchange
            contracts.append(contract)
            logger.info(
                f"Getting quotes snapshot for tickers: {ticker} for exchange: {contract.exchange}"
            )

        nb_retreis = 3
        while True:
            try:
                results_raw = await asyncio.gather(
                    *[
                        self._tws_client.reqQuoteSnapshot(
                            contract,
                            timeout=1,
                            **kwargs,
                        )
                        for contract in contracts
                    ]
                )
                return [tws_ticks_to_quote_data(result) for result in results_raw]
            except TimeoutError:
                nb_retreis -= 1
                if nb_retreis == 0:
                    raise
                await asyncio.sleep(0.2)
                logger.warning(
                    f"TimeoutError when getting quotes snapshot. Retrying... ({nb_retreis} retries left)"
                )

    def subscribe_realtime_bars(
        self,
        ticker: str,
        resolution: Resolution,
        callback: Callable[[Bar], Awaitable[None]],
        **kwargs: Any,
    ) -> str:
        """Subscribe to real-time bars.

        Args:
            symbol: Symbol name
            resolution: Bar resolution
            callback: Callback for each new bar
            exchange: Optional exchange filter

        Returns:
            Subscription ID (for unsubscribe)

        Raises:
            DatafeedError: If subscription fails or resolution not supported
        """

        bar_size = map_resolution_to_tws_bar_size(resolution)

        async def bar_callback(
            rt_data: dict[str, Any], fields: list[str] | None
        ) -> None:
            if fields is None or any(f.startswith("bar_") for f in fields):
                if DEBUG_TWS_PROVIDER:
                    debug_log(
                        f"Received real-time bar update for {ticker} with fields: {fields}"
                    )
                await callback(tws_ticks_to_bar(rt_data))

        contract = build_contract(ticker)
        if contract.primaryExchange in SMART_EXCHANGES and resolution in [
            Resolution.MIN_1,
            Resolution.MIN_5,
            Resolution.MIN_15,
            Resolution.MIN_30,
            Resolution.HOUR_1,
            Resolution.HOUR_2,
            Resolution.HOUR_4,
        ]:
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
        return self._tws_client.reqBarDataStream(
            contract,
            bar_size,
            bar_callback,
            **kwargs,
        )

    def subscribe_market_data(
        self,
        tickers: list[str],
        callback: Callable[[QuoteData], Awaitable[None]],
        **kwargs: Any,
    ) -> list[str]:
        """Subscribe to real-time market data.

        Args:
            symbols: List of symbol names
            callback: Callback for tick updates
            exchange: Optional exchange filter

        Returns:
            List of subscription IDs (one per symbol)

        Raises:
            DatafeedError: If subscription fails
        """

        # Register quote callback on the ticker
        async def quote_callback(
            rt_data: dict[str, Any], fields: list[str] | None
        ) -> None:
            if fields is not None and any(f in {"bid", "ask", "last"} for f in fields):
                if DEBUG_TWS_PROVIDER:
                    debug_log(
                        f"Received market data update for {rt_data.get('ticker_name', 'UNKNOWN')}"
                        f" with fields: {fields}"
                    )
                await callback(tws_ticks_to_quote_data(rt_data))

        sub_ids = []
        for ticker in tickers:
            contract = build_contract(ticker)
            if contract.primaryExchange in SMART_EXCHANGES:
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
            sub_ids.append(
                self._tws_client.reqMktDataStream(
                    build_contract(ticker), quote_callback, **kwargs
                )
            )

        return sub_ids

    def unsubscribe_realtime_bars(self, subscription_id: str) -> None:
        """Unsubscribe from real-time bars.

        Args:
            subscription_id: ID from subscribe_realtime_bars

        Raises:
            DatafeedError: If subscription ID not found
        """
        # Lookup symbol/exchange from reverse mapping
        self._tws_client.cancelBarDataStream(subscription_id)

    def unsubscribe_market_data(self, subscription_ids: list[str]) -> None:
        """Unsubscribe from market data.

        Args:
            subscription_ids: IDs from subscribe_market_data

        Raises:
            DatafeedError: If subscription ID not found
        """
        for sub_id in subscription_ids:
            self._tws_client.cancelMktDataStream(sub_id)

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
