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

import logging
from datetime import datetime
from pathlib import Path
from typing import Callable

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

    # === Provider Implementation ===

    def __del__(self) -> None:
        """Cleanup TWS connection on deletion."""
        try:
            self._tws_client.disconnect()
        except Exception as e:
            logger.warning(f"Error disconnecting TWS client: {e}")

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
            DatafeedError: If search fails
        """
        result = await self._tws_client.reqMatchingSymbols(pattern)

        return [contract_description_to_search_result(cd) for cd in result]

    async def get_symbol_info(
        self,
        symbol: str,
        exchange: str | None = None,
        timeout: float = 5.0,
    ) -> SymbolInfo:
        """Get detailed symbol information.

        [ASYNC-BRIDGE]: Wraps sync TWS callback with async Future.
        [ACCUMULATION]: TWS may return multiple ContractDetails, we use first match.
        [DOMAIN-ONLY]: Returns domain SymbolInfo (no TWS types).

        Args:
            symbol: Symbol name (e.g., "AAPL")
            exchange: Optional exchange filter (default: "SMART" for smart routing)
            timeout: Request timeout in seconds

        Returns:
            Detailed symbol metadata (SymbolInfo)

        Raises:
            DatafeedError: If symbol not found or request fails
        """
        # Build TWS Contract for the request
        contract = self._build_contract(symbol, exchange=exchange or "SMART")

        try:
            # Get contract details via TWSClient (returns list)
            contract_details_list = await self._tws_client.reqContractDetails(contract)

            if not contract_details_list:
                raise DatafeedError(f"Symbol not found: {symbol}")

            # Use first match (most common case is single result)
            return contract_details_to_symbol_info(contract_details_list[0])

        except DatafeedError:
            raise
        except Exception as e:
            logger.error(f"Error getting symbol info for {symbol}: {e}")
            raise DatafeedError(f"Failed to get symbol info for {symbol}: {e}") from e

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
            DatafeedError: If request fails
        """
        raise DatafeedError("get_historical_bars not yet implemented")

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
            DatafeedError: If subscription fails or resolution not supported
        """
        raise DatafeedError("subscribe_realtime_bars not yet implemented")

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
            DatafeedError: Not yet implemented
        """
        raise DatafeedError("subscribe_market_data not yet implemented")

    def unsubscribe_realtime_bars(self, subscription_id: int) -> None:
        """Unsubscribe from real-time bars.

        Args:
            subscription_id: ID from subscribe_realtime_bars

        Raises:
            DatafeedError: If subscription ID not found
        """
        raise DatafeedError("unsubscribe_realtime_bars not yet implemented")

    def unsubscribe_market_data(self, subscription_id: int) -> None:
        """Unsubscribe from market data.

        [NOT-IMPLEMENTED]: Placeholder for future implementation.

        Args:
            subscription_id: ID from subscribe_market_data

        Raises:
            DatafeedError: Not yet implemented
        """
        raise DatafeedError("unsubscribe_market_data not yet implemented")


# Alias for auto-discovery compatibility (provider registry expects TwsProvider)
TwsProvider = TWSProvider

__all__ = ["TWSProvider", "TwsProvider"]
