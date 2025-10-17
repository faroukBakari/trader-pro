"""
Tests for BarBroadcaster background service.
"""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from trading_api.core.datafeed_broadcaster import DataFeedBroadcaster
from trading_api.core.datafeed_service import DatafeedService
from trading_api.models import Bar, QuoteData, QuoteValues
from trading_api.plugins.fastws_adapter import FastWSAdapter
from trading_api.ws.router_interface import buildTopicParams


def build_topic(symbol: str, resolution: str) -> str:
    """Helper to build topic string matching backend format."""
    params = {"resolution": resolution, "symbol": symbol}
    return f"bars:{buildTopicParams(params)}"


def build_quote_topic(symbols: list[str]) -> str:
    """Helper to build quote topic string matching backend format."""
    params = {"fast_symbols": [], "symbols": symbols}
    return f"quotes:{buildTopicParams(params)}"


@pytest.fixture
def mock_ws_app() -> Any:
    """Create a mock FastWSAdapter."""
    ws_app = Mock(spec=FastWSAdapter)
    ws_app.connections = {}
    ws_app.publish = AsyncMock()
    return ws_app


@pytest.fixture
def mock_datafeed_service() -> Any:
    """Create a mock DatafeedService."""
    service = Mock(spec=DatafeedService)
    # Mock bar with realistic data
    mock_bar = Bar(
        time=1697097600000,
        open=150.0,
        high=151.0,
        low=149.5,
        close=150.5,
        volume=1000000,
    )
    service.mock_last_bar = Mock(return_value=mock_bar)

    # Mock quote data with realistic values
    mock_quote = QuoteData(
        s="ok",
        n="AAPL",
        v=QuoteValues(
            lp=150.5,
            ask=150.6,
            bid=150.4,
            spread=0.2,
            open_price=150.0,
            high_price=151.0,
            low_price=149.5,
            prev_close_price=149.0,
            volume=1000000,
            ch=0.5,
            chp=0.33,
            short_name="AAPL",
            exchange="DEMO",
            description="Demo quotes for AAPL",
            original_name="AAPL",
        ),
    )
    service.get_quotes = Mock(return_value=[mock_quote])
    return service


@pytest.fixture
def broadcaster(
    mock_ws_app: Any,
    mock_datafeed_service: Any,
) -> DataFeedBroadcaster:
    """Create a BarBroadcaster instance."""
    return DataFeedBroadcaster(
        ws_app=mock_ws_app,
        datafeed_service=mock_datafeed_service,
        interval=0.1,  # Fast interval for testing
        symbols=["AAPL"],
        resolutions=["1"],
    )


class TestBarBroadcasterInitialization:
    """Test broadcaster initialization and configuration."""

    def test_initialization_with_defaults(
        self,
        mock_ws_app: Any,
        mock_datafeed_service: Any,
    ) -> None:
        """Test broadcaster initializes with default values."""
        broadcaster = DataFeedBroadcaster(
            ws_app=mock_ws_app,
            datafeed_service=mock_datafeed_service,
        )

        assert broadcaster.ws_app == mock_ws_app
        assert broadcaster.datafeed_service == mock_datafeed_service
        assert broadcaster.interval == 2.0
        assert broadcaster.symbols == ["AAPL", "GOOGL", "MSFT"]
        assert broadcaster.resolutions == ["1D"]
        assert not broadcaster.is_running

    def test_initialization_with_custom_values(
        self,
        mock_ws_app: Any,
        mock_datafeed_service: Any,
    ) -> None:
        """Test broadcaster initializes with custom values."""
        broadcaster = DataFeedBroadcaster(
            ws_app=mock_ws_app,
            datafeed_service=mock_datafeed_service,
            interval=5.0,
            symbols=["BTC", "ETH"],
            resolutions=["1", "5", "D"],
        )

        assert broadcaster.interval == 5.0
        assert broadcaster.symbols == ["BTC", "ETH"]
        assert broadcaster.resolutions == ["1", "5", "D"]

    def test_initial_metrics(self, broadcaster: DataFeedBroadcaster) -> None:
        """Test initial metrics are zero."""
        metrics = broadcaster.metrics

        assert metrics["is_running"] is False
        assert metrics["broadcasts_sent"] == 0
        assert metrics["broadcasts_skipped"] == 0
        assert metrics["errors"] == 0
        assert metrics["interval"] == 0.1
        assert metrics["symbols"] == ["AAPL"]
        assert metrics["resolutions"] == ["1"]


class TestBarBroadcasterLifecycle:
    """Test broadcaster start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_broadcaster(self, broadcaster: DataFeedBroadcaster) -> None:
        """Test starting the broadcaster creates a task."""
        broadcaster.start()

        assert broadcaster.is_running
        assert broadcaster._task is not None
        assert isinstance(broadcaster._task, asyncio.Task)

        # Cleanup
        broadcaster.stop()

    @pytest.mark.asyncio
    async def test_start_already_running(
        self, broadcaster: DataFeedBroadcaster
    ) -> None:
        """Test starting an already running broadcaster does nothing."""
        broadcaster.start()
        task1 = broadcaster._task

        broadcaster.start()  # Try to start again
        task2 = broadcaster._task

        assert task1 == task2  # Same task
        assert broadcaster.is_running

        # Cleanup
        broadcaster.stop()

    @pytest.mark.asyncio
    async def test_stop_broadcaster(self, broadcaster: DataFeedBroadcaster) -> None:
        """Test stopping the broadcaster cancels the task."""
        broadcaster.start()
        assert broadcaster.is_running

        broadcaster.stop()

        # Wait a moment for task cancellation to complete
        await asyncio.sleep(0.05)

        assert not broadcaster.is_running
        assert broadcaster._task is not None  # type: ignore[unreachable]
        assert broadcaster._task.cancelled() or broadcaster._task.done()

    def test_stop_not_running(self, broadcaster: DataFeedBroadcaster) -> None:
        """Test stopping a non-running broadcaster does nothing."""
        assert not broadcaster.is_running

        broadcaster.stop()  # Should not raise

        assert not broadcaster.is_running


class TestBarBroadcasterSubscriberCheck:
    """Test subscriber checking logic."""

    def test_has_subscribers_with_active_client(
        self, broadcaster: DataFeedBroadcaster
    ) -> None:
        """Test has_subscribers returns True when client is subscribed."""
        # Create mock client with topic
        mock_client = Mock()
        mock_client.topics = {"bars:1:AAPL"}

        broadcaster.ws_app.connections = {"client1": mock_client}

        assert broadcaster._has_subscribers("bars:1:AAPL") is True

    def test_has_subscribers_without_active_client(
        self, broadcaster: DataFeedBroadcaster
    ) -> None:
        """Test has_subscribers returns False when no client is subscribed."""
        broadcaster.ws_app.connections = {}

        assert broadcaster._has_subscribers("bars:1:AAPL") is False

    def test_has_subscribers_with_different_topic(
        self, broadcaster: DataFeedBroadcaster
    ) -> None:
        """Test has_subscribers returns False for different topic."""
        # Create mock client subscribed to different topic
        mock_client = Mock()
        mock_client.topics = {"bars:1:GOOGL"}

        broadcaster.ws_app.connections = {"client1": mock_client}

        assert broadcaster._has_subscribers("bars:1:AAPL") is False

    def test_has_subscribers_with_multiple_clients(
        self, broadcaster: DataFeedBroadcaster
    ) -> None:
        """Test has_subscribers with multiple clients."""
        # Client 1: subscribed to AAPL
        client1 = Mock()
        client1.topics = {"bars:1:AAPL"}

        # Client 2: subscribed to GOOGL
        client2 = Mock()
        client2.topics = {"bars:1:GOOGL"}

        broadcaster.ws_app.connections = {"client1": client1, "client2": client2}

        assert broadcaster._has_subscribers("bars:1:AAPL") is True
        assert broadcaster._has_subscribers("bars:1:GOOGL") is True
        assert broadcaster._has_subscribers("bars:1:MSFT") is False


class TestBarBroadcasterBroadcasting:
    """Test bar broadcasting functionality."""

    @pytest.mark.asyncio
    async def test_broadcast_with_subscriber(
        self, broadcaster: DataFeedBroadcaster
    ) -> None:
        """Test broadcasting sends data when subscribers exist."""
        # Setup subscriber
        mock_client = Mock()
        mock_client.topics = {build_topic("AAPL", "1")}
        broadcaster.ws_app.connections = {"client1": mock_client}

        # Broadcast
        await broadcaster._broadcast_bars()

        # Verify publish was called
        assert broadcaster.ws_app.publish.called  # type: ignore[attr-defined]
        assert broadcaster.ws_app.publish.call_count == 1  # type: ignore[attr-defined]

        # Verify call arguments
        call_args = broadcaster.ws_app.publish.call_args  # type: ignore[attr-defined]
        assert call_args.kwargs["topic"] == build_topic("AAPL", "1")
        assert call_args.kwargs["message_type"] == "bars.update"
        assert isinstance(call_args.kwargs["data"], Bar)

        # Verify metrics
        assert broadcaster._broadcasts_sent == 1
        assert broadcaster._broadcasts_skipped == 0

    @pytest.mark.asyncio
    async def test_broadcast_without_subscriber(
        self, broadcaster: DataFeedBroadcaster
    ) -> None:
        """Test broadcasting skips when no subscribers exist."""
        # No subscribers
        broadcaster.ws_app.connections = {}

        # Broadcast
        await broadcaster._broadcast_bars()

        # Verify publish was NOT called
        assert not broadcaster.ws_app.publish.called  # type: ignore[attr-defined]

        # Verify metrics
        assert broadcaster._broadcasts_sent == 0
        assert broadcaster._broadcasts_skipped == 1

    @pytest.mark.asyncio
    async def test_broadcast_multiple_symbols(
        self,
        mock_ws_app: Any,
        mock_datafeed_service: Any,
    ) -> None:
        """Test broadcasting for multiple symbols."""
        broadcaster = DataFeedBroadcaster(
            ws_app=mock_ws_app,
            datafeed_service=mock_datafeed_service,
            symbols=["AAPL", "GOOGL"],
            resolutions=["1"],
        )

        # Subscribe to both symbols
        client = Mock()
        client.topics = {build_topic("AAPL", "1"), build_topic("GOOGL", "1")}
        broadcaster.ws_app.connections = {"client1": client}

        # Broadcast
        await broadcaster._broadcast_bars()

        # Should publish twice (once per symbol)
        assert broadcaster.ws_app.publish.call_count == 2  # type: ignore[attr-defined]
        assert broadcaster._broadcasts_sent == 2

    @pytest.mark.asyncio
    async def test_broadcast_multiple_resolutions(
        self,
        mock_ws_app: Any,
        mock_datafeed_service: Any,
    ) -> None:
        """Test broadcasting for multiple resolutions."""
        broadcaster = DataFeedBroadcaster(
            ws_app=mock_ws_app,
            datafeed_service=mock_datafeed_service,
            symbols=["AAPL"],
            resolutions=["1", "5", "D"],
        )

        # Subscribe to all resolutions
        client = Mock()
        client.topics = {
            build_topic("AAPL", "1"),
            build_topic("AAPL", "5"),
            build_topic("AAPL", "D"),
        }
        broadcaster.ws_app.connections = {"client1": client}

        # Broadcast
        await broadcaster._broadcast_bars()

        # Should publish three times (once per resolution)
        assert broadcaster.ws_app.publish.call_count == 3  # type: ignore[attr-defined]
        assert broadcaster._broadcasts_sent == 3

    @pytest.mark.asyncio
    async def test_broadcast_handles_datafeed_error(
        self, broadcaster: DataFeedBroadcaster
    ) -> None:
        """Test broadcasting handles datafeed service errors."""
        # Mock datafeed to return None (error case)
        # noqa: E501
        broadcaster.datafeed_service.mock_last_bar.return_value = None  # type: ignore[attr-defined]

        # Setup subscriber
        client = Mock()
        client.topics = {build_topic("AAPL", "1")}
        broadcaster.ws_app.connections = {"client1": client}

        # Broadcast
        await broadcaster._broadcast_bars()

        # Should not publish
        assert not broadcaster.ws_app.publish.called  # type: ignore[attr-defined]
        assert broadcaster._broadcasts_sent == 0

    @pytest.mark.asyncio
    async def test_broadcast_handles_publish_error(
        self, broadcaster: DataFeedBroadcaster
    ) -> None:
        """Test broadcasting handles publish errors gracefully."""
        # Make publish raise an error
        broadcaster.ws_app.publish.side_effect = Exception("Publish failed")  # type: ignore[attr-defined]

        # Setup subscriber
        client = Mock()
        client.topics = {build_topic("AAPL", "1")}
        broadcaster.ws_app.connections = {"client1": client}

        # Broadcast (should not raise)
        await broadcaster._broadcast_bars()

        # Verify error was tracked
        assert broadcaster._errors == 1
        assert broadcaster._broadcasts_sent == 0


class TestBarBroadcasterLoop:
    """Test the main broadcast loop."""

    @pytest.mark.asyncio
    async def test_broadcast_loop_runs_periodically(
        self, broadcaster: DataFeedBroadcaster
    ) -> None:
        """Test broadcast loop runs at configured interval."""
        # Setup subscriber
        client = Mock()
        client.topics = {build_topic("AAPL", "1")}
        broadcaster.ws_app.connections = {"client1": client}

        # Start broadcaster
        broadcaster.start()

        # Wait for a few broadcasts
        await asyncio.sleep(0.35)  # Should get ~3 broadcasts at 0.1s interval

        # Stop broadcaster
        broadcaster.stop()

        # Verify multiple broadcasts occurred
        assert broadcaster._broadcasts_sent >= 2
        assert broadcaster.ws_app.publish.call_count >= 2  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_broadcast_loop_continues_after_error(
        self, broadcaster: DataFeedBroadcaster
    ) -> None:
        """Test broadcast loop continues running after errors."""
        # Setup subscriber
        client = Mock()
        client.topics = {build_topic("AAPL", "1")}
        broadcaster.ws_app.connections = {"client1": client}

        # Make first call fail, then succeed
        broadcaster.ws_app.publish.side_effect = [  # type: ignore[attr-defined]
            Exception("Error 1"),
            None,  # Success
            None,  # Success
        ]

        # Start broadcaster
        broadcaster.start()

        # Wait for broadcasts
        await asyncio.sleep(0.35)

        # Stop broadcaster
        broadcaster.stop()

        # Verify it continued after error
        assert broadcaster._errors >= 1
        assert broadcaster._broadcasts_sent >= 1

    @pytest.mark.asyncio
    async def test_broadcast_loop_stops_gracefully(
        self, broadcaster: DataFeedBroadcaster
    ) -> None:
        """Test broadcast loop stops gracefully when cancelled."""
        broadcaster.start()
        assert broadcaster.is_running

        # Give it time to start
        await asyncio.sleep(0.05)

        # Stop broadcaster
        broadcaster.stop()

        # Wait for task to finish
        await asyncio.sleep(0.1)

        assert not broadcaster.is_running
        assert broadcaster._task is not None  # type: ignore[unreachable]
        assert broadcaster._task.cancelled() or broadcaster._task.done()


class TestBarBroadcasterMetrics:
    """Test broadcaster metrics tracking."""

    @pytest.mark.asyncio
    async def test_metrics_track_broadcasts(
        self, broadcaster: DataFeedBroadcaster
    ) -> None:
        """Test metrics accurately track broadcasts."""
        # Setup subscriber
        client = Mock()
        client.topics = {build_topic("AAPL", "1")}
        broadcaster.ws_app.connections = {"client1": client}

        # Do multiple broadcasts
        await broadcaster._broadcast_bars()
        await broadcaster._broadcast_bars()
        await broadcaster._broadcast_bars()

        metrics = broadcaster.metrics

        assert metrics["broadcasts_sent"] == 3
        assert metrics["broadcasts_skipped"] == 0
        assert metrics["errors"] == 0

    @pytest.mark.asyncio
    async def test_metrics_track_skipped(
        self, broadcaster: DataFeedBroadcaster
    ) -> None:
        """Test metrics track skipped broadcasts."""
        # No subscribers
        broadcaster.ws_app.connections = {}

        # Do multiple broadcasts
        await broadcaster._broadcast_bars()
        await broadcaster._broadcast_bars()

        metrics = broadcaster.metrics

        assert metrics["broadcasts_sent"] == 0
        assert metrics["broadcasts_skipped"] == 2
        assert metrics["errors"] == 0

    @pytest.mark.asyncio
    async def test_metrics_track_errors(self, broadcaster: DataFeedBroadcaster) -> None:
        """Test metrics track errors."""
        # Setup subscriber
        client = Mock()
        client.topics = {build_topic("AAPL", "1")}
        broadcaster.ws_app.connections = {"client1": client}

        # Make publish fail
        broadcaster.ws_app.publish.side_effect = Exception("Error")  # type: ignore[attr-defined]

        # Do broadcast
        await broadcaster._broadcast_bars()

        metrics = broadcaster.metrics

        assert metrics["broadcasts_sent"] == 0
        assert metrics["errors"] == 1


class TestQuoteBroadcasting:
    """Test quote broadcasting functionality."""

    @pytest.mark.asyncio
    async def test_broadcast_quotes_with_subscriber(
        self, broadcaster: DataFeedBroadcaster
    ) -> None:
        """Test broadcasting quotes sends data when subscribers exist."""
        # Setup subscriber
        mock_client = Mock()
        mock_client.topics = {build_quote_topic(["AAPL"])}
        broadcaster.ws_app.connections = {"client1": mock_client}

        # Broadcast
        await broadcaster._broadcast_quotes()

        # Verify publish was called
        assert broadcaster.ws_app.publish.called  # type: ignore[attr-defined]
        assert broadcaster.ws_app.publish.call_count == 1  # type: ignore[attr-defined]

        # Verify call arguments
        call_args = broadcaster.ws_app.publish.call_args  # type: ignore[attr-defined]
        assert call_args.kwargs["topic"] == build_quote_topic(["AAPL"])
        assert call_args.kwargs["message_type"] == "quotes.update"
        assert isinstance(call_args.kwargs["data"], QuoteData)

        # Verify metrics
        assert broadcaster._quote_broadcasts_sent == 1
        assert broadcaster._quote_broadcasts_skipped == 0

    @pytest.mark.asyncio
    async def test_broadcast_quotes_without_subscriber(
        self, broadcaster: DataFeedBroadcaster
    ) -> None:
        """Test broadcasting quotes skips when no subscribers exist."""
        # No subscribers
        broadcaster.ws_app.connections = {}

        # Broadcast
        await broadcaster._broadcast_quotes()

        # Verify publish was NOT called
        assert not broadcaster.ws_app.publish.called  # type: ignore[attr-defined]

        # Verify metrics
        assert broadcaster._quote_broadcasts_sent == 0
        assert broadcaster._quote_broadcasts_skipped == 1

    @pytest.mark.asyncio
    async def test_broadcast_quotes_multiple_symbols(
        self,
        mock_ws_app: Any,
        mock_datafeed_service: Any,
    ) -> None:
        """Test broadcasting quotes for multiple symbols."""
        # Mock multiple quotes
        mock_datafeed_service.get_quotes.return_value = [  # type: ignore[attr-defined]
            QuoteData(
                s="ok",
                n="AAPL",
                v=QuoteValues(
                    lp=150.5,
                    ask=150.6,
                    bid=150.4,
                    spread=0.2,
                    open_price=150.0,
                    high_price=151.0,
                    low_price=149.5,
                    prev_close_price=149.0,
                    volume=1000000,
                    ch=0.5,
                    chp=0.33,
                    short_name="AAPL",
                    exchange="DEMO",
                    description="Demo quotes for AAPL",
                    original_name="AAPL",
                ),
            ),
            QuoteData(
                s="ok",
                n="GOOGL",
                v=QuoteValues(
                    lp=120.0,
                    ask=120.1,
                    bid=119.9,
                    spread=0.2,
                    open_price=119.5,
                    high_price=120.5,
                    low_price=119.0,
                    prev_close_price=118.5,
                    volume=800000,
                    ch=0.5,
                    chp=0.42,
                    short_name="GOOGL",
                    exchange="DEMO",
                    description="Demo quotes for GOOGL",
                    original_name="GOOGL",
                ),
            ),
        ]

        broadcaster = DataFeedBroadcaster(
            ws_app=mock_ws_app,
            datafeed_service=mock_datafeed_service,
            symbols_for_quotes=["AAPL", "GOOGL"],
        )

        # Subscribe to both symbols
        client = Mock()
        client.topics = {build_quote_topic(["AAPL"]), build_quote_topic(["GOOGL"])}
        broadcaster.ws_app.connections = {"client1": client}

        # Broadcast
        await broadcaster._broadcast_quotes()

        # Should publish twice (once per symbol)
        assert broadcaster.ws_app.publish.call_count == 2  # type: ignore[attr-defined]
        assert broadcaster._quote_broadcasts_sent == 2

    @pytest.mark.asyncio
    async def test_broadcast_quotes_handles_get_quotes_error(
        self, broadcaster: DataFeedBroadcaster
    ) -> None:
        """Test broadcasting handles get_quotes service errors."""
        # Mock datafeed to return empty list
        broadcaster.datafeed_service.get_quotes.return_value = []  # type: ignore[attr-defined]

        # Setup subscriber
        client = Mock()
        client.topics = {build_quote_topic(["AAPL"])}
        broadcaster.ws_app.connections = {"client1": client}

        # Broadcast
        await broadcaster._broadcast_quotes()

        # Should not publish
        assert not broadcaster.ws_app.publish.called  # type: ignore[attr-defined]
        assert broadcaster._quote_broadcasts_sent == 0

    @pytest.mark.asyncio
    async def test_broadcast_quotes_handles_error_status(
        self, broadcaster: DataFeedBroadcaster
    ) -> None:
        """Test broadcasting skips quotes with error status."""
        # Mock datafeed to return error
        broadcaster.datafeed_service.get_quotes.return_value = [  # type: ignore[attr-defined]
            QuoteData(s="error", n="AAPL", v={"error": "Symbol not found"})
        ]

        # Setup subscriber
        client = Mock()
        client.topics = {build_quote_topic(["AAPL"])}
        broadcaster.ws_app.connections = {"client1": client}

        # Broadcast
        await broadcaster._broadcast_quotes()

        # Should not publish
        assert not broadcaster.ws_app.publish.called  # type: ignore[attr-defined]
        assert broadcaster._quote_broadcasts_sent == 0

    @pytest.mark.asyncio
    async def test_broadcast_quotes_handles_publish_error(
        self, broadcaster: DataFeedBroadcaster
    ) -> None:
        """Test broadcasting handles publish errors gracefully."""
        # Make publish raise an error
        broadcaster.ws_app.publish.side_effect = Exception("Publish failed")  # type: ignore[attr-defined]

        # Setup subscriber
        client = Mock()
        client.topics = {build_quote_topic(["AAPL"])}
        broadcaster.ws_app.connections = {"client1": client}

        # Broadcast (should not raise)
        await broadcaster._broadcast_quotes()

        # Verify error was tracked
        assert broadcaster._quote_errors == 1
        assert broadcaster._quote_broadcasts_sent == 0

    @pytest.mark.asyncio
    async def test_broadcast_quotes_with_no_symbols_configured(
        self,
        mock_ws_app: Any,
        mock_datafeed_service: Any,
    ) -> None:
        """Test broadcasting quotes with empty symbols list does nothing."""
        broadcaster = DataFeedBroadcaster(
            ws_app=mock_ws_app,
            datafeed_service=mock_datafeed_service,
            symbols_for_quotes=[],
        )

        # Verify symbols_for_quotes is actually empty
        assert broadcaster.symbols_for_quotes == []

        # Reset mock call counts after initialization
        mock_datafeed_service.get_quotes.reset_mock()  # type: ignore[attr-defined]
        mock_ws_app.publish.reset_mock()  # type: ignore[attr-defined]

        # Broadcast
        await broadcaster._broadcast_quotes()

        # Should not call get_quotes or publish
        assert not mock_datafeed_service.get_quotes.called  # type: ignore[attr-defined]
        assert not broadcaster.ws_app.publish.called  # type: ignore[attr-defined]


class TestBroadcasterWithBothBarsAndQuotes:
    """Test broadcaster with both bar and quote broadcasting."""

    @pytest.mark.asyncio
    async def test_broadcast_loop_runs_both_bars_and_quotes(
        self,
        mock_ws_app: Any,
        mock_datafeed_service: Any,
    ) -> None:
        """Test broadcast loop runs both bar and quote broadcasts."""
        broadcaster = DataFeedBroadcaster(
            ws_app=mock_ws_app,
            datafeed_service=mock_datafeed_service,
            interval=0.1,
            symbols=["AAPL"],
            resolutions=["1"],
            symbols_for_quotes=["AAPL"],
        )

        # Setup subscribers for both bars and quotes
        client = Mock()
        client.topics = {build_topic("AAPL", "1"), build_quote_topic(["AAPL"])}
        broadcaster.ws_app.connections = {"client1": client}

        # Start broadcaster
        broadcaster.start()

        # Wait for a few broadcasts
        await asyncio.sleep(0.35)

        # Stop broadcaster
        broadcaster.stop()

        # Verify both types of broadcasts occurred
        assert broadcaster._broadcasts_sent >= 2
        assert broadcaster._quote_broadcasts_sent >= 2

        # Verify publish was called for both types
        call_count = broadcaster.ws_app.publish.call_count  # type: ignore[attr-defined]
        assert call_count >= 4  # At least 2 bar + 2 quote broadcasts

    @pytest.mark.asyncio
    async def test_metrics_include_both_bar_and_quote_data(
        self,
        mock_ws_app: Any,
        mock_datafeed_service: Any,
    ) -> None:
        """Test metrics include both bar and quote statistics."""
        broadcaster = DataFeedBroadcaster(
            ws_app=mock_ws_app,
            datafeed_service=mock_datafeed_service,
            symbols=["AAPL"],
            symbols_for_quotes=["AAPL", "GOOGL"],
        )

        metrics = broadcaster.metrics

        assert "broadcasts_sent" in metrics
        assert "broadcasts_skipped" in metrics
        assert "errors" in metrics
        assert "quote_broadcasts_sent" in metrics
        assert "quote_broadcasts_skipped" in metrics
        assert "quote_errors" in metrics
        assert metrics["symbols_for_quotes"] == ["AAPL", "GOOGL"]

    def test_initialization_with_different_symbols_for_quotes(
        self,
        mock_ws_app: Any,
        mock_datafeed_service: Any,
    ) -> None:
        """Test broadcaster can have different symbols for bars vs quotes."""
        broadcaster = DataFeedBroadcaster(
            ws_app=mock_ws_app,
            datafeed_service=mock_datafeed_service,
            symbols=["AAPL", "GOOGL"],
            symbols_for_quotes=["MSFT", "TSLA", "NVDA"],
        )

        assert broadcaster.symbols == ["AAPL", "GOOGL"]
        assert broadcaster.symbols_for_quotes == ["MSFT", "TSLA", "NVDA"]

    def test_initialization_symbols_for_quotes_defaults_to_symbols(
        self,
        mock_ws_app: Any,
        mock_datafeed_service: Any,
    ) -> None:
        """Test symbols_for_quotes defaults to symbols if not specified."""
        broadcaster = DataFeedBroadcaster(
            ws_app=mock_ws_app,
            datafeed_service=mock_datafeed_service,
            symbols=["AAPL", "GOOGL"],
        )

        assert broadcaster.symbols_for_quotes == ["AAPL", "GOOGL"]
