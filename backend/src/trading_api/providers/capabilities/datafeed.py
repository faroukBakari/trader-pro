"""Datafeed capability interface."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Callable

from trading_api.models.market import (
    Bar,
    QuoteData,
    SearchSymbolResultItem,
    SymbolInfo,
    TimeFrame,
)


class DatafeedCapability(ABC):
    """Datafeed capability interface.

    Providers implementing this capability can provide market data including:
    - Symbol search
    - Symbol metadata
    - Historical bars (OHLCV)
    - Real-time bar subscriptions
    - Real-time quote subscriptions

    [PROVIDER-AGNOSTIC]: All methods use domain models only (no provider-specific types).
    [ASYNC]: All data-fetching methods are async for I/O efficiency.
    """

    @abstractmethod
    async def search_symbols(
        self,
        pattern: str,
        **kwargs: Any,
    ) -> list[SearchSymbolResultItem]:
        """Search for symbols matching pattern.

        Args:
            pattern: Search pattern (symbol name, description, etc.)
            timeout: Request timeout in seconds

        Returns:
            List of matching symbols

        Raises:
            TimeoutError: If request exceeds timeout
            DatafeedError: If search fails
        """
        ...

    @abstractmethod
    async def get_symbol_info(
        self,
        symbol: str,
        **kwargs: Any,
    ) -> SymbolInfo:
        """Get detailed symbol information.

        Args:
            symbol: Symbol name (e.g., "AAPL")
            exchange: Optional exchange filter
            timeout: Request timeout in seconds

        Returns:
            Detailed symbol metadata

        Raises:
            TimeoutError: If request exceeds timeout
            DatafeedError: If symbol not found or request fails
        """
        ...

    @abstractmethod
    async def get_historical_bars(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime,
        resolution: TimeFrame,
        **kwargs: Any,
    ) -> list[Bar]:
        """Get historical OHLCV bars.

        Args:
            symbol: Symbol name
            start_time: Start of time range (inclusive)
            end_time: End of time range (inclusive)
            resolution: Bar timeframe
            exchange: Optional exchange filter
            timeout: Request timeout in seconds

        Returns:
            List of historical bars (ascending time order)

        Raises:
            TimeoutError: If request exceeds timeout
            DatafeedError: If request fails
        """
        ...

    @abstractmethod
    async def get_quotes_snapshot(
        self,
        symbols: list[str],
        **kwargs: Any,
    ) -> list[QuoteData]:
        """Get current market quotes for multiple symbols (snapshot).

        Args:
            symbols: List of symbol names
            exchange: Optional exchange filter
            timeout: Request timeout in seconds

        Returns:
            List of QuoteData (one per symbol)

        Raises:
            DatafeedError: If request fails
            TimeoutError: If snapshot exceeds timeout
        """
        ...

    @abstractmethod
    def subscribe_realtime_bars(
        self,
        symbol: str,
        callback: Callable[[Bar], None],
        **kwargs: Any,
    ) -> int:
        """Subscribe to real-time bars.

        Args:
            symbol: Symbol name
            callback: Callback invoked for each new bar
            exchange: Optional exchange filter
            resolution: Bar timeframe (default: 5 seconds)

        Returns:
            Subscription ID (for unsubscribe)

        Raises:
            DatafeedError: If subscription fails

        [CONTINUOUS]: Callback invoked continuously until unsubscribe.
        [THREAD-SAFE]: Callback may be invoked from provider thread.
        """
        ...

    @abstractmethod
    def subscribe_market_data(
        self,
        symbols: list[str],
        callback: Callable[[QuoteData], None],
        **kwargs: Any,
    ) -> list[int]:
        """Subscribe to real-time market data (ticks/quotes).

        Args:
            symbol: Symbol name
            callback: Callback invoked for each tick update
            exchange: Optional exchange filter

        Returns:
            Subscription ID (for unsubscribe)

        Raises:
            DatafeedError: If subscription fails

        [CONTINUOUS]: Callback invoked continuously until unsubscribe.
        [THREAD-SAFE]: Callback may be invoked from provider thread.
        """
        ...

    @abstractmethod
    def unsubscribe_realtime_bars(self, subscription_id: int) -> None:
        """Unsubscribe from real-time bars.

        Args:
            subscription_id: ID returned from subscribe_realtime_bars

        Raises:
            DatafeedError: If subscription ID not found
        """
        ...

    @abstractmethod
    def unsubscribe_market_data(self, subscription_ids: list[int]) -> None:
        """Unsubscribe from market data.

        Args:
            subscription_id: ID returned from subscribe_market_data

        Raises:
            DatafeedError: If subscription ID not found
        """
        ...
