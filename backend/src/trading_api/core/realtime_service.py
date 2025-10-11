"""
Real-time data feed service for WebSocket broadcasting
"""

import asyncio
import logging
import random
from datetime import datetime
from typing import Dict, List, Optional

from ..core.websocket_manager import connection_manager
from ..models import (
    CandlestickUpdate,
    MarketDataTick,
    OrderBookUpdate,
    TradingNotification,
)

logger = logging.getLogger(__name__)


class RealTimeDataService:
    """Service for generating and broadcasting real-time market data"""

    def __init__(self) -> None:
        self.symbols = ["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN", "NVDA", "META"]
        self.base_prices = {symbol: random.uniform(100, 500) for symbol in self.symbols}
        self.is_running = False
        self.tasks: List[asyncio.Task] = []

    async def start(self) -> None:
        """Start all real-time data feeds"""
        if self.is_running:
            return

        self.is_running = True
        logger.info("Starting real-time data feeds...")

        # Start different data feed tasks
        self.tasks = [
            asyncio.create_task(self._market_data_feed()),
            asyncio.create_task(self._orderbook_feed()),
            asyncio.create_task(self._chart_data_feed()),
            asyncio.create_task(self._notification_feed()),
        ]

        logger.info(f"Started {len(self.tasks)} real-time data feed tasks")

    async def stop(self) -> None:
        """Stop all real-time data feeds"""
        if not self.is_running:
            return

        self.is_running = False
        logger.info("Stopping real-time data feeds...")

        # Cancel all tasks
        for task in self.tasks:
            task.cancel()

        # Wait for tasks to complete
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()

        logger.info("All real-time data feeds stopped")

    async def _market_data_feed(self) -> None:
        """Generate real-time market price updates"""
        while self.is_running:
            try:
                for symbol in self.symbols:
                    # Simulate price movement
                    base_price = self.base_prices[symbol]
                    change_percent = random.uniform(-0.05, 0.05)  # -5% to +5%
                    new_price = base_price * (1 + change_percent)

                    # Update base price slowly
                    self.base_prices[symbol] = (base_price * 0.99) + (new_price * 0.01)

                    # Calculate other values
                    volume = random.randint(1000, 10000)
                    bid = new_price * random.uniform(0.995, 0.999)
                    ask = new_price * random.uniform(1.001, 1.005)
                    change = new_price - base_price
                    change_percent_value = (change / base_price) * 100

                    # Create market data tick
                    tick = MarketDataTick(
                        timestamp=datetime.now(),
                        channel="market_data",
                        request_id=None,
                        symbol=symbol,
                        price=round(new_price, 2),
                        volume=volume,
                        bid=round(bid, 2),
                        ask=round(ask, 2),
                        change=round(change, 2),
                        change_percent=round(change_percent_value, 2),
                    )

                    # Broadcast to market_data channel subscribers
                    await connection_manager.broadcast_to_channel(
                        "market_data", tick, symbol=symbol
                    )

                # Wait before next update
                await asyncio.sleep(random.uniform(0.5, 2.0))

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in data generation: {e}")
                break

    async def _orderbook_feed(self) -> None:
        """Generate real-time order book updates"""
        sequence = 0

        while self.is_running:
            try:
                for symbol in self.symbols:
                    base_price = self.base_prices[symbol]

                    # Generate bid orders (price descending)
                    bids = []
                    for i in range(5):
                        price = base_price * (1 - (i + 1) * 0.001)
                        quantity = random.uniform(10, 1000)
                        bids.append([round(price, 2), round(quantity, 2)])

                    # Generate ask orders (price ascending)
                    asks = []
                    for i in range(5):
                        price = base_price * (1 + (i + 1) * 0.001)
                        quantity = random.uniform(10, 1000)
                        asks.append([round(price, 2), round(quantity, 2)])

                    sequence += 1

                    # Create order book update
                    orderbook = OrderBookUpdate(
                        timestamp=datetime.now(),
                        channel="orderbook",
                        request_id=None,
                        symbol=symbol,
                        bids=bids,
                        asks=asks,
                        sequence=sequence,
                    )

                    # Broadcast to orderbook channel subscribers
                    await connection_manager.broadcast_to_channel(
                        "orderbook", orderbook, symbol=symbol
                    )

                # Wait before next update
                await asyncio.sleep(random.uniform(2.0, 5.0))

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in orderbook feed: {e}")
                await asyncio.sleep(1)

    async def _chart_data_feed(self) -> None:
        """Generate real-time candlestick updates"""
        candle_data = {
            symbol: {
                "open": self.base_prices[symbol],
                "high": self.base_prices[symbol],
                "low": self.base_prices[symbol],
                "close": self.base_prices[symbol],
                "volume": 0,
                "start_time": datetime.now().timestamp() * 1000,
            }
            for symbol in self.symbols
        }

        while self.is_running:
            try:
                current_time = datetime.now().timestamp() * 1000

                for symbol in self.symbols:
                    candle = candle_data[symbol]
                    current_price = self.base_prices[symbol]

                    # Update candle data
                    candle["close"] = current_price
                    candle["high"] = max(candle["high"], current_price)
                    candle["low"] = min(candle["low"], current_price)
                    candle["volume"] += random.randint(100, 1000)

                    # Check if we should start a new candle (every 60 seconds)
                    if current_time - candle["start_time"] > 60000:  # 1 minute
                        # Finalize current candle
                        final_candle = CandlestickUpdate(
                            timestamp=datetime.now(),
                            channel="chart_data",
                            request_id=None,
                            symbol=symbol,
                            resolution="1m",
                            time=int(candle["start_time"]),
                            open=round(candle["open"], 2),
                            high=round(candle["high"], 2),
                            low=round(candle["low"], 2),
                            close=round(candle["close"], 2),
                            volume=int(candle["volume"]),
                            is_final=True,
                        )

                        await connection_manager.broadcast_to_channel(
                            "chart_data", final_candle, symbol=symbol
                        )

                        # Start new candle
                        candle_data[symbol] = {
                            "open": current_price,
                            "high": current_price,
                            "low": current_price,
                            "close": current_price,
                            "volume": 0,
                            "start_time": current_time,
                        }
                    else:
                        # Send updating candle
                        updating_candle = CandlestickUpdate(
                            timestamp=datetime.now(),
                            channel="chart_data",
                            request_id=None,
                            symbol=symbol,
                            resolution="1m",
                            time=int(candle["start_time"]),
                            open=round(candle["open"], 2),
                            high=round(candle["high"], 2),
                            low=round(candle["low"], 2),
                            close=round(candle["close"], 2),
                            volume=int(candle["volume"]),
                            is_final=False,
                        )

                        await connection_manager.broadcast_to_channel(
                            "chart_data", updating_candle, symbol=symbol
                        )

                # Wait before next update
                await asyncio.sleep(5.0)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in chart data feed: {e}")
                await asyncio.sleep(1)

    async def _notification_feed(self) -> None:
        """Generate occasional trading notifications"""
        from typing import Literal

        notification_types = [
            ("info", "Market Update", "Trading session opened for {symbol}"),
            ("warning", "Price Alert", "{symbol} has moved {change}% in the last hour"),
            (
                "success",
                "Order Filled",
                "Your buy order for {symbol} has been executed",
            ),
            (
                "info",
                "Market News",
                "Earnings report for {symbol} will be released tomorrow",
            ),
        ]

        await asyncio.sleep(random.uniform(30, 60))

        while self.is_running:
            try:
                # Pick random notification
                category_str, title, message_template = random.choice(
                    notification_types
                )
                symbol = random.choice(self.symbols)
                change = round(random.uniform(-10, 10), 1)

                message = message_template.format(symbol=symbol, change=change)

                # Type cast to ensure literal type
                category: Literal[
                    "info", "warning", "error", "success"
                ] = category_str  # type: ignore

                notification = TradingNotification(
                    timestamp=datetime.now(),
                    channel="notifications",
                    request_id=None,
                    category=category,
                    title=title,
                    message=message,
                    data={"symbol": symbol, "change": change},
                )

                # Broadcast to notifications channel (requires auth)
                await connection_manager.broadcast_to_channel(
                    "notifications", notification
                )

                await asyncio.sleep(random.uniform(30, 60))

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in notification feed: {e}")
                await asyncio.sleep(1)

    async def broadcast_custom_message(
        self, channel: str, message_data: Dict, symbol: Optional[str] = None
    ) -> int:
        """Broadcast a custom message to a specific channel"""
        try:
            from ..models import WebSocketMessage

            message = WebSocketMessage(
                type=message_data.get("type", "custom"),
                timestamp=datetime.now(),
                channel=channel,
                request_id=None,
            )

            # Add custom fields
            for key, value in message_data.items():
                if key not in ["type", "timestamp", "channel", "request_id"]:
                    setattr(message, key, value)

            sent_count = await connection_manager.broadcast_to_channel(
                channel, message, symbol=symbol
            )

            logger.info(
                f"Broadcasted custom message to {sent_count} subscribers on {channel}"
            )
            return sent_count

        except Exception as e:
            logger.error(f"Error broadcasting custom message: {e}")
            return 0


# Global instance
realtime_data_service = RealTimeDataService()
