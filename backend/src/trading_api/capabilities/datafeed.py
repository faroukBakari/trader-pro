"""Datafeed capability interface."""

from abc import ABC, abstractmethod
from collections.abc import Coroutine
from datetime import datetime
from typing import Any, Callable

from trading_api.models.exceptions import TradingApiException
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
            ProviderException: If search fails
        """
        ...

    @abstractmethod
    async def get_symbol_info(
        self,
        ticker_name: str,
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
            ProviderException: If symbol not found or request fails
        """
        ...

    @abstractmethod
    async def get_historical_bars(
        self,
        ticker_name: str,
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
            ProviderException: If request fails
        """
        ...

    @abstractmethod
    async def get_quotes_snapshot(
        self,
        ticker_names: list[str],
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
            ProviderException: If request fails
            TimeoutError: If snapshot exceeds timeout
        """
        ...

    @abstractmethod
    def subscribe_realtime_bars(
        self,
        ticker_name: str,
        resolution: Resolution,
        callback: Callable[[Bar], Coroutine[Any, Any, None]],
        on_error: Callable[[TradingApiException], Coroutine[Any, Any, None]],
        **kwargs: Any,
    ) -> str:
        """Subscribe to real-time bars.

        Args:
            ticker: Ticker chain
            resolution: Bar timeframe (default: 5 seconds)
            callback: Callback invoked for each new bar
            on_error: Optional callback invoked on errors (e.g., timeout, connection lost)
            **kwargs: Provider-specific options (e.g., exchange)

        Returns:
            Subscription ID (for unsubscribe)

        Raises:
            ProviderException: If subscription fails

        [CONTINUOUS]: Callback invoked continuously until unsubscribe.
        [THREAD-SAFE]: Callback may be invoked from provider thread.
        [ERROR-HANDLING]: If on_error is provided, transient errors call it instead of raising.
        """
        ...

    @abstractmethod
    def subscribe_market_data(
        self,
        ticker_names: list[str],
        callback: Callable[[QuoteData], Coroutine[Any, Any, None]],
        on_error: Callable[[TradingApiException], Coroutine[Any, Any, None]],
        **kwargs: Any,
    ) -> list[str]:
        """Subscribe to real-time market data (ticks/quotes).

        Args:
            tickers: List of ticker chains
            callback: Callback invoked for each tick update
            on_error: Optional callback invoked on errors (e.g., timeout, rate limit)
            **kwargs: Provider-specific options (e.g., exchange)

        Returns:
            Subscription ID (for unsubscribe)

        Raises:
            ProviderException: If subscription fails

        [CONTINUOUS]: Callback invoked continuously until unsubscribe.
        [THREAD-SAFE]: Callback may be invoked from provider thread.
        [ERROR-HANDLING]: If on_error is provided, transient errors call it instead of raising.
        """
        ...

    @abstractmethod
    def unsubscribe_realtime_bars(self, subscription_id: str) -> None:
        """Unsubscribe from real-time bars.

        Args:
            subscription_id: ID returned from subscribe_realtime_bars

        Raises:
            ProviderException: If subscription ID not found
        """
        ...

    @abstractmethod
    def unsubscribe_market_data(self, subscription_ids: list[str]) -> None:
        """Unsubscribe from market data.

        Args:
            subscription_id: ID returned from subscribe_market_data

        Raises:
            ProviderException: If subscription ID not found
        """
        ...
