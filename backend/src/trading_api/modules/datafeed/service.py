"""
Datafeed service for handling market data operations
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, List, Optional
from zoneinfo import ZoneInfo

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
from trading_api.models.exceptions import ServiceException
from trading_api.models.market import Resolution
from trading_api.providers.capabilities.datafeed import DatafeedCapability
from trading_api.shared.ws.ws_router import WsRouteService

logger = logging.getLogger(__name__)

us_eastern = ZoneInfo("US/Eastern")


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
        providers: list | None = None,
    ):
        """Initialize the datafeed service

        Args:
            module_dir: Path to the module directory
            providers: Provider instances for capabilities (unused, for interface compatibility)
        """
        super().__init__(module_dir, providers=providers)
        self.configuration = DatafeedConfiguration()
        # Track provider subscription IDs for each topic (for cleanup)
        self._topic_to_subscription_id: dict[str, str | list[str]] = {}

    def get_configuration(self) -> DatafeedConfiguration:
        """Get datafeed configuration.

        Returns:
            DatafeedConfiguration with supported resolutions, exchanges, etc.
        """
        return self.configuration

    def create_topic(
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

        if topic in self._topic_to_subscription_id:
            raise ServiceException(
                code="SERVICE_DATAFEED_TOPIC_EXISTS",
                message=f"Topic already exists in DatafeedService: {topic}",
                module="datafeed",
            )

        # Parse topic format: "topic_type:{json_params}"
        if ":" not in topic:
            raise ServiceException(
                code="SERVICE_DATAFEED_INVALID_TOPIC_FORMAT",
                message=f"Invalid topic format: {topic}",
                module="datafeed",
            )

        topic_type, params_json = topic.split(":", 1)

        # TODO: need to validate create_topic params/types against provider capabilities at runtime

        if topic_type == "bars":
            # Parse the JSON params part / Validate model
            params_dict = json.loads(params_json)
            subscription_request = BarsSubscriptionRequest.model_validate(params_dict)

            logger.info(f"creating new topic : {topic}")

            subscription_id = self.datafeed_provider.subscribe_realtime_bars(
                ticker=subscription_request.symbol,
                resolution=subscription_request.resolution,
                callback=topic_update,
            )

            # Track subscription ID for cleanup
            self._topic_to_subscription_id[topic] = subscription_id
        elif topic_type == "quotes":
            # Parse the JSON params part / Validate model
            params_dict = json.loads(params_json)
            quote_subscription_request = QuoteDataSubscriptionRequest.model_validate(
                params_dict
            )

            # Combine all symbols (both slow and fast)
            all_symbols = list(
                set(
                    quote_subscription_request.symbols
                    + quote_subscription_request.fast_symbols
                )
            )

            if not all_symbols:
                raise ServiceException(
                    code="SERVICE_DATAFEED_NO_SYMBOLS",
                    message="No symbols provided for quote subscription",
                    module="datafeed",
                )

            logger.info(f"creating new topic : {topic}")

            # Subscribe to market data for all symbols via provider (returns list of subscription IDs)
            subscription_ids = self.datafeed_provider.subscribe_market_data(
                tickers=all_symbols, callback=topic_update
            )

            # Track subscription IDs for cleanup (list for quotes, int for bars)
            self._topic_to_subscription_id[topic] = subscription_ids
        else:
            raise ServiceException(
                code="SERVICE_DATAFEED_UNKNOWN_TOPIC_TYPE",
                message=f"Unknown topic type: {topic_type}",
                module="datafeed",
            )

    def remove_topic(self, topic: str) -> None:
        """Remove topic and cleanup subscriptions.

        Handles both legacy asyncio tasks and provider subscriptions.
        """
        logger.info(f"removing topic: {topic}")

        # Unsubscribe from provider if subscription exists
        subscription_id = self._topic_to_subscription_id.pop(topic, None)
        if subscription_id is not None:
            # Determine topic type from topic string
            if ":" in topic:
                topic_type = topic.split(":", 1)[0]

                if topic_type == "bars":
                    # Single subscription ID for bars (always int)
                    assert isinstance(
                        subscription_id, str
                    ), "Expected str subscription ID for bars"
                    logger.info(
                        f"Unsubscribing from bars: subscription ID {subscription_id}"
                    )
                    self.datafeed_provider.unsubscribe_realtime_bars(subscription_id)
                elif topic_type == "quotes":
                    # Multiple subscription IDs for quotes (one per symbol)
                    assert isinstance(
                        subscription_id, list
                    ), "Expected list[str] subscription ID for quotes"
                    logger.info(
                        f"Unsubscribing from quotes: subscription IDs {subscription_id}"
                    )
                    self.datafeed_provider.unsubscribe_market_data(subscription_id)
        else:
            logger.error(f"No subscription_id found for topic: {topic}")

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

    async def resolve_ticker(self, ticker: str) -> Optional[SymbolInfo]:
        """Resolve symbol information via datafeed provider."""
        return await self.datafeed_provider.get_symbol_info(
            ticker=ticker,
            timeout=5.0,
        )

    async def get_bars(
        self,
        ticker: str,
        resolution: Resolution,
        from_time: int,
        to_time: int,
        count_back: Optional[int] = None,
    ) -> List[Bar]:
        """Get historical bars for a symbol.

        Delegates to datafeed provider with proper parameter conversion.

        Args:
            ticker: Symbol ticker (format: "SYMBOL" or "SYMBOL:EXCHANGE")
            resolution: Resolution enum (type-safe TradingView resolution)
            from_time: Start time (Unix milliseconds)
            to_time: End time (Unix milliseconds)
            count_back: Optional limit on number of bars to return

        Returns:
            List of bars in ascending time order
        """
        # Convert timestamps from milliseconds to datetime
        start_time = datetime.fromtimestamp(from_time / 1000)
        end_time = datetime.fromtimestamp(to_time / 1000)

        bars = await self.datafeed_provider.get_historical_bars(
            ticker=ticker,
            start_time=start_time,
            end_time=end_time,
            resolution=resolution,
            timeout=30.0,
        )

        # Apply count_back filter if specified
        if count_back and count_back > 0:
            bars = bars[-count_back:]

        return bars

    async def get_quotes(self, tickers: List[str]) -> List[QuoteData]:
        """Get quotes for multiple symbols"""

        # try:
        # Delegate to provider for real quote snapshots
        return await self.datafeed_provider.get_quotes_snapshot(
            tickers=tickers,
            timeout=4.0,
        )
        # except ProviderException as e:
        #     logger.exception(e)
        #     # Return error responses for all symbols
        #     return [
        #         QuoteData(s="error", n=symbol, v={"error": f"{e!r}"})
        #         for symbol in tickers
        #     ]
