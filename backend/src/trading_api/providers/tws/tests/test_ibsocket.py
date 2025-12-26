"""Tests for IBSocket - TWS callback handler and state management.

Tests cover:
- State machine management (READY→CONNECTING→CONNECTED→RUNNING→CLOSED)
- Future creation and resolution (create_future, _resolve_future)
- Stream management (register/update/unregister_stream, _active_streams tracking)
- Error handling (_handle_request_error: future rejection, stream on_error, cleanup)
- Stream notifications (_notify_stream: snapshot resolution, stream dispatch, cleanup)
- Tick callbacks (tickPrice, tickSize, tickString - field updates + notifications)
- Historical callbacks (historicalData accumulation, historicalDataEnd resolution)

Note: All tests test IBSocket in isolation without real TWS connections.
"""

import asyncio
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from ibapi.common import BarData, TickAttrib

from trading_api.models.exceptions import ProviderException
from trading_api.providers.tws.tws_connection import (
    IBSocket,
    IBSocketState,
    decode_data,
    make_fields,
    to_str,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def ibsocket() -> IBSocket:
    """Create a fresh IBSocket instance for testing."""
    return IBSocket()


@pytest.fixture
def running_ibsocket() -> IBSocket:
    """Create an IBSocket in RUNNING state for callback testing."""
    sock = IBSocket()
    sock._state = IBSocketState.RUNNING
    return sock


# =============================================================================
# TestIBSocketStateManagement
# =============================================================================


class TestIBSocketStateManagement:
    """Test IBSocket state machine: READY→CONNECTING→CONNECTED→RUNNING→CLOSED."""

    def test_initial_state_is_ready(self, ibsocket: IBSocket) -> None:
        """Test IBSocket starts in READY state."""
        assert ibsocket._state == IBSocketState.READY

    def test_running_property_false_when_not_running(self, ibsocket: IBSocket) -> None:
        """Test running property returns False when not in RUNNING state."""
        assert ibsocket.running is False

    def test_running_property_true_when_running(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test running property returns True in RUNNING state."""
        assert running_ibsocket.running is True

    def test_next_req_id_increments(self, ibsocket: IBSocket) -> None:
        """Test next_req_id returns sequential IDs."""
        id1 = ibsocket.next_req_id
        id2 = ibsocket.next_req_id
        id3 = ibsocket.next_req_id

        assert id2 == id1 + 1
        assert id3 == id2 + 1

    def test_disconnect_sets_closed_state(self, ibsocket: IBSocket) -> None:
        """Test disconnect transitions to CLOSED state."""
        ibsocket.disconnect()

        assert ibsocket._state == IBSocketState.CLOSED

    def test_reset_clears_internal_state(self, ibsocket: IBSocket) -> None:
        """Test _reset clears all tracking dictionaries."""
        # Setup some state
        ibsocket._future_hooks[1] = (MagicMock(), MagicMock())
        ibsocket._future_data[1] = [1, 2, 3]
        ibsocket._stream_data[1] = {"test": "data"}
        ibsocket._reader_accounts = ["U123"]
        ibsocket._nxt_order_id = 42
        ibsocket._ready_event.set()

        # Reset
        ibsocket._reset()

        # Verify cleared
        assert len(ibsocket._future_hooks) == 0
        assert len(ibsocket._future_data) == 0
        assert len(ibsocket._stream_data) == 0
        assert len(ibsocket._reader_accounts) == 0
        assert getattr(ibsocket, "_nxt_order_id") is None
        assert not ibsocket._ready_event.is_set()


# =============================================================================
# TestIBSocketFutureManagement
# =============================================================================


class TestIBSocketFutureManagement:
    """Test create_future, _resolve_future, timeout cleanup."""

    @pytest.mark.asyncio
    async def test_create_future_registers_in_hooks(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test create_future registers future in _future_hooks."""
        reqId = 42
        awaitable = running_ibsocket.create_future(reqId, capability="datafeed")

        assert reqId in running_ibsocket._future_hooks
        assert reqId in running_ibsocket._future_data
        assert reqId in running_ibsocket._reqId_to_capability
        assert running_ibsocket._reqId_to_capability[reqId] == "datafeed"

        # Cleanup - resolve and await to avoid warning
        _, future = running_ibsocket._future_hooks[reqId]
        future.set_result([])
        await awaitable

    @pytest.mark.asyncio
    async def test_create_future_initializes_empty_data(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test create_future initializes empty data list."""
        reqId = 42
        awaitable = running_ibsocket.create_future(reqId, capability="shared")

        assert running_ibsocket._future_data[reqId] == []

        # Cleanup - resolve and await to avoid warning
        _, future = running_ibsocket._future_hooks[reqId]
        future.set_result([])
        await awaitable

    @pytest.mark.asyncio
    async def test_resolve_future_sets_result(self, running_ibsocket: IBSocket) -> None:
        """Test _resolve_future sets accumulated data as result."""
        reqId = 42
        awaitable = running_ibsocket.create_future(
            reqId, capability="datafeed", timeout=5
        )

        # Accumulate some data
        running_ibsocket._future_data[reqId].extend(["item1", "item2"])

        # Resolve the future (call_soon_threadsafe is synchronous in tests)
        running_ibsocket._resolve_future(reqId)

        # Allow event loop to process
        await asyncio.sleep(0.01)

        # Future should be resolved
        result = await awaitable
        assert result == ["item1", "item2"]

    @pytest.mark.asyncio
    async def test_resolve_future_cleans_up_hooks(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test _resolve_future removes reqId from tracking dicts."""
        reqId = 42
        awaitable = running_ibsocket.create_future(
            reqId, capability="datafeed", timeout=5
        )

        running_ibsocket._resolve_future(reqId)
        await asyncio.sleep(0.01)

        # Await the coroutine to avoid warning
        await awaitable

        # Cleanup check - hooks and data should be removed
        assert reqId not in running_ibsocket._future_hooks
        assert reqId not in running_ibsocket._future_data
        assert reqId not in running_ibsocket._reqId_to_capability

    @pytest.mark.asyncio
    async def test_create_tick_future_reuses_existing_stream(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test create_tick_future reuses existing stream data if present."""
        reqId = 42
        ticker = "AAPL:NASDAQ:STK-12345"

        # Pre-populate stream with complete data
        running_ibsocket._stream_data[reqId] = {
            "reqId": reqId,
            "ticker_name": ticker,
            "bid": 150.0,
            "ask": 150.5,
            "last": 150.25,
        }

        awaitable = running_ibsocket.create_stream_future(
            reqId, ticker, capability="datafeed", timeout=5
        )

        # Future should be immediately resolved since bid/ask/last are present
        result = await awaitable

        assert result["bid"] == 150.0
        assert result["ask"] == 150.5
        assert result["last"] == 150.25

    @pytest.mark.asyncio
    async def test_create_tick_future_creates_stream_data(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test create_tick_future creates stream_data entry."""
        reqId = 42
        ticker = "AAPL:NASDAQ:STK-12345"

        awaitable = running_ibsocket.create_stream_future(
            reqId, ticker, capability="datafeed", timeout=5
        )

        assert reqId in running_ibsocket._stream_data
        assert running_ibsocket._stream_data[reqId]["ticker_name"] == ticker

        # Cleanup - resolve and await to avoid warning
        _, future = running_ibsocket._snapshot_hooks[reqId]
        future.set_result(running_ibsocket._stream_data[reqId])
        await awaitable


# =============================================================================
# TestIBSocketStreamManagement
# =============================================================================


class TestIBSocketStreamManagement:
    """Test register/update/unregister_stream, _active_streams tracking."""

    @pytest.mark.asyncio
    async def test_register_stream_creates_all_tracking(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test register_stream creates hooks, data, capability, and active_streams."""
        reqId = 42
        ticker = "AAPL:NASDAQ:STK-12345"

        async def callback(data: dict, fields: list) -> None:
            pass

        running_ibsocket.register_stream(reqId, ticker, callback, capability="datafeed")

        assert reqId in running_ibsocket._stream_hooks
        assert reqId in running_ibsocket._stream_data
        assert reqId in running_ibsocket._reqId_to_capability
        assert ticker in running_ibsocket._active_streams
        assert running_ibsocket._active_streams[ticker] == reqId
        assert running_ibsocket._stream_data[reqId]["ticker_name"] == ticker

    @pytest.mark.asyncio
    async def test_register_stream_with_error_callback(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test register_stream stores error callback."""
        reqId = 42
        ticker = "AAPL:NASDAQ:STK-12345"

        async def callback(data: dict, fields: list) -> None:
            pass

        async def on_error(error: ProviderException) -> None:
            pass

        running_ibsocket.register_stream(
            reqId, ticker, callback, capability="datafeed", on_error=on_error
        )

        _, _, stored_on_error = running_ibsocket._stream_hooks[reqId]
        assert stored_on_error is on_error

    @pytest.mark.asyncio
    async def test_update_stream_replaces_callback(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test update_stream replaces the callback."""
        reqId = 42
        ticker = "AAPL:NASDAQ:STK-12345"

        async def original_callback(data: dict, fields: list) -> None:
            pass

        async def new_callback(data: dict, fields: list) -> None:
            pass

        running_ibsocket.register_stream(
            reqId, ticker, original_callback, capability="datafeed"
        )
        running_ibsocket.update_stream(reqId, new_callback)

        _, stored_callback, _ = running_ibsocket._stream_hooks[reqId]
        assert stored_callback is new_callback

    def test_unregister_stream_cleans_up_all_tracking(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test unregister_stream removes all tracking state."""
        reqId = 42
        ticker = "AAPL:NASDAQ:STK-12345"

        async def callback(data: dict, fields: list) -> None:
            pass

        running_ibsocket.register_stream(reqId, ticker, callback, capability="datafeed")

        # Unregister
        running_ibsocket.unregister_stream(reqId)

        assert reqId not in running_ibsocket._stream_hooks
        assert reqId not in running_ibsocket._stream_data
        assert reqId not in running_ibsocket._reqId_to_capability
        assert ticker not in running_ibsocket._active_streams

    def test_stream_req_id_returns_reqid_for_active_stream(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test stream_req_id returns reqId for active stream."""
        reqId = 42
        ticker = "AAPL:NASDAQ:STK-12345"

        async def callback(data: dict, fields: list) -> None:
            pass

        running_ibsocket.register_stream(reqId, ticker, callback, capability="datafeed")

        result = running_ibsocket.stream_req_id(ticker)
        assert result == reqId

    def test_stream_req_id_returns_none_for_unknown(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test stream_req_id returns None for unknown ticker."""
        result = running_ibsocket.stream_req_id("UNKNOWN:TICKER")
        assert result is None


# =============================================================================
# TestIBSocketErrorHandling
# =============================================================================


class TestIBSocketErrorHandling:
    """Test _handle_request_error: future rejection, stream on_error, cleanup."""

    @pytest.mark.asyncio
    async def test_handle_error_rejects_pending_future(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test _handle_request_error rejects pending future with ProviderException."""
        reqId = 42
        awaitable = running_ibsocket.create_future(
            reqId, capability="datafeed", timeout=5
        )

        # Trigger error
        running_ibsocket._handle_request_error(
            category="API",
            detail="VALIDATION_200",
            reqId=reqId,
            message="No security definition found",
        )

        await asyncio.sleep(0.01)

        # Future should be rejected
        with pytest.raises(ProviderException) as exc_info:
            await awaitable

        assert "VALIDATION_200" in exc_info.value.code
        assert "No security definition found" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_handle_error_calls_stream_on_error(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test _handle_request_error calls stream on_error callback."""
        reqId = 42
        ticker = "AAPL:NASDAQ:STK-12345"
        error_received: list[ProviderException] = []

        async def callback(data: dict, fields: list) -> None:
            pass

        async def on_error(error: ProviderException) -> None:
            error_received.append(error)

        running_ibsocket.register_stream(
            reqId, ticker, callback, capability="datafeed", on_error=on_error
        )

        # Trigger error
        running_ibsocket._handle_request_error(
            category="API",
            detail="SUBSCRIPTION_354",
            reqId=reqId,
            message="Not subscribed to market data",
        )

        await asyncio.sleep(0.05)

        # on_error should have been called
        assert len(error_received) == 1
        assert "SUBSCRIPTION_354" in error_received[0].code

    @pytest.mark.asyncio
    async def test_handle_error_non_recoverable_cleans_up_stream(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test _handle_request_error cleans up stream for non-recoverable errors."""
        reqId = 42
        ticker = "AAPL:NASDAQ:STK-12345"

        async def callback(data: dict, fields: list) -> None:
            pass

        async def on_error(error: ProviderException) -> None:
            pass

        running_ibsocket.register_stream(
            reqId, ticker, callback, capability="datafeed", on_error=on_error
        )

        # Trigger NON_RECOVERABLE error
        running_ibsocket._handle_request_error(
            category="API",
            detail="VALIDATION_200_NON_RECOVERABLE",
            reqId=reqId,
            message="Fatal error",
        )

        await asyncio.sleep(0.05)

        # Stream should be cleaned up
        assert reqId not in running_ibsocket._stream_data
        assert reqId not in running_ibsocket._stream_hooks
        assert ticker not in running_ibsocket._active_streams

    @pytest.mark.asyncio
    async def test_handle_error_uses_capability_fallback(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test _handle_request_error uses capability_fallback when reqId not tracked."""
        reqId = 99  # Not tracked

        awaitable = running_ibsocket.create_future(
            reqId, capability="shared", timeout=5
        )

        running_ibsocket._handle_request_error(
            category="API",
            detail="TEST_ERROR",
            reqId=reqId,
            message="Test error",
            capability_fallback="shared",
        )

        await asyncio.sleep(0.01)

        with pytest.raises(ProviderException) as exc_info:
            await awaitable

        assert exc_info.value.capability == "shared"


# =============================================================================
# TestIBSocketNotifyStream
# =============================================================================


class TestIBSocketNotifyStream:
    """Test _notify_stream: snapshot resolution, stream dispatch, cleanup paths."""

    @pytest.mark.asyncio
    async def test_notify_stream_resolves_snapshot_when_complete(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test _notify_stream resolves future when bid/ask/last complete."""
        reqId = 42
        ticker = "AAPL:NASDAQ:STK-12345"

        awaitable = running_ibsocket.create_stream_future(
            reqId, ticker, capability="datafeed", timeout=5
        )

        # Populate stream with complete data
        running_ibsocket._stream_data[reqId]["bid"] = 150.0
        running_ibsocket._stream_data[reqId]["ask"] = 150.5
        running_ibsocket._stream_data[reqId]["last"] = 150.25

        # Trigger notification
        running_ibsocket._notify_stream(reqId, ["last"])

        await asyncio.sleep(0.05)

        result = await awaitable
        assert result["bid"] == 150.0

    @pytest.mark.asyncio
    async def test_notify_stream_dispatches_to_callback(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test _notify_stream calls stream callback with data and fields."""
        reqId = 42
        ticker = "AAPL:NASDAQ:STK-12345"
        received_data: list[tuple[dict, list]] = []

        async def callback(data: dict, fields: list) -> None:
            received_data.append((dict(data), list(fields)))

        running_ibsocket.register_stream(reqId, ticker, callback, capability="datafeed")
        running_ibsocket._stream_data[reqId]["bid"] = 150.0

        # Trigger notification
        running_ibsocket._notify_stream(reqId, ["bid"])

        await asyncio.sleep(0.05)

        assert len(received_data) == 1
        assert received_data[0][0]["bid"] == 150.0
        assert received_data[0][1] == ["bid"]

    @pytest.mark.asyncio
    async def test_notify_stream_cleans_up_snapshot_only_request(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test _notify_stream cleans up when future resolved and no stream hook."""
        reqId = 42
        ticker = "AAPL:NASDAQ:STK-12345"

        awaitable = running_ibsocket.create_stream_future(
            reqId, ticker, capability="datafeed", timeout=5
        )

        # No stream hook - only future
        # Populate with complete data
        running_ibsocket._stream_data[reqId]["bid"] = 150.0
        running_ibsocket._stream_data[reqId]["ask"] = 150.5
        running_ibsocket._stream_data[reqId]["last"] = 150.25

        running_ibsocket._notify_stream(reqId, ["last"])

        await asyncio.sleep(0.05)

        # Await the coroutine to avoid warning
        await awaitable

        # Should be cleaned up (no stream hook to keep alive)
        assert reqId not in running_ibsocket._stream_data
        assert reqId not in running_ibsocket._reqId_to_capability

    def test_notify_stream_ignores_unknown_reqid(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test _notify_stream handles unknown reqId gracefully."""
        # Should not raise
        running_ibsocket._notify_stream(99999, ["bid"])


# =============================================================================
# TestIBSocketTickCallbacks
# =============================================================================


class TestIBSocketTickCallbacks:
    """Test tickPrice, tickSize, tickString - field updates + notifications."""

    def test_tick_price_updates_stream_data(self, running_ibsocket: IBSocket) -> None:
        """Test tickPrice updates stream_data with price."""
        reqId = 42
        running_ibsocket._stream_data[reqId] = {"reqId": reqId, "ticker_name": "TEST"}

        # TickType 1 = BID
        attrib = TickAttrib()
        running_ibsocket.tickPrice(reqId, 1, 150.25, attrib)

        assert running_ibsocket._stream_data[reqId]["bid"] == 150.25

    def test_tick_price_ignores_same_value(self, running_ibsocket: IBSocket) -> None:
        """Test tickPrice doesn't notify if value unchanged."""
        reqId = 42
        running_ibsocket._stream_data[reqId] = {
            "reqId": reqId,
            "ticker_name": "TEST",
            "bid": 150.25,
        }

        # Mock _notify_stream to track calls
        notify_calls: list[int] = []
        original_notify = running_ibsocket._notify_stream

        def mock_notify(rid: int, fields: list) -> None:
            notify_calls.append(rid)
            original_notify(rid, fields)

        running_ibsocket._notify_stream = mock_notify  # type: ignore

        # Same price - should not notify
        attrib = TickAttrib()
        running_ibsocket.tickPrice(reqId, 1, 150.25, attrib)

        assert len(notify_calls) == 0

    def test_tick_price_notifies_on_change(self, running_ibsocket: IBSocket) -> None:
        """Test tickPrice notifies when value changes."""
        reqId = 42
        running_ibsocket._stream_data[reqId] = {
            "reqId": reqId,
            "ticker_name": "TEST",
            "bid": 150.25,
        }

        notify_calls: list[tuple[int, list]] = []
        running_ibsocket._notify_stream

        def mock_notify(rid: int, fields: list) -> None:
            notify_calls.append((rid, fields))

        running_ibsocket._notify_stream = mock_notify  # type: ignore

        # Different price - should notify
        attrib = TickAttrib()
        running_ibsocket.tickPrice(reqId, 1, 150.50, attrib)

        assert len(notify_calls) == 1
        assert notify_calls[0][1] == ["bid"]

    def test_tick_price_updates_bar_close_for_last(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test tickPrice also updates bar_close when last price updates."""
        reqId = 42
        running_ibsocket._stream_data[reqId] = {"reqId": reqId, "ticker_name": "TEST"}

        # TickType 4 = LAST
        attrib = TickAttrib()
        running_ibsocket.tickPrice(reqId, 4, 150.75, attrib)

        assert running_ibsocket._stream_data[reqId]["last"] == 150.75
        assert running_ibsocket._stream_data[reqId]["bar_close"] == 150.75

    def test_tick_size_updates_stream_data(self, running_ibsocket: IBSocket) -> None:
        """Test tickSize updates stream_data with size."""
        reqId = 42
        running_ibsocket._stream_data[reqId] = {"reqId": reqId, "ticker_name": "TEST"}

        # TickType 0 = BID_SIZE
        running_ibsocket.tickSize(reqId, 0, Decimal("100"))

        assert running_ibsocket._stream_data[reqId]["bid_size"] == Decimal("100")

    def test_tick_string_updates_stream_data(self, running_ibsocket: IBSocket) -> None:
        """Test tickString updates stream_data with string value."""
        reqId = 42
        running_ibsocket._stream_data[reqId] = {"reqId": reqId, "ticker_name": "TEST"}

        # TickType 45 = LAST_TIMESTAMP
        running_ibsocket.tickString(reqId, 45, "1702656000")

        assert running_ibsocket._stream_data[reqId]["last_timestamp"] == "1702656000"

    def test_tick_generic_updates_stream_data(self, running_ibsocket: IBSocket) -> None:
        """Test tickGeneric updates stream_data with float value."""
        reqId = 42
        running_ibsocket._stream_data[reqId] = {"reqId": reqId, "ticker_name": "TEST"}

        # TickType 24 = OPTION_IMPLIED_VOL (0-indexed: OPTION_IMPLIED_VOL is at index 24)
        running_ibsocket.tickGeneric(reqId, 24, 0.25)

        assert running_ibsocket._stream_data[reqId]["option_implied_vol"] == 0.25

    def test_tick_ignores_unknown_stream(self, running_ibsocket: IBSocket) -> None:
        """Test tick callbacks handle unknown reqId gracefully."""
        # Should not raise
        attrib = TickAttrib()
        running_ibsocket.tickPrice(99999, 1, 150.0, attrib)
        running_ibsocket.tickSize(99999, 0, Decimal("100"))
        running_ibsocket.tickString(99999, 45, "12345")
        running_ibsocket.tickGeneric(99999, 23, 0.5)


# =============================================================================
# TestIBSocketHistoricalCallbacks
# =============================================================================


class TestIBSocketHistoricalCallbacks:
    """Test historicalData accumulation, historicalDataEnd resolution."""

    @pytest.mark.asyncio
    async def test_historical_data_accumulates_bars(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test historicalData accumulates bars in future_data."""
        reqId = 42
        awaitable = running_ibsocket.create_future(
            reqId, capability="datafeed", timeout=5
        )

        bar1 = BarData()
        bar1.date = "20231215"
        bar1.open = 150.0
        bar1.high = 151.0
        bar1.low = 149.0
        bar1.close = 150.5

        bar2 = BarData()
        bar2.date = "20231216"
        bar2.open = 150.5
        bar2.high = 152.0
        bar2.low = 150.0
        bar2.close = 151.5

        running_ibsocket.historicalData(reqId, bar1)
        running_ibsocket.historicalData(reqId, bar2)

        assert len(running_ibsocket._future_data[reqId]) == 2
        assert running_ibsocket._future_data[reqId][0].open == 150.0

        # Cleanup - resolve and await to avoid warning
        _, future = running_ibsocket._future_hooks[reqId]
        future.set_result([])
        await awaitable

    @pytest.mark.asyncio
    async def test_historical_data_end_resolves_future(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test historicalDataEnd resolves future with accumulated bars."""
        reqId = 42
        awaitable = running_ibsocket.create_future(
            reqId, capability="datafeed", timeout=5
        )

        bar1 = BarData()
        bar1.date = "20231215"
        bar1.open = 150.0

        running_ibsocket.historicalData(reqId, bar1)
        running_ibsocket.historicalDataEnd(reqId, "20231215", "20231216")

        await asyncio.sleep(0.01)

        result = await awaitable
        assert len(result) == 1
        assert result[0].open == 150.0

    @pytest.mark.asyncio
    async def test_historical_data_update_notifies_stream(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test historicalDataUpdate updates stream and notifies."""
        reqId = 42
        ticker = "AAPL:NASDAQ:STK-12345@5 mins"
        received: list[tuple[dict, list]] = []

        async def callback(data: dict, fields: list) -> None:
            received.append((dict(data), list(fields)))

        running_ibsocket.register_stream(reqId, ticker, callback, capability="datafeed")

        bar = BarData()
        bar.date = "20231215 16:00:00"
        bar.open = 150.0
        bar.high = 151.0
        bar.low = 149.5
        bar.close = 150.5
        bar.volume = Decimal("1000")
        bar.wap = Decimal("150.25")
        bar.barCount = 100

        running_ibsocket.historicalDataUpdate(reqId, bar)

        await asyncio.sleep(0.05)

        assert len(received) == 1
        assert received[0][0]["bar_open"] == 150.0
        assert received[0][0]["bar_close"] == 150.5
        assert "bar_open" in received[0][1]


# =============================================================================
# TestIBSocketSnapshotEnd
# =============================================================================


class TestIBSocketSnapshotEnd:
    """Test tickSnapshotEnd callback behavior."""

    @pytest.mark.asyncio
    async def test_tick_snapshot_end_resolves_future(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test tickSnapshotEnd resolves pending future."""
        reqId = 42
        ticker = "AAPL:NASDAQ:STK-12345"

        awaitable = running_ibsocket.create_stream_future(
            reqId, ticker, capability="datafeed", timeout=5
        )
        running_ibsocket._stream_data[reqId]["bid"] = 150.0
        running_ibsocket._stream_data[reqId]["ask"] = 150.5

        running_ibsocket.tickSnapshotEnd(reqId)

        await asyncio.sleep(0.05)

        result = await awaitable
        assert result["bid"] == 150.0

    @pytest.mark.asyncio
    async def test_tick_snapshot_end_cleans_up_snapshot_only(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test tickSnapshotEnd cleans up only when no stream hook exists."""
        reqId = 42
        ticker = "AAPL:NASDAQ:STK-12345"

        # Create pending snapshot (snapshot-only scenario, no stream hook)
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        running_ibsocket._snapshot_hooks[reqId] = (loop, future)
        running_ibsocket._stream_data[reqId] = {"reqId": reqId, "ticker_name": ticker}

        running_ibsocket.tickSnapshotEnd(reqId)

        await asyncio.sleep(0.05)

        # Snapshot-only path cleans up (no stream hook)
        assert reqId not in running_ibsocket._stream_data

    @pytest.mark.asyncio
    async def test_tick_snapshot_end_preserves_active_stream(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test tickSnapshotEnd does NOT clean up when stream hook exists."""
        reqId = 42
        ticker = "AAPL:NASDAQ:STK-12345"

        async def callback(data: dict, fields: list) -> None:
            pass

        # Register stream hook (active subscription scenario)
        running_ibsocket.register_stream(reqId, ticker, callback, capability="datafeed")

        # Also add a pending snapshot
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        running_ibsocket._snapshot_hooks[reqId] = (loop, future)

        running_ibsocket.tickSnapshotEnd(reqId)

        await asyncio.sleep(0.05)

        # Stream data should be preserved (active subscription)
        assert reqId in running_ibsocket._stream_data
        assert reqId in running_ibsocket._stream_hooks


# =============================================================================
# TestIBSocketErrorCallback
# =============================================================================


class TestIBSocketErrorCallback:
    """Test error() and errorProtoBuf() callbacks."""

    @pytest.mark.asyncio
    async def test_error_callback_rejects_pending_future(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test error() callback rejects pending future."""
        reqId = 42
        awaitable = running_ibsocket.create_future(
            reqId, capability="datafeed", timeout=5
        )

        running_ibsocket.error(
            reqId=reqId,
            errorTime=1702656000000,
            errorCode=200,
            errorString="No security definition found",
        )

        await asyncio.sleep(0.05)

        with pytest.raises(ProviderException) as exc_info:
            await awaitable

        assert "200" in exc_info.value.code
        assert "No security definition found" in exc_info.value.message

    def test_error_callback_logs_system_errors(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test error() with reqId=-1 logs without raising."""
        # Should not raise - just log
        running_ibsocket.error(
            reqId=-1,
            errorTime=1702656000000,
            errorCode=2104,
            errorString="Market data farm connection is OK",
        )

    @pytest.mark.asyncio
    async def test_error_callback_notifies_stream_on_error(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test error() calls stream on_error callback."""
        reqId = 42
        ticker = "AAPL:NASDAQ:STK-12345"
        errors_received: list[ProviderException] = []

        async def callback(data: dict, fields: list) -> None:
            pass

        async def on_error(error: ProviderException) -> None:
            errors_received.append(error)

        running_ibsocket.register_stream(
            reqId, ticker, callback, capability="datafeed", on_error=on_error
        )

        running_ibsocket.error(
            reqId=reqId,
            errorTime=1702656000000,
            errorCode=354,
            errorString="Not subscribed to market data",
        )

        await asyncio.sleep(0.05)

        assert len(errors_received) == 1
        assert "354" in errors_received[0].code


# =============================================================================
# TestIBSocketManagedAccounts
# =============================================================================


class TestIBSocketManagedAccounts:
    """Test managedAccounts and nextValidId callbacks."""

    def test_managed_accounts_parses_list(self, running_ibsocket: IBSocket) -> None:
        """Test managedAccounts parses comma-separated account list."""
        running_ibsocket.managedAccounts("U123,U456,U789")

        assert running_ibsocket._reader_accounts == ["U123", "U456", "U789"]

    def test_next_valid_id_sets_ready_event(self, running_ibsocket: IBSocket) -> None:
        """Test nextValidId sets the ready event."""
        assert not running_ibsocket._ready_event.is_set()

        running_ibsocket.nextValidId(100)

        assert running_ibsocket._nxt_order_id == 100
        assert running_ibsocket._ready_event.is_set()


# =============================================================================
# Wire Protocol Tests (Phase 0.2)
# =============================================================================


class TestToStr:
    """Test to_str() wire encoding function.

    Converts Python values to TWS wire protocol strings.
    """

    def test_bool_true_to_one(self) -> None:
        """Test True converts to '1'."""
        assert to_str(True) == "1"

    def test_bool_false_to_zero(self) -> None:
        """Test False converts to '0'."""
        assert to_str(False) == "0"

    def test_list_to_comma_separated(self) -> None:
        """Test list converts to comma-separated string."""
        assert to_str([1, 2, 3]) == "1,2,3"
        assert to_str(["a", "b", "c"]) == "a,b,c"

    def test_empty_list_to_empty_string(self) -> None:
        """Test empty list converts to empty string."""
        assert to_str([]) == ""

    def test_nested_list_flattens(self) -> None:
        """Test nested list is recursively converted."""
        assert to_str([[1, 2], [3, 4]]) == "1,2,3,4"

    def test_unset_integer_to_empty(self) -> None:
        """Test UNSET_INTEGER converts to empty string."""
        from ibapi.const import UNSET_INTEGER

        assert to_str(UNSET_INTEGER) == ""

    def test_unset_double_to_empty(self) -> None:
        """Test UNSET_DOUBLE converts to empty string."""
        from ibapi.const import UNSET_DOUBLE

        assert to_str(UNSET_DOUBLE) == ""

    def test_double_infinity_to_infinity_str(self) -> None:
        """Test DOUBLE_INFINITY converts to infinity string."""
        from ibapi.const import DOUBLE_INFINITY, INFINITY_STR

        assert to_str(DOUBLE_INFINITY) == str(INFINITY_STR)

    def test_integer_to_string(self) -> None:
        """Test integer converts to string."""
        assert to_str(42) == "42"
        assert to_str(-1) == "-1"
        assert to_str(0) == "0"

    def test_float_to_string(self) -> None:
        """Test float converts to string."""
        assert to_str(3.14159) == "3.14159"

    def test_string_passthrough(self) -> None:
        """Test string passes through unchanged."""
        assert to_str("AAPL") == "AAPL"
        assert to_str("") == ""


class TestMakeFields:
    """Test make_fields() wire encoding function.

    Converts list of values to null-delimited byte string.
    """

    def test_single_value(self) -> None:
        """Test single value encoding."""
        result = make_fields([42])
        assert result == b"42\x00"

    def test_multiple_values(self) -> None:
        """Test multiple values encoding."""
        result = make_fields([1, "AAPL", 100.5])
        assert result == b"1\x00AAPL\x00100.5\x00"

    def test_empty_list(self) -> None:
        """Test empty list encoding."""
        result = make_fields([])
        assert result == b""

    def test_with_bool_values(self) -> None:
        """Test bool values are encoded correctly."""
        result = make_fields([True, False])
        assert result == b"1\x000\x00"

    def test_with_empty_string(self) -> None:
        """Test empty string is encoded as just null."""
        result = make_fields(["a", "", "b"])
        assert result == b"a\x00\x00b\x00"


class TestDecodeData:
    """Test decode_data() wire decoding function.

    Parses TWS wire protocol messages from byte buffer.
    """

    def test_incomplete_header(self) -> None:
        """Test incomplete header returns -1."""
        buf = bytearray(b"\x00\x00")  # Only 2 bytes, need 4 for header
        msg_id, payload, buf, buf_siz = decode_data(buf, 2)

        assert msg_id == -1
        assert payload == b""
        assert buf_siz == 2

    def test_incomplete_message(self) -> None:
        """Test incomplete message returns -1."""
        # Header says 100 bytes, but only have 10
        buf = bytearray(b"\x00\x00\x00\x64" + b"short")  # 100 bytes declared
        msg_id, payload, buf, buf_siz = decode_data(buf, 9)

        assert msg_id == -1
        assert payload == b""

    def test_complete_message(self) -> None:
        """Test complete message parsing."""
        # Message: size=12 (4 for msgId + 8 payload), msgId=1, payload="testdata"
        # Size field doesn't include itself (4 bytes)
        msg_size = 4 + 8  # msgId (4) + payload (8)
        buf = bytearray(
            msg_size.to_bytes(4, "big")
            + (1).to_bytes(4, "big")  # size
            + b"testdata"  # msgId  # payload
        )
        buf_siz = len(buf)

        msg_id, payload, remaining_buf, new_buf_siz = decode_data(buf, buf_siz)

        assert msg_id == 1
        assert payload == b"testdata"
        assert new_buf_siz == 0  # No remaining data

    def test_buffer_management(self) -> None:
        """Test buffer is properly trimmed after message consumption."""
        # Two messages back-to-back
        msg1_size = 4 + 4  # msgId + "msg1"
        msg2_size = 4 + 4  # msgId + "msg2"
        buf = bytearray(
            msg1_size.to_bytes(4, "big")
            + (1).to_bytes(4, "big")
            + b"msg1"
            + msg2_size.to_bytes(4, "big")
            + (2).to_bytes(4, "big")
            + b"msg2"
        )
        buf_siz = len(buf)

        # First decode
        msg_id, payload, buf, buf_siz = decode_data(buf, buf_siz)
        assert msg_id == 1
        assert payload == b"msg1"

        # Second decode from remaining buffer
        msg_id, payload, buf, buf_siz = decode_data(buf, buf_siz)
        assert msg_id == 2
        assert payload == b"msg2"
        assert buf_siz == 0

    def test_empty_buffer(self) -> None:
        """Test empty buffer returns -1."""
        buf = bytearray()
        msg_id, payload, buf, buf_siz = decode_data(buf, 0)

        assert msg_id == -1
        assert payload == b""
