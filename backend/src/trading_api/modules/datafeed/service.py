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
from trading_api.shared.ws.ws_route_interface import WsRouteService

logger = logging.getLogger(__name__)


class DatafeedService(WsRouteService):
    """Service for handling datafeed operations"""

    def __init__(self, symbols_file_path: Optional[str] = None):
        """Initialize the datafeed service

        Args:
            symbols_file_path: Path to symbols JSON file. If None, uses
                default embedded symbols.
        """
        self.configuration = DatafeedConfiguration()
        self.symbols_file_path = symbols_file_path
        self._symbols: List[SymbolInfo] = []
        self._sample_bars: List[Bar] = []
        self._load_symbols()
        self._generate_sample_bars()

        # temporarly broadcast mocked data / should be replaced with real datafeed logic
        self._topic_generators: dict[str, asyncio.Task] = {}

    # temporarly broadcast mocked data / should be replaced with real datafeed logic
    async def _bar_generator(
        self, symbol: str, topic_update: Callable[[Bar], None]
    ) -> None:
        """Start broadcasting real-time bar updates to all subscribed topics"""
        logger.info(f"Starting service _bar_generator loop for symbol: {symbol}")

        while True:
            updated_bar = self.mock_last_bar(symbol)
            if updated_bar:
                topic_update(updated_bar)
            await asyncio.sleep(0.2)

    # temporarly broadcast mocked data / should be replaced with real datafeed logic
    async def _quote_generator(
        self, symbols: List[str], topic_update: Callable[[QuoteData], None]
    ) -> None:
        """Start broadcasting real-time quote updates for subscribed symbols"""
        logger.info(f"Starting service _quote_generator loop for symbols: {symbols}")

        while True:
            quotes = self.get_quotes(symbols)
            for quote in quotes:
                topic_update(quote)
            await asyncio.sleep(0.2)

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

                # Create task with parsed symbol
                self._topic_generators[topic] = asyncio.create_task(
                    self._bar_generator(subscription_request.symbol, topic_update)
                )
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

                # Create task with all symbols
                self._topic_generators[topic] = asyncio.create_task(
                    self._quote_generator(all_symbols, topic_update)
                )
            else:
                raise ValueError(f"Unknown topic type: {topic_type}")

    def remove_topic(self, topic: str) -> None:
        logger.info(f"Deleting topic queue for: {topic}")
        task = self._topic_generators.get(topic)
        if task:
            task.cancel()
        self._topic_generators.pop(topic, None)

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
                print(f"Error loading symbols from {self.symbols_file_path}: {e}")
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

    def search_symbols(
        self,
        user_input: str,
        exchange: str = "",
        symbol_type: str = "",
        max_results: int = 50,
    ) -> List[SearchSymbolResultItem]:
        """Search symbols based on user input and filters"""
        filtered_symbols = self._symbols

        # Filter by user input (search in name, description, or ticker)
        if user_input and user_input.strip():
            search_term = user_input.lower().strip()
            filtered_symbols = [
                symbol
                for symbol in filtered_symbols
                if (
                    search_term in symbol.name.lower()
                    or search_term in symbol.description.lower()
                    or (symbol.ticker and search_term in symbol.ticker.lower())
                )
            ]

        # Filter by exchange
        if exchange:
            filtered_symbols = [
                symbol
                for symbol in filtered_symbols
                if symbol.exchange.lower() == exchange.lower()
            ]

        # Filter by symbol type
        if symbol_type:
            filtered_symbols = [
                symbol
                for symbol in filtered_symbols
                if symbol.type.lower() == symbol_type.lower()
            ]

        # Limit results
        limited_symbols = filtered_symbols[:max_results]

        # Convert to search result items
        results = [
            SearchSymbolResultItem(
                symbol=symbol.name,
                description=symbol.description,
                exchange=symbol.exchange,
                ticker=symbol.ticker,
                type=symbol.type,
            )
            for symbol in limited_symbols
        ]

        return results

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

    def get_bars(
        self,
        symbol: str,
        resolution: str,
        from_time: int,
        to_time: int,
        count_back: Optional[int] = None,
    ) -> List[Bar]:
        """Get historical bars for a symbol"""
        # Only support 1D resolution for now
        if resolution != "1D":
            return []

        # Check if symbol exists
        symbol_info = self.resolve_symbol(symbol)
        if not symbol_info:
            return []

        # Filter bars within the requested time range
        filtered_bars = [
            bar for bar in self._sample_bars if from_time <= bar.time <= to_time
        ]

        # Sort bars by time
        filtered_bars.sort(key=lambda x: x.time)

        return filtered_bars[count_back * -1 :] if count_back else filtered_bars

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
            try:
                task.cancel()
                logger.info(f"Cancelled generator task: {task.get_name()}")
            except Exception as e:
                logger.error(f"Error cancelling generator task: {e}")
