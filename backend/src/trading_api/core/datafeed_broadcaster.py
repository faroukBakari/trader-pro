"""
Background task that broadcasts mocked bar data to subscribed WebSocket clients.

This service runs within the main FastAPI application and periodically
generates mocked bar data, broadcasting it to clients subscribed to specific topics.
"""

import asyncio
import logging
from typing import List

from trading_api.core.datafeed_service import DatafeedService
from trading_api.plugins.fastws_adapter import FastWSAdapter
from trading_api.ws.datafeed import (
    BarsSubscriptionRequest,
    QuoteDataSubscriptionRequest,
    bars_topic_builder,
    quotes_topic_builder,
)

logger = logging.getLogger(__name__)


class DataFeedBroadcaster:
    """
    Background task that periodically broadcasts mocked bar data.

    Generates realistic bar variations using DatafeedService.mock_last_bar()
    and broadcasts them to subscribed WebSocket clients via FastWSAdapter.
    """

    def __init__(
        self,
        ws_app: FastWSAdapter,
        datafeed_service: DatafeedService,
        interval: float = 2.0,
        symbols: List[str] | None = None,
        resolutions: List[str] | None = None,
        symbols_for_quotes: List[str] | None = None,
    ) -> None:
        """
        Initialize the bar broadcaster.

        Args:
            ws_app: FastWSAdapter instance for publishing updates
            datafeed_service: DatafeedService instance for generating bar data
            interval: Broadcast interval in seconds (default: 2.0)
            symbols: List of symbols to broadcast bars for (default: ["AAPL", "GOOGL", "MSFT"])
            resolutions: List of resolutions to broadcast (default: ["1D"])
            symbols_for_quotes: List of symbols to broadcast quotes for (default: same as symbols)
        """
        self.ws_app = ws_app
        self.datafeed_service = datafeed_service
        self.interval = interval
        self.symbols = symbols or ["AAPL", "GOOGL", "MSFT"]
        self.resolutions = resolutions or ["1D"]
        self.symbols_for_quotes = (
            symbols_for_quotes if symbols_for_quotes is not None else self.symbols
        )

        self._task: asyncio.Task[None] | None = None
        self._running = False

        # Bar metrics
        self._broadcasts_sent = 0
        self._broadcasts_skipped = 0
        self._errors = 0

        # Quote metrics
        self._quote_broadcasts_sent = 0
        self._quote_broadcasts_skipped = 0
        self._quote_errors = 0

    @property
    def is_running(self) -> bool:
        """Check if broadcaster is currently running."""
        return self._running

    @property
    def metrics(self) -> dict:
        """Get broadcaster metrics."""
        return {
            "is_running": self._running,
            "interval": self.interval,
            "symbols": self.symbols,
            "resolutions": self.resolutions,
            "symbols_for_quotes": self.symbols_for_quotes,
            "broadcasts_sent": self._broadcasts_sent,
            "broadcasts_skipped": self._broadcasts_skipped,
            "errors": self._errors,
            "quote_broadcasts_sent": self._quote_broadcasts_sent,
            "quote_broadcasts_skipped": self._quote_broadcasts_skipped,
            "quote_errors": self._quote_errors,
        }

    def start(self) -> None:
        """Start the broadcaster background task."""
        if self._running:
            logger.warning("Broadcaster already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._broadcast_loop())
        logger.info(
            f"Bar broadcaster started: symbols={self.symbols}, "
            f"resolutions={self.resolutions}, interval={self.interval}s"
        )

    def stop(self) -> None:
        """Stop the broadcaster background task."""
        if not self._running:
            logger.warning("Broadcaster not running")
            return

        self._running = False
        if self._task:
            self._task.cancel()

        logger.info(
            f"Bar broadcaster stopped: sent={self._broadcasts_sent}, "
            f"skipped={self._broadcasts_skipped}, errors={self._errors}"
        )

    def _has_subscribers(self, topic: str) -> bool:
        """
        Check if topic has any active subscribers.

        Args:
            topic: Topic identifier (e.g., "bars:AAPL:1")

        Returns:
            True if at least one client is subscribed to the topic
        """
        for client in self.ws_app.connections.values():
            if topic in client.topics:
                return True
        return False

    async def _broadcast_loop(self) -> None:
        """
        Main broadcasting loop.

        Continuously generates and broadcasts bar and quote data at the configured interval.
        Only broadcasts to topics with active subscribers to minimize overhead.
        """
        try:
            while self._running:
                try:
                    await self._broadcast_bars()
                    await self._broadcast_quotes()
                    await asyncio.sleep(self.interval)

                except asyncio.CancelledError:
                    # Graceful shutdown
                    logger.debug("Broadcast loop cancelled")
                    break

                except Exception as e:
                    self._errors += 1
                    logger.error(f"Error in broadcast loop: {e}", exc_info=True)
                    # Continue running despite errors
                    await asyncio.sleep(self.interval)

        finally:
            logger.debug("Broadcast loop terminated")

    async def _broadcast_bars(self) -> None:
        """
        Generate and broadcast bars for all configured symbols and resolutions.

        Only broadcasts if there are active subscribers for the topic.
        """
        for symbol in self.symbols:
            # Generate mocked bar data
            mocked_bar = self.datafeed_service.mock_last_bar(symbol)

            if not mocked_bar:
                logger.warning(f"Failed to generate bar for {symbol}")
                continue

            for resolution in self.resolutions:
                # Build topic identifier
                topic = bars_topic_builder(
                    BarsSubscriptionRequest(symbol=symbol, resolution=resolution)
                )

                # Only broadcast if someone is listening
                if not self._has_subscribers(topic):
                    self._broadcasts_skipped += 1
                    logger.debug(f"No subscribers for {topic}, skipping")
                    continue

                try:
                    # Broadcast to all subscribed clients
                    await self.ws_app.publish(
                        topic=topic,
                        data=mocked_bar,
                        message_type="bars.update",
                    )

                    self._broadcasts_sent += 1
                    logger.debug(f"Broadcasted bar to {topic}")

                except Exception as e:
                    self._errors += 1
                    logger.error(f"Failed to broadcast to {topic}: {e}", exc_info=True)

    async def _broadcast_quotes(self) -> None:
        """
        Generate and broadcast quotes for all configured symbols.

        Only broadcasts if there are active subscribers for the topic.
        """
        if not self.symbols_for_quotes:
            return

        # Generate quote data for all symbols at once
        quote_data_list = self.datafeed_service.get_quotes(self.symbols_for_quotes)

        if not quote_data_list:
            logger.warning("Failed to generate quotes")
            return

        # Broadcast each quote to its subscribers
        for quote_data in quote_data_list:
            # Skip error responses
            if quote_data.s != "ok":
                logger.warning(f"Error in quote data for {quote_data.n}")
                continue

            # Build topic identifier for this symbol
            topic = quotes_topic_builder(
                QuoteDataSubscriptionRequest(
                    symbols=[quote_data.n],
                    fast_symbols=[],
                )
            )

            # Only broadcast if someone is listening
            if not self._has_subscribers(topic):
                self._quote_broadcasts_skipped += 1
                logger.debug(f"No subscribers for {topic}, skipping")
                continue

            try:
                # Broadcast to all subscribed clients
                await self.ws_app.publish(
                    topic=topic,
                    data=quote_data,
                    message_type="quotes.update",
                )

                self._quote_broadcasts_sent += 1
                logger.debug(f"Broadcasted quote to {topic}")

            except Exception as e:
                self._quote_errors += 1
                logger.error(
                    f"Failed to broadcast quote to {topic}: {e}", exc_info=True
                )
