"""
Datafeed service for handling market data operations
"""

import asyncio
import json
import logging
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, List, Optional

from trading_api.models import (
    Bar,
    BarsSubscriptionRequest,
    DatafeedConfiguration,
    QuoteData,
    QuoteDataSubscriptionRequest,
    QuoteValues,
    SearchSymbolResultItem,
    SymbolInfo,
)
from trading_api.models.common import CapabilitySpec
from trading_api.models.market import TimeFrame
from trading_api.providers.capabilities.datafeed import DatafeedCapability
from trading_api.shared.ws.ws_route_interface import WsRouteService

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
        self._load_symbols()
        self._generate_sample_bars()

        # temporarly broadcast mocked data / should be replaced with real datafeed logic
        self._topic_generators: dict[str, asyncio.Task] = {}
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

    # temporarly broadcast mocked data / should be replaced with real datafeed logic
    def _subscribe_to_realtime_bars(
        self, symbol: str, exchange: str, topic_update: Callable[[Bar], None]
    ) -> int:
        """Subscribe to real-time bars via provider.

        Args:
            symbol: Symbol name (e.g., 'AAPL')
            exchange: Exchange name (e.g., 'NASDAQ', 'SMART')
            topic_update: Callback for bar updates

        Returns:
            Subscription ID for cleanup
        """
        logger.info(f"Subscribing to real-time bars for {symbol}:{exchange}")

        # Subscribe via provider - callback will be invoked in TWS reader thread
        subscription_id = self.datafeed_provider.subscribe_realtime_bars(
            symbol=symbol,
            callback=topic_update,  # Pass callback directly
            exchange=exchange,
            resolution=TimeFrame.SEC_5,  # TWS only supports 5-second bars
        )

        logger.info(f"Subscribed to bars for {symbol} with ID {subscription_id}")
        return subscription_id

    def _subscribe_to_market_data(
        self, symbols: list[str], topic_update: Callable[[QuoteData], None]
    ) -> list[int]:
        """Subscribe to real-time market data (quotes) for multiple symbols via provider.

        Args:
            symbols: List of symbol names (e.g., ['AAPL', 'GOOGL'])
            topic_update: Callback for quote updates

        Returns:
            List of subscription IDs (one per symbol) for cleanup
        """
        logger.info(f"Subscribing to market data for {len(symbols)} symbols: {symbols}")

        subscription_ids: list[int] = []

        for symbol in symbols:
            # Parse ticker to get symbol and exchange
            parsed_symbol, exchange = self._parse_ticker(symbol)

            # Subscribe via provider - callback will be invoked in TWS reader thread
            subscription_id = self.datafeed_provider.subscribe_market_data(
                symbol=parsed_symbol,
                callback=topic_update,  # Pass callback directly
                exchange=exchange,
            )

            subscription_ids.append(subscription_id)
            logger.info(
                f"Subscribed to quotes for {parsed_symbol} with ID {subscription_id}"
            )

        return subscription_ids

    async def create_topic(self, topic: str, topic_update: Callable) -> None:
        """Parse topic and create appropriate subscription task.

        Topic formats:
            - bars:{"resolution":"1D","symbol":"AAPL"}
            - quotes:{"symbols":["AAPL","GOOGL"],"fast_symbols":["MSFT"]}

        Raises:
            ValueError: If topic format is invalid or unknown topic type
            json.JSONDecodeError: If JSON params cannot be parsed
        """

        if topic not in self._topic_generators:
            logger.info(f"New topic in DatafeedService : {topic}")
            # Parse topic format: "topic_type:{json_params}"
            if ":" not in topic:
                raise ValueError(f"Invalid topic format: {topic}")

            topic_type, params_json = topic.split(":", 1)

            if topic_type == "bars":
                # Parse the JSON params part / Validate model
                params_dict = json.loads(params_json)
                subscription_request = BarsSubscriptionRequest.model_validate(
                    params_dict
                )

                # Parse ticker to get symbol and exchange
                symbol, exchange = self._parse_ticker(subscription_request.symbol)

                # Subscribe to real-time bars via provider (sync method, returns subscription ID)
                subscription_id = self._subscribe_to_realtime_bars(
                    symbol=symbol, exchange=exchange, topic_update=topic_update
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
                subscription_ids = self._subscribe_to_market_data(
                    symbols=all_symbols, topic_update=topic_update
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

        # Cancel legacy asyncio task if exists
        task = self._topic_generators.get(topic)
        if task:
            task.cancel()
            self._topic_generators.pop(topic, None)

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
                        for sub_id in subscription_id:
                            self.datafeed_provider.unsubscribe_market_data(sub_id)
                    else:
                        logger.info(
                            f"Unsubscribing from quotes: subscription ID {subscription_id}"
                        )
                        self.datafeed_provider.unsubscribe_market_data(subscription_id)

            self._topic_to_subscription_id.pop(topic, None)

    def _load_symbols(self) -> None:
        """Load symbols from JSON file or use default symbols"""
        if self.symbols_file_path and Path(self.symbols_file_path).exists():
            try:
                with open(self.symbols_file_path, "r") as f:
                    symbols_data = json.load(f)
                self._symbols = [
                    SymbolInfo.model_validate(symbol) for symbol in symbols_data
                ]
            except Exception as e:
                print(
                    f"Warning: Unable to load symbols from {self.symbols_file_path}: {e}"
                )
                self._load_default_symbols()
        else:
            self._load_default_symbols()

    def _load_default_symbols(self) -> None:
        """Load default symbols if file is not available"""
        default_symbols = [
            {
                "name": "AAPL",
                "description": "Apple Inc.",
                "type": "stock",
                "session": "0930-1600",
                "timezone": "America/New_York",
                "ticker": "AAPL",
                "exchange": "NASDAQ",
                "listed_exchange": "NASDAQ",
                "format": "price",
                "pricescale": 100,
                "minmov": 1,
                "has_intraday": True,
                "has_daily": True,
                "supported_resolutions": ["1D"],
                "volume_precision": 0,
                "data_status": "streaming",
            },
            {
                "name": "GOOGL",
                "description": "Alphabet Inc. Class A",
                "type": "stock",
                "session": "0930-1600",
                "timezone": "America/New_York",
                "ticker": "GOOGL",
                "exchange": "NASDAQ",
                "listed_exchange": "NASDAQ",
                "format": "price",
                "pricescale": 100,
                "minmov": 1,
                "has_intraday": True,
                "has_daily": True,
                "supported_resolutions": ["1D"],
                "volume_precision": 0,
                "data_status": "streaming",
            },
            {
                "name": "MSFT",
                "description": "Microsoft Corporation",
                "type": "stock",
                "session": "0930-1600",
                "timezone": "America/New_York",
                "ticker": "MSFT",
                "exchange": "NASDAQ",
                "listed_exchange": "NASDAQ",
                "format": "price",
                "pricescale": 100,
                "minmov": 1,
                "has_intraday": True,
                "has_daily": True,
                "supported_resolutions": ["1D"],
                "volume_precision": 0,
                "data_status": "streaming",
            },
        ]
        self._symbols = [
            SymbolInfo.model_validate(symbol) for symbol in default_symbols
        ]

    def _generate_sample_bars(self) -> None:
        """Generate 400 bars for the last 400 days until today"""
        bars: List[Bar] = []
        today = datetime.now()
        current_price = 100.0  # Starting price

        # Generate bars for the last 400 days
        for i in range(400, -1, -1):
            date = today - timedelta(days=i)
            date = date.replace(hour=0, minute=0, second=0, microsecond=0)
            timestamp = int(date.timestamp() * 1000)  # Convert to milliseconds

            # Use date as seed for deterministic random generation
            seed = int(date.timestamp())

            def seeded_random(offset: int) -> float:
                x = math.sin(seed + offset) * 10000
                return x - math.floor(x)

            # Generate realistic OHLC data
            volatility = 2.0
            open_price = current_price
            change = (seeded_random(1) - 0.5) * volatility
            close_price = open_price + change
            high_price = max(open_price, close_price) + seeded_random(2) * volatility
            low_price = min(open_price, close_price) - seeded_random(3) * volatility
            volume = int(seeded_random(4) * 1000000) + 500000

            bar = Bar(
                time=timestamp,
                open=round(open_price, 2),
                high=round(high_price, 2),
                low=round(low_price, 2),
                close=round(close_price, 2),
                volume=volume,
            )

            bars.append(bar)

            # Update price for next bar (trend simulation)
            current_price = close_price + (seeded_random(5) - 0.48) * 0.5

        self._sample_bars = bars

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
            timeout=5.0,
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

    def resolve_symbol(self, symbol_name: str) -> Optional[SymbolInfo]:
        """Resolve symbol information by name or ticker"""
        for symbol in self._symbols:
            if (
                symbol.name == symbol_name
                or symbol.ticker == symbol_name
                or symbol.name.lower() == symbol_name.lower()
                or (symbol.ticker and symbol.ticker.lower() == symbol_name.lower())
            ):
                return symbol
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

    def get_quotes(self, symbols: List[str]) -> List[QuoteData]:
        """Get quotes for multiple symbols"""
        quote_data: List[QuoteData] = []

        for symbol in symbols:
            # Check if symbol exists
            symbol_info = self.resolve_symbol(symbol)
            if not symbol_info:
                quote_data.append(
                    QuoteData(s="error", n=symbol, v={"error": "Symbol not found"})
                )
                continue

            # Get the last bar for quote generation
            if not self._sample_bars:
                quote_data.append(
                    QuoteData(s="error", n=symbol, v={"error": "No data available"})
                )
                continue

            last_bar = self._sample_bars[-1]

            # Generate realistic quote values based on the last bar
            base_price = max(last_bar.close, 0.01)  # Ensure positive price
            spread = max(base_price * 0.001, 0.01)  # 0.1% spread, minimum 0.01

            # Generate some variation for real-time feel
            import random

            variation = (
                (random.random() - 0.5) * base_price * 0.005
            )  # 0.5% max variation
            current_price = max(base_price + variation, 0.01)  # Ensure positive

            bid = max(current_price - spread / 2, 0.01)  # Ensure positive bid
            ask = max(current_price + spread / 2, bid + 0.01)  # Ensure ask > bid

            change = current_price - last_bar.open
            change_percent = (change / last_bar.open) * 100 if last_bar.open > 0 else 0

            quote_values = QuoteValues(
                lp=round(current_price, 2),
                ask=round(ask, 2),
                bid=round(bid, 2),
                spread=round(ask - bid, 2),
                open_price=round(max(last_bar.open, 0.01), 2),
                high_price=round(max(last_bar.high, current_price, 0.01), 2),
                low_price=round(max(min(last_bar.low, current_price), 0.01), 2),
                prev_close_price=round(max(last_bar.close * 0.995, 0.01), 2),
                volume=max(last_bar.volume or 0, 0),
                ch=round(change, 2),
                chp=round(change_percent, 2),
                short_name=symbol,
                exchange="DEMO",
                description=f"Demo quotes for {symbol}",
                original_name=symbol,
            )

            quote_data.append(QuoteData(s="ok", n=symbol, v=quote_values))

        return quote_data

    def mock_last_bar(self, symbol: str) -> Optional[Bar]:
        """Create a mock bar by modifying the last bar to simulate real-time updates"""
        if not self._sample_bars:
            return None

        # Check if symbol exists
        symbol_info = self.resolve_symbol(symbol)
        if not symbol_info:
            return None

        last_bar = self._sample_bars[-1]

        # Create a variation within the high-low range
        range_size = last_bar.high - last_bar.low
        import random

        random_factor = random.random()  # 0 to 1
        new_close = last_bar.low + range_size * random_factor

        # Ensure the new close doesn't exceed the original high/low bounds
        adjusted_close = max(last_bar.low, min(last_bar.high, new_close))

        # Update high/low if the new close exceeds them
        new_high = max(last_bar.high, adjusted_close)
        new_low = min(last_bar.low, adjusted_close)

        return Bar(
            time=last_bar.time,  # Same time to update existing bar
            open=last_bar.open,  # Keep original open
            high=round(new_high, 2),
            low=round(new_low, 2),
            close=round(adjusted_close, 2),
            volume=(last_bar.volume or 0)
            + int(random.random() * 10000),  # Add some volume
        )

    def __del__(self) -> None:
        """Cleanup generator tasks on instance deletion"""
        for task in self._topic_generators.values():
            if not task.done():
                task.cancel()
                logger.info(f"Cancelled broadcasting task: {task.get_name()}")
