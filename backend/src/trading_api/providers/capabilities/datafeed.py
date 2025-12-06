"""Datafeed capability interface."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Awaitable, Callable

from trading_api.models.market import (
    Bar,
    QuoteData,
    Resolution,
    SearchSymbolResultItem,
    SymbolInfo,
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
        ticker: str,
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
        ticker: str,
        start_time: datetime,
        end_time: datetime,
        resolution: Resolution,
        **kwargs: Any,
    ) -> list[Bar]:
        """Get historical OHLCV bars.

        Args:
            ticker: ticker chain
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
        tickers: list[str],
        **kwargs: Any,
    ) -> list[QuoteData]:
        """Get current market quotes for multiple tickers (snapshot).

        Args:
            tickers: List of ticker chains
            exchange: Optional exchange filter
            timeout: Request timeout in seconds

        Returns:
            List of QuoteData (one per ticker)

        Raises:
            DatafeedError: If request fails
            TimeoutError: If snapshot exceeds timeout
        """
        ...

    @abstractmethod
    def subscribe_realtime_bars(
        self,
        ticker: str,
        resolution: Resolution,
        callback: Callable[[Bar], Awaitable[None]],
        **kwargs: Any,
    ) -> str:
        """Subscribe to real-time bars.

        Args:
            ticker: Ticker chain
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
        tickers: list[str],
        callback: Callable[[QuoteData], Awaitable[None]],
        **kwargs: Any,
    ) -> list[str]:
        """Subscribe to real-time market data (ticks/quotes).

        Args:
            tickers: List of ticker chains
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
    def unsubscribe_realtime_bars(self, subscription_id: str) -> None:
        """Unsubscribe from real-time bars.

        Args:
            subscription_id: ID returned from subscribe_realtime_bars

        Raises:
            DatafeedError: If subscription ID not found
        """
        ...

    @abstractmethod
    def unsubscribe_market_data(self, subscription_ids: list[str]) -> None:
        """Unsubscribe from market data.

        Args:
            subscription_id: ID returned from subscribe_market_data

        Raises:
            DatafeedError: If subscription ID not found
        """
        ...
