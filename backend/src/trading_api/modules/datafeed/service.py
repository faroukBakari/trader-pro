"""
Datafeed service for handling market data operations
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, List, Optional

from trading_api.models import (
    Bar,
    BarsSubscriptionRequest,
    DatafeedConfiguration,
    QuoteData,
    QuoteDataSubscriptionRequest,
    SearchSymbolResultItem,
    SymbolInfo,
)
from trading_api.models.common import CapabilitySpec
from trading_api.models.market import TimeFrame
from trading_api.providers.capabilities.datafeed import DatafeedCapability
from trading_api.shared.ws.ws_router import WsRouteService

logger = logging.getLogger(__name__)


class DatafeedService(WsRouteService):
    """Service for handling datafeed operations"""

    @classmethod
    def capabilities(cls) -> list[CapabilitySpec]:
        """Return required capabilities for datafeed service.

        Requires datafeed capability from provider (e.g., TWSProvider).

        Returns:
            List with datafeed capability requirement
        """
        return [CapabilitySpec(name="datafeed")]

    @property
    def datafeed_provider(self) -> DatafeedCapability:
        """Cached O(1) lookup - type-safe provider access.

        Returns:
            DatafeedCapability provider instance

        Raises:
            RuntimeError: If datafeed provider not available
        """
        provider = self.get_capability_provider("datafeed")
        # Type assertion: provider must implement DatafeedCapability (validated at init)
        assert isinstance(provider, DatafeedCapability)
        return provider

    def __init__(
        self,
        module_dir: Path,
        *,  # Force keyword-only arguments
        symbols_file_path: Optional[str] = None,
        providers: list | None = None,
    ):
        """Initialize the datafeed service

        Args:
            module_dir: Path to the module directory
            symbols_file_path: Path to symbols JSON file. If None, uses
                default embedded symbols.
            providers: Provider instances for capabilities (unused, for interface compatibility)
        """
        super().__init__(module_dir, providers=providers)
        self.configuration = DatafeedConfiguration()
        self.symbols_file_path = symbols_file_path
        self._symbols: List[SymbolInfo] = []
        self._sample_bars: List[Bar] = []
        # Track provider subscription IDs for each topic (for cleanup)
        self._topic_to_subscription_id: dict[str, int | list[int]] = {}

    # === Helper Methods ===

    def _parse_ticker(self, ticker: str) -> tuple[str, str]:
        """Parse ticker format 'SYMBOL:EXCHANGE' into components.

        Args:
            ticker: Ticker in format 'SYMBOL:EXCHANGE' or just 'SYMBOL'

        Returns:
            Tuple of (symbol, exchange)
                - If ticker contains ':', returns (SYMBOL, EXCHANGE)
                - If ticker has no ':', returns (SYMBOL, 'SMART')

        Examples:
            >>> self._parse_ticker('AAPL:NASDAQ')
            ('AAPL', 'NASDAQ')
            >>> self._parse_ticker('GOOGL')
            ('GOOGL', 'SMART')
        """
        if ":" in ticker:
            symbol, exchange = ticker.split(":", 1)
            return symbol.strip(), exchange.strip()
        return ticker.strip(), "SMART"

    def _convert_resolution_to_timeframe(self, resolution: str) -> TimeFrame:
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
        resolution_map: dict[str, TimeFrame] = {
            "1": TimeFrame.MIN_1,
            "5": TimeFrame.MIN_5,
            "15": TimeFrame.MIN_15,
            "30": TimeFrame.MIN_30,
            "60": TimeFrame.HOUR_1,
            "1D": TimeFrame.DAY_1,
            "1W": TimeFrame.WEEK_1,
            "1M": TimeFrame.MONTH_1,
        }

        if resolution not in resolution_map:
            raise ValueError(
                f"Unsupported resolution: {resolution}. "
                f"Supported: {list(resolution_map.keys())}"
            )

        return resolution_map[resolution]

    async def create_topic(
        self, topic: str, topic_update: Callable[[Any], Awaitable[None]]
    ) -> None:
        """Parse topic and create appropriate subscription task.

        Topic formats:
            - bars:{"resolution":"1D","symbol":"AAPL"}
            - quotes:{"symbols":["AAPL","GOOGL"],"fast_symbols":["MSFT"]}

        Raises:
            ValueError: If topic format is invalid or unknown topic type
            json.JSONDecodeError: If JSON params cannot be parsed
        """

        if topic not in self._topic_to_subscription_id:
            logger.info(f"New topic in DatafeedService : {topic}")
            # Parse topic format: "topic_type:{json_params}"
            if ":" not in topic:
                raise ValueError(f"Invalid topic format: {topic}")

            topic_type, params_json = topic.split(":", 1)

            # TODO: need to validate create_topic params/types against provider capabilities at runtime

            if topic_type == "bars":
                # Parse the JSON params part / Validate model
                params_dict = json.loads(params_json)
                subscription_request = BarsSubscriptionRequest.model_validate(
                    params_dict
                )

                subscription_id = self.datafeed_provider.subscribe_realtime_bars(
                    symbol=subscription_request.symbol, callback=topic_update
                )

                # Track subscription ID for cleanup
                self._topic_to_subscription_id[topic] = subscription_id
            elif topic_type == "quotes":
                # Parse the JSON params part / Validate model
                params_dict = json.loads(params_json)
                quote_subscription_request = (
                    QuoteDataSubscriptionRequest.model_validate(params_dict)
                )

                # Combine all symbols (both slow and fast)
                all_symbols = list(
                    set(
                        quote_subscription_request.symbols
                        + quote_subscription_request.fast_symbols
                    )
                )

                if not all_symbols:
                    raise ValueError("No symbols provided for quote subscription")

                # Subscribe to market data for all symbols via provider (returns list of subscription IDs)
                subscription_ids = self.datafeed_provider.subscribe_market_data(
                    symbols=all_symbols, callback=topic_update
                )

                # Track subscription IDs for cleanup (list for quotes, int for bars)
                self._topic_to_subscription_id[topic] = subscription_ids
            else:
                raise ValueError(f"Unknown topic type: {topic_type}")

    def remove_topic(self, topic: str) -> None:
        """Remove topic and cleanup subscriptions.

        Handles both legacy asyncio tasks and provider subscriptions.
        """
        logger.info(f"Deleting topic queue for: {topic}")

        # Unsubscribe from provider if subscription exists
        subscription_id = self._topic_to_subscription_id.get(topic)
        if subscription_id is not None:
            # Determine topic type from topic string
            if ":" in topic:
                topic_type = topic.split(":", 1)[0]

                if topic_type == "bars":
                    # Single subscription ID for bars (always int)
                    if isinstance(subscription_id, int):
                        logger.info(
                            f"Unsubscribing from bars: subscription ID {subscription_id}"
                        )
                        self.datafeed_provider.unsubscribe_realtime_bars(
                            subscription_id
                        )
                elif topic_type == "quotes":
                    # Multiple subscription IDs for quotes (one per symbol)
                    if isinstance(subscription_id, list):
                        logger.info(
                            f"Unsubscribing from quotes: subscription IDs {subscription_id}"
                        )
                        self.datafeed_provider.unsubscribe_market_data(subscription_id)
                    else:
                        logger.info(
                            f"Unsubscribing from quotes: subscription ID {subscription_id}"
                        )
                        self.datafeed_provider.unsubscribe_market_data(
                            [subscription_id]
                        )

            self._topic_to_subscription_id.pop(topic, None)

    def get_configuration(self) -> DatafeedConfiguration:
        """Get datafeed configuration"""
        return self.configuration

    async def search_symbols(
        self,
        user_input: str,
        exchange: str = "",
        symbol_type: str = "",
        max_results: int = 50,
    ) -> List[SearchSymbolResultItem]:
        """Search symbols based on user input and filters.

        Delegates to datafeed provider and applies business logic filters.

        Args:
            user_input: Search pattern (symbol, description, ticker)
            exchange: Optional exchange filter (applied after provider search)
            symbol_type: Optional symbol type filter (applied after provider search)
            max_results: Maximum results to return (applied after filtering)

        Returns:
            List of matching symbols with business filters applied
        """
        # Delegate to provider for raw search results
        provider_results = await self.datafeed_provider.search_symbols(
            pattern=user_input if user_input.strip() else "*",
            timeout=10.0,
        )

        # Apply business logic filters on provider results
        filtered_results = provider_results

        # Filter by exchange (case-insensitive)
        if exchange:
            filtered_results = [
                result
                for result in filtered_results
                if result.exchange.lower() == exchange.lower()
            ]

        # Filter by symbol type (case-insensitive)
        if symbol_type:
            filtered_results = [
                result
                for result in filtered_results
                if result.type.lower() == symbol_type.lower()
            ]

        # Limit results
        return filtered_results[:max_results]

    async def resolve_symbol(self, symbol_name: str) -> Optional[SymbolInfo]:
        """Resolve symbol information via datafeed provider."""
        parsed_symbol, exchange = self._parse_ticker(symbol_name)
        try:
            return await self.datafeed_provider.get_symbol_info(
                symbol=parsed_symbol,
                exchange=exchange,
                timeout=5.0,
            )
        except Exception as e:
            logger.warning(f"Failed to resolve symbol '{symbol_name}': {e}")
            return None

    async def get_bars(
        self,
        symbol: str,
        resolution: str,
        from_time: int,
        to_time: int,
        count_back: Optional[int] = None,
    ) -> List[Bar]:
        """Get historical bars for a symbol.

        Delegates to datafeed provider with proper parameter conversion.

        Args:
            symbol: Symbol ticker (format: "SYMBOL" or "SYMBOL:EXCHANGE")
            resolution: TradingView resolution string ("1", "5", "1D", etc.)
            from_time: Start time (Unix milliseconds)
            to_time: End time (Unix milliseconds)
            count_back: Optional limit on number of bars to return

        Returns:
            List of bars in ascending time order
        """
        # Parse ticker to extract symbol and exchange
        parsed_symbol, exchange = self._parse_ticker(symbol)

        # Convert resolution to TimeFrame enum
        try:
            timeframe = self._convert_resolution_to_timeframe(resolution)
        except ValueError as e:
            logger.warning(f"Unsupported resolution '{resolution}': {e}")
            return []

        # Convert timestamps from milliseconds to datetime
        start_time = datetime.fromtimestamp(from_time / 1000)
        end_time = datetime.fromtimestamp(to_time / 1000)

        # Delegate to provider
        try:
            bars = await self.datafeed_provider.get_historical_bars(
                symbol=parsed_symbol,
                start_time=start_time,
                end_time=end_time,
                resolution=timeframe,
                exchange=exchange,
                timeout=30.0,
            )

            # Apply count_back filter if specified
            if count_back and count_back > 0:
                bars = bars[-count_back:]

            return bars

        except Exception as e:
            logger.error(f"Failed to get bars for {symbol}: {e}")
            return []

    async def get_quotes(self, symbols: List[str]) -> List[QuoteData]:
        """Get quotes for multiple symbols"""

        parsed_symbols = [self._parse_ticker(s)[0] for s in symbols]

        try:
            # Delegate to provider for real quote snapshots
            return await self.datafeed_provider.get_quotes_snapshot(
                symbols=parsed_symbols,
                timeout=12.0,
            )
        except Exception as e:
            logger.error(f"Failed to get quotes for {symbols}: {e}")
            # Return error responses for all symbols
            return [
                QuoteData(s="error", n=symbol, v={"error": str(e)})
                for symbol in symbols
            ]
