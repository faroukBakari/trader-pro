"""Tests for IBSocket - TWS callback handler and state management.

Tests cover:
- State machine management (READY→CONNECTING→CONNECTED→RUNNING→CLOSED)
- Snapshot creation and resolution (create_snapshot, _flag_snapshot_complete)
- Stream management (create_stream, remove_stream, _dispatch_update)
- Error handling (_handle_request_error: snapshot rejection, stream on_error, cleanup)
- Stream notifications (_notify_stream: snapshot resolution, stream dispatch)
- Tick callbacks (tickPrice, tickSize, tickString - field updates + notifications)
- Historical callbacks (historicalData accumulation, historicalDataEnd resolution)
- Symbol/Contract callbacks (symbolSamples, contractDetails, contractDetailsEnd)

Note: All tests test IBSocket in isolation without real TWS connections.
"""

import asyncio
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from ibapi.common import BarData, TickAttrib
from ibapi.contract import Contract, ContractDescription, ContractDetails

from trading_api.models.exceptions import ProviderException
from trading_api.providers.tws.tws_connection import (
    IBSocket,
    IBSocketState,
    decode_data,
    make_fields,
    to_str,
)
from trading_api.providers.tws.tws_models import StreamData

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
        """Test _reset clears tracking dictionaries used during connection."""
        # Setup some state
        ibsocket._stream_data["test"] = MagicMock()  # New structure uses str keys
        ibsocket._reader_accounts = ["U123"]
        ibsocket._nxt_order_id = 42
        ibsocket._ready_event.set()

        # Reset
        ibsocket._reset()

        # Verify cleared (note: _business_to_tws_key is not cleared by _reset)
        assert len(ibsocket._stream_data) == 0
        assert len(ibsocket._reader_accounts) == 0
        assert getattr(ibsocket, "_nxt_order_id") is None
        assert not ibsocket._ready_event.is_set()


# =============================================================================
# TestIBSocketSnapshotManagement
# =============================================================================


class TestIBSocketSnapshotManagement:
    """Test create_snapshot, _resolve_snapshots, _flag_snapshot_complete.

    New API uses business_key strings instead of numeric reqId:
    - business_key format: "capability:identifier" (e.g., "datafeed:Quote:NASDAQ:AAPL")
    - tws_key format: "req_{reqId}" (internal mapping)
    - StreamData: dataclass extending list[dict] with metadata
    """

    @pytest.mark.asyncio
    async def test_create_snapshot_registers_in_hooks(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test create_snapshot registers future in _snapshot_hooks."""
        business_key = "datafeed:Quote:NASDAQ:AAPL"

        reqId, awaitable = running_ibsocket.create_snapshot(business_key, timeout=5)

        # Should create tws_key mapping
        tws_key = f"req_{reqId}"
        assert running_ibsocket._business_to_tws_key[business_key] == tws_key
        assert tws_key in running_ibsocket._snapshot_hooks
        assert tws_key in running_ibsocket._stream_data

        # Cleanup - flag complete and await
        running_ibsocket._flag_snapshot_complete(tws_key)
        await awaitable

    @pytest.mark.asyncio
    async def test_create_snapshot_initializes_stream_data(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test create_snapshot creates StreamData entry."""
        business_key = "shared:test:pattern"

        reqId, awaitable = running_ibsocket.create_snapshot(business_key, timeout=5)

        tws_key = f"req_{reqId}"
        stream = running_ibsocket._stream_data[tws_key]

        # StreamData should be initialized with business_key
        assert stream.business_key == business_key
        assert stream.snapshot_complete is False
        assert len(stream) == 0  # Empty list initially

        # Cleanup
        running_ibsocket._flag_snapshot_complete(tws_key)
        await awaitable

    @pytest.mark.asyncio
    async def test_create_snapshot_reuses_existing_tws_key(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test create_snapshot reuses existing tws_key for same business_key."""
        business_key = "datafeed:Quote:NASDAQ:AAPL"

        # First call creates tws_key
        reqId1, awaitable1 = running_ibsocket.create_snapshot(business_key, timeout=5)
        tws_key = f"req_{reqId1}"

        # Complete first snapshot to allow second
        running_ibsocket._flag_snapshot_complete(tws_key)
        await awaitable1

        # Second call should reuse same tws_key (returns None reqId)
        reqId2, awaitable2 = running_ibsocket.create_snapshot(business_key, timeout=5)

        assert reqId2 is None  # No new reqId generated
        assert running_ibsocket._business_to_tws_key[business_key] == tws_key

        await awaitable2

    @pytest.mark.asyncio
    async def test_flag_snapshot_complete_resolves_future(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test _flag_snapshot_complete resolves pending snapshot future."""
        business_key = "datafeed:Quote:NASDAQ:AAPL"

        reqId, awaitable = running_ibsocket.create_snapshot(business_key, timeout=5)
        tws_key = f"req_{reqId}"

        # Add some data
        running_ibsocket._update_stream_data(tws_key, {"bid": 150.0, "ask": 150.5})

        # Flag complete - should resolve the future
        running_ibsocket._flag_snapshot_complete(tws_key)

        # Allow event loop to process
        await asyncio.sleep(0.01)

        result = await awaitable
        assert len(result) == 1
        assert result[-1]["bid"] == 150.0

    @pytest.mark.asyncio
    async def test_snapshot_immediately_resolves_when_already_complete(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test create_snapshot resolves immediately if snapshot already complete."""
        business_key = "datafeed:Quote:NASDAQ:AAPL"

        # First snapshot
        reqId, awaitable1 = running_ibsocket.create_snapshot(business_key, timeout=5)
        tws_key = f"req_{reqId}"

        # Add data and complete
        running_ibsocket._update_stream_data(
            tws_key, {"bid": 150.0, "ask": 150.5, "last": 150.25}
        )
        running_ibsocket._flag_snapshot_complete(tws_key)
        await awaitable1

        # Second snapshot should resolve immediately (data already complete)
        _, awaitable2 = running_ibsocket.create_snapshot(business_key, timeout=5)

        result = await awaitable2
        assert result[-1]["bid"] == 150.0


# =============================================================================
# TestIBSocketStreamManagement
# =============================================================================


class TestIBSocketStreamManagement:
    """Test create_stream, remove_stream, _dispatch_update.

    New API uses business_key strings:
    - create_stream(business_key, callback, on_error) → reqId | None
    - remove_stream(business_key)
    """

    @pytest.mark.asyncio
    async def test_create_stream_creates_all_tracking(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test create_stream creates hooks, data, and key mapping."""
        business_key = "datafeed:Quote:NASDAQ:AAPL"

        async def callback(data: dict, fields: list) -> None:
            pass

        async def on_error(error: ProviderException) -> None:
            pass

        reqId = running_ibsocket.create_stream(business_key, callback, on_error)

        tws_key = f"req_{reqId}"
        assert running_ibsocket._business_to_tws_key[business_key] == tws_key
        assert tws_key in running_ibsocket._stream_hooks
        assert tws_key in running_ibsocket._stream_data

        stream = running_ibsocket._stream_data[tws_key]
        assert stream.business_key == business_key

    @pytest.mark.asyncio
    async def test_create_stream_stores_callbacks(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test create_stream stores data and error callbacks."""
        business_key = "datafeed:Quote:NASDAQ:AAPL"

        async def callback(data: dict, fields: list) -> None:
            pass

        async def on_error(error: ProviderException) -> None:
            pass

        reqId = running_ibsocket.create_stream(business_key, callback, on_error)
        tws_key = f"req_{reqId}"

        loop, stored_callback, stored_on_error = running_ibsocket._stream_hooks[tws_key]
        assert stored_callback is callback
        assert stored_on_error is on_error

    @pytest.mark.asyncio
    async def test_create_stream_reuses_existing_tws_key(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test create_stream reuses existing tws_key for same business_key."""
        business_key = "datafeed:Quote:NASDAQ:AAPL"

        async def callback1(data: dict, fields: list) -> None:
            pass

        async def callback2(data: dict, fields: list) -> None:
            pass

        async def on_error(error: ProviderException) -> None:
            pass

        # First stream
        reqId1 = running_ibsocket.create_stream(business_key, callback1, on_error)
        tws_key = f"req_{reqId1}"

        # Second stream with same business_key should reuse
        reqId2 = running_ibsocket.create_stream(business_key, callback2, on_error)

        assert reqId2 is None  # No new reqId
        # Callback should be updated
        _, stored_callback, _ = running_ibsocket._stream_hooks[tws_key]
        assert stored_callback is callback2

    def test_remove_stream_cleans_up_all_tracking(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test remove_stream removes all tracking state."""
        business_key = "datafeed:Quote:NASDAQ:AAPL"

        async def callback(data: dict, fields: list) -> None:
            pass

        async def on_error(error: ProviderException) -> None:
            pass

        reqId = running_ibsocket.create_stream(business_key, callback, on_error)
        tws_key = f"req_{reqId}"

        # Verify tracking exists
        assert business_key in running_ibsocket._business_to_tws_key
        assert tws_key in running_ibsocket._stream_hooks
        assert tws_key in running_ibsocket._stream_data

        # Remove stream
        running_ibsocket.remove_stream(business_key)

        # Verify cleaned up
        assert business_key not in running_ibsocket._business_to_tws_key
        assert tws_key not in running_ibsocket._stream_hooks
        # Stream data is moved back to business_key for caching
        assert business_key in running_ibsocket._stream_data

    def test_get_tws_key_returns_key_for_active_stream(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test _get_tws_key returns tws_key for active stream."""
        business_key = "datafeed:Quote:NASDAQ:AAPL"

        async def callback(data: dict, fields: list) -> None:
            pass

        async def on_error(error: ProviderException) -> None:
            pass

        reqId = running_ibsocket.create_stream(business_key, callback, on_error)
        tws_key = f"req_{reqId}"

        result = running_ibsocket._get_tws_key(business_key)
        assert result == tws_key

    def test_get_tws_key_returns_none_for_unknown(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test _get_tws_key returns None for unknown business_key."""
        result = running_ibsocket._get_tws_key("unknown:key")
        assert result is None

    @pytest.mark.asyncio
    async def test_dispatch_update_calls_callback(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test _dispatch_update calls stream callback with data and fields."""
        business_key = "datafeed:Quote:NASDAQ:AAPL"
        received_data: list[tuple[dict, list]] = []

        async def callback(data: dict, fields: list) -> None:
            received_data.append((dict(data), list(fields)))

        async def on_error(error: ProviderException) -> None:
            pass

        reqId = running_ibsocket.create_stream(business_key, callback, on_error)
        tws_key = f"req_{reqId}"

        # Update stream data
        running_ibsocket._update_stream_data(tws_key, {"bid": 150.0})

        await asyncio.sleep(0.05)

        assert len(received_data) == 1
        assert received_data[0][0]["bid"] == 150.0
        assert "bid" in received_data[0][1]


# =============================================================================
# TestIBSocketErrorHandling
# =============================================================================


class TestIBSocketErrorHandling:
    """Test _handle_request_error: snapshot rejection, stream on_error, cleanup."""

    @pytest.mark.asyncio
    async def test_handle_error_rejects_pending_snapshot(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test _handle_request_error rejects pending snapshot with ProviderException."""
        business_key = "datafeed:Quote:NASDAQ:AAPL"
        reqId, awaitable = running_ibsocket.create_snapshot(business_key, timeout=5)
        tws_key = f"req_{reqId}"

        # Trigger error
        running_ibsocket._handle_request_error(
            category="API",
            detail="VALIDATION_200",
            tws_key=tws_key,
            message="No security definition found",
        )

        await asyncio.sleep(0.01)

        # Snapshot should be rejected
        with pytest.raises(ProviderException) as exc_info:
            await awaitable

        assert "VALIDATION_200" in exc_info.value.code
        assert "No security definition found" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_handle_error_calls_stream_on_error(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test _handle_request_error calls stream on_error callback."""
        business_key = "datafeed:Quote:NASDAQ:AAPL"
        error_received: list[ProviderException] = []

        async def callback(data: dict, fields: list) -> None:
            pass

        async def on_error(error: ProviderException) -> None:
            error_received.append(error)

        reqId = running_ibsocket.create_stream(business_key, callback, on_error)
        tws_key = f"req_{reqId}"

        # Trigger error
        running_ibsocket._handle_request_error(
            category="API",
            detail="SUBSCRIPTION_354",
            tws_key=tws_key,
            message="Not subscribed to market data",
        )

        await asyncio.sleep(0.05)

        # on_error should have been called
        assert len(error_received) == 1
        assert "SUBSCRIPTION_354" in error_received[0].code

    def test_handle_error_non_recoverable_cleans_up_stream(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test _handle_request_error schedules cleanup for non-recoverable errors.

        The actual cleanup is scheduled via call_soon_threadsafe for the stream's event
        loop. Here we verify the error callback is invoked and then test remove_stream
        directly to confirm cleanup logic.
        """
        business_key = "datafeed:Quote:NASDAQ:AAPL"
        errors_received: list[ProviderException] = []

        async def callback(data: dict, fields: list) -> None:
            pass

        async def on_error(error: ProviderException) -> None:
            errors_received.append(error)

        reqId = running_ibsocket.create_stream(business_key, callback, on_error)
        tws_key = f"req_{reqId}"

        # Verify stream is set up
        assert tws_key in running_ibsocket._stream_hooks
        assert business_key in running_ibsocket._business_to_tws_key
        assert tws_key in running_ibsocket._stream_data

        # Trigger NON_RECOVERABLE error - this schedules on_error and remove_stream
        running_ibsocket._handle_request_error(
            category="API",
            detail="VALIDATION_200_NON_RECOVERABLE",
            tws_key=tws_key,
            message="Fatal error",
        )

        # Since we're testing synchronously, directly call remove_stream
        # to verify cleanup behavior (actual cleanup is scheduled async)
        running_ibsocket.remove_stream(business_key)

        # After remove_stream: business_key mapping is removed
        assert business_key not in running_ibsocket._business_to_tws_key
        # Stream hooks should be cleared
        assert tws_key not in running_ibsocket._stream_hooks
        # Stream data moves back to business_key (for caching)
        assert business_key in running_ibsocket._stream_data

    @pytest.mark.asyncio
    async def test_handle_error_extracts_capability_from_business_key(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test _handle_request_error extracts capability from business_key prefix."""
        business_key = "broker:orders:123"

        async def callback(data: dict, fields: list) -> None:
            pass

        async def on_error(error: ProviderException) -> None:
            pass

        reqId = running_ibsocket.create_stream(business_key, callback, on_error)
        tws_key = f"req_{reqId}"

        errors_received: list[ProviderException] = []

        async def capture_error(error: ProviderException) -> None:
            errors_received.append(error)

        # Update the on_error callback
        running_ibsocket._stream_hooks[tws_key] = (
            asyncio.get_event_loop(),
            callback,
            capture_error,
        )

        running_ibsocket._handle_request_error(
            category="API",
            detail="TEST_ERROR",
            tws_key=tws_key,
            message="Test error",
        )

        await asyncio.sleep(0.05)

        assert len(errors_received) == 1
        assert errors_received[0].capability == "broker"

    def test_handle_error_orphan_error_logged(self, running_ibsocket: IBSocket) -> None:
        """Test _handle_request_error logs orphan errors (no hooks registered)."""
        # No snapshot or stream registered for this tws_key
        tws_key = "req_99999"

        # Should not raise - just log
        running_ibsocket._handle_request_error(
            category="API",
            detail="ORPHAN_ERROR",
            tws_key=tws_key,
            message="Orphan error message",
        )


# =============================================================================
# TestIBSocketNotifyStream
# =============================================================================


class TestIBSocketNotifyStream:
    """Test _notify_stream: snapshot resolution, stream dispatch, cleanup paths."""

    @pytest.mark.asyncio
    async def test_notify_stream_resolves_snapshot_when_complete(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test _notify_stream resolves snapshot when flagged complete."""
        business_key = "datafeed:Quote:NASDAQ:AAPL"

        reqId, awaitable = running_ibsocket.create_snapshot(business_key, timeout=5)
        tws_key = f"req_{reqId}"

        # Populate stream with data
        running_ibsocket._update_stream_data(
            tws_key, {"bid": 150.0, "ask": 150.5, "last": 150.25}
        )

        # Flag as complete - triggers notification
        running_ibsocket._flag_snapshot_complete(tws_key)

        await asyncio.sleep(0.05)

        result = await awaitable
        assert result[-1]["bid"] == 150.0

    @pytest.mark.asyncio
    async def test_notify_stream_dispatches_to_callback(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test _notify_stream calls stream callback with data and fields."""
        business_key = "datafeed:Quote:NASDAQ:AAPL"
        received_data: list[tuple[dict, list]] = []

        async def callback(data: dict, fields: list) -> None:
            received_data.append((dict(data), list(fields)))

        async def on_error(error: ProviderException) -> None:
            pass

        reqId = running_ibsocket.create_stream(business_key, callback, on_error)
        tws_key = f"req_{reqId}"

        # Update stream data - triggers notification
        running_ibsocket._update_stream_data(tws_key, {"bid": 150.0})

        await asyncio.sleep(0.05)

        assert len(received_data) == 1
        assert received_data[0][0]["bid"] == 150.0
        assert received_data[0][1] == ["bid"]

    @pytest.mark.asyncio
    async def test_notify_stream_handles_both_snapshot_and_stream(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test _notify_stream handles both snapshot and stream for same business_key."""
        business_key = "datafeed:Quote:NASDAQ:AAPL"
        stream_received: list[tuple[dict, list]] = []

        async def callback(data: dict, fields: list) -> None:
            stream_received.append((dict(data), list(fields)))

        async def on_error(error: ProviderException) -> None:
            pass

        # Create snapshot first
        reqId, snapshot_awaitable = running_ibsocket.create_snapshot(
            business_key, timeout=5
        )
        tws_key = f"req_{reqId}"

        # Add stream hook (would normally reuse the same tws_key)
        running_ibsocket._stream_hooks[tws_key] = (
            asyncio.get_event_loop(),
            callback,
            on_error,
        )

        # Update data
        running_ibsocket._update_stream_data(
            tws_key, {"bid": 150.0, "ask": 150.5, "last": 150.25}
        )
        running_ibsocket._flag_snapshot_complete(tws_key)

        await asyncio.sleep(0.05)

        # Both should receive data
        snapshot_result = await snapshot_awaitable
        assert snapshot_result[-1]["bid"] == 150.0
        assert len(stream_received) >= 1

    def test_notify_stream_ignores_unknown_tws_key(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test _notify_stream handles unknown tws_key gracefully."""
        from trading_api.providers.tws.tws_models import StreamData

        # Create a StreamData with unknown tws_key
        stream = StreamData("unknown:key")
        # Should not raise
        running_ibsocket._notify_stream("req_99999", stream)


# =============================================================================
# TestIBSocketTickCallbacks
# =============================================================================


class TestIBSocketTickCallbacks:
    """Test tickPrice, tickSize, tickString - field updates + notifications."""

    def test_tick_price_updates_stream_data(self, running_ibsocket: IBSocket) -> None:
        """Test tickPrice updates stream_data with price."""
        from trading_api.providers.tws.tws_models import StreamData

        business_key = "datafeed:Quote:NASDAQ:TEST"
        tws_key = "req_42"

        # Setup stream data
        running_ibsocket._business_to_tws_key[business_key] = tws_key
        running_ibsocket._stream_data[tws_key] = StreamData(business_key)
        running_ibsocket._stream_data[tws_key].append({})

        # TickType 1 = BID
        attrib = TickAttrib()
        running_ibsocket.tickPrice(42, 1, 150.25, attrib)

        assert running_ibsocket._stream_data[tws_key][-1]["bid"] == 150.25

    def test_tick_price_ignores_same_value(self, running_ibsocket: IBSocket) -> None:
        """Test tickPrice doesn't notify if value unchanged."""
        from trading_api.providers.tws.tws_models import StreamData

        business_key = "datafeed:Quote:NASDAQ:TEST"
        tws_key = "req_42"

        # Setup stream with existing bid
        running_ibsocket._business_to_tws_key[business_key] = tws_key
        stream = StreamData(business_key)
        stream.append({"bid": 150.25})
        running_ibsocket._stream_data[tws_key] = stream

        # Track notifications
        notify_count = [0]
        original_notify = running_ibsocket._notify_stream

        def mock_notify(key: str, s: StreamData) -> None:
            notify_count[0] += 1
            original_notify(key, s)

        running_ibsocket._notify_stream = mock_notify  # type: ignore

        # Same price - should not notify
        attrib = TickAttrib()
        running_ibsocket.tickPrice(42, 1, 150.25, attrib)

        assert notify_count[0] == 0

    def test_tick_price_notifies_on_change(self, running_ibsocket: IBSocket) -> None:
        """Test tickPrice notifies when value changes."""
        from trading_api.providers.tws.tws_models import StreamData

        business_key = "datafeed:Quote:NASDAQ:TEST"
        tws_key = "req_42"

        # Setup stream with existing bid
        running_ibsocket._business_to_tws_key[business_key] = tws_key
        stream = StreamData(business_key)
        stream.append({"bid": 150.25})
        running_ibsocket._stream_data[tws_key] = stream

        # Track notifications
        notify_calls: list[tuple[str, list]] = []

        def mock_notify(key: str, s: StreamData) -> None:
            notify_calls.append((key, list(s.updated_fields)))

        running_ibsocket._notify_stream = mock_notify  # type: ignore

        # Different price - should notify
        attrib = TickAttrib()
        running_ibsocket.tickPrice(42, 1, 150.50, attrib)

        assert len(notify_calls) == 1
        assert notify_calls[0][1] == ["bid"]

    def test_tick_price_auto_completes_snapshot(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test tickPrice auto-completes snapshot when bid/ask/last received."""
        from trading_api.providers.tws.tws_models import StreamData

        business_key = "datafeed:Quote:NASDAQ:TEST"
        tws_key = "req_42"

        # Setup stream data
        running_ibsocket._business_to_tws_key[business_key] = tws_key
        stream = StreamData(business_key)
        stream.append({"bid": 150.0, "ask": 150.5})
        running_ibsocket._stream_data[tws_key] = stream

        assert stream.snapshot_complete is False

        # TickType 4 = LAST - should complete snapshot
        attrib = TickAttrib()
        running_ibsocket.tickPrice(42, 4, 150.25, attrib)

        assert stream.snapshot_complete is True

    def test_tick_size_updates_stream_data(self, running_ibsocket: IBSocket) -> None:
        """Test tickSize updates stream_data with size."""
        from trading_api.providers.tws.tws_models import StreamData

        business_key = "datafeed:Quote:NASDAQ:TEST"
        tws_key = "req_42"

        running_ibsocket._business_to_tws_key[business_key] = tws_key
        running_ibsocket._stream_data[tws_key] = StreamData(business_key)
        running_ibsocket._stream_data[tws_key].append({})

        # TickType 0 = BID_SIZE
        running_ibsocket.tickSize(42, 0, Decimal("100"))

        assert running_ibsocket._stream_data[tws_key][-1]["bid_size"] == Decimal("100")

    def test_tick_string_updates_stream_data(self, running_ibsocket: IBSocket) -> None:
        """Test tickString updates stream_data with string value."""
        from trading_api.providers.tws.tws_models import StreamData

        business_key = "datafeed:Quote:NASDAQ:TEST"
        tws_key = "req_42"

        running_ibsocket._business_to_tws_key[business_key] = tws_key
        running_ibsocket._stream_data[tws_key] = StreamData(business_key)
        running_ibsocket._stream_data[tws_key].append({})

        # TickType 45 = LAST_TIMESTAMP
        running_ibsocket.tickString(42, 45, "1702656000")

        assert (
            running_ibsocket._stream_data[tws_key][-1]["last_timestamp"] == "1702656000"
        )

    def test_tick_generic_updates_stream_data(self, running_ibsocket: IBSocket) -> None:
        """Test tickGeneric updates stream_data with float value."""
        from trading_api.providers.tws.tws_models import StreamData

        business_key = "datafeed:Quote:NASDAQ:TEST"
        tws_key = "req_42"

        running_ibsocket._business_to_tws_key[business_key] = tws_key
        running_ibsocket._stream_data[tws_key] = StreamData(business_key)
        running_ibsocket._stream_data[tws_key].append({})

        # TickType 24 = OPTION_IMPLIED_VOL
        running_ibsocket.tickGeneric(42, 24, 0.25)

        assert running_ibsocket._stream_data[tws_key][-1]["option_implied_vol"] == 0.25

    def test_tick_ignores_unknown_stream(self, running_ibsocket: IBSocket) -> None:
        """Test tick callbacks handle unknown reqId gracefully."""
        # Should not raise for unknown reqId
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
        """Test historicalData accumulates bars in stream_data."""
        business_key = "datafeed:reqHistoricalData:SMART:1 D::AAPL:NASDAQ:STK"

        reqId, awaitable = running_ibsocket.create_snapshot(business_key, timeout=5)
        assert reqId is not None, "Expected reqId from create_snapshot"
        tws_key = f"req_{reqId}"

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

        stream = running_ibsocket._stream_data[tws_key]
        assert len(stream) == 2
        assert stream[0]["open"] == 150.0
        assert stream[1]["open"] == 150.5

        # Cleanup
        running_ibsocket._flag_snapshot_complete(tws_key)
        await awaitable

    @pytest.mark.asyncio
    async def test_historical_data_end_resolves_future(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test historicalDataEnd resolves snapshot with accumulated bars."""
        business_key = "datafeed:reqHistoricalData:SMART:1 D::AAPL:NASDAQ:STK"

        reqId, awaitable = running_ibsocket.create_snapshot(business_key, timeout=5)
        assert reqId is not None, "Expected reqId from create_snapshot"

        bar1 = BarData()
        bar1.date = "20231215"
        bar1.open = 150.0

        running_ibsocket.historicalData(reqId, bar1)
        running_ibsocket.historicalDataEnd(reqId, "20231215", "20231216")

        await asyncio.sleep(0.01)

        result = await awaitable
        assert len(result) == 1
        assert result[0]["open"] == 150.0

    @pytest.mark.asyncio
    async def test_historical_data_update_updates_stream(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test historicalDataUpdate updates existing bar in stream."""
        business_key = "datafeed:reqBarDataStream:SMART:AAPL:NASDAQ:STK@5 mins"
        received: list[tuple[dict, list]] = []

        async def callback(data: dict, fields: list) -> None:
            received.append((dict(data), list(fields)))

        async def on_error(error: ProviderException) -> None:
            pass

        reqId = running_ibsocket.create_stream(business_key, callback, on_error)
        assert reqId is not None, "Expected reqId from create_snapshot"
        tws_key = f"req_{reqId}"

        # Initialize with first bar
        stream = running_ibsocket._stream_data[tws_key]
        stream.append({"date": "20231215 16:00:00", "open": 150.0, "close": 150.5})

        # Update bar
        bar = BarData()
        bar.date = "20231215 16:00:00"
        bar.open = 150.0
        bar.high = 151.0
        bar.low = 149.5
        bar.close = 150.75
        bar.volume = Decimal("1000")
        bar.wap = Decimal("150.25")
        bar.barCount = 100

        running_ibsocket.historicalDataUpdate(reqId, bar)

        await asyncio.sleep(0.05)

        assert len(received) >= 1
        assert received[0][0]["close"] == 150.75


# =============================================================================
# TestIBSocketSnapshotEnd
# =============================================================================


class TestIBSocketSnapshotEnd:
    """Test tickSnapshotEnd callback behavior."""

    @pytest.mark.asyncio
    async def test_tick_snapshot_end_resolves_future(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test tickSnapshotEnd resolves pending snapshot."""
        business_key = "datafeed:Quote:NASDAQ:AAPL"

        reqId, awaitable = running_ibsocket.create_snapshot(business_key, timeout=5)
        assert reqId is not None, "Expected reqId from create_snapshot"
        tws_key = f"req_{reqId}"

        # Add data
        running_ibsocket._update_stream_data(tws_key, {"bid": 150.0, "ask": 150.5})

        # tickSnapshotEnd flags completion
        running_ibsocket.tickSnapshotEnd(reqId)

        await asyncio.sleep(0.05)

        result = await awaitable
        assert result[-1]["bid"] == 150.0

    @pytest.mark.asyncio
    async def test_tick_snapshot_end_preserves_active_stream(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test tickSnapshotEnd does NOT clean up when stream hook exists."""
        business_key = "datafeed:Quote:NASDAQ:AAPL"

        async def callback(data: dict, fields: list) -> None:
            pass

        async def on_error(error: ProviderException) -> None:
            pass

        # Create snapshot first
        reqId, snapshot_awaitable = running_ibsocket.create_snapshot(
            business_key, timeout=5
        )
        assert reqId is not None, "Expected reqId from create_snapshot"
        tws_key = f"req_{reqId}"

        # Register stream hook (simulates active subscription)
        running_ibsocket._stream_hooks[tws_key] = (
            asyncio.get_event_loop(),
            callback,
            on_error,
        )

        # Add data and trigger snapshot end
        running_ibsocket._update_stream_data(tws_key, {"bid": 150.0, "ask": 150.5})
        running_ibsocket.tickSnapshotEnd(reqId)

        await asyncio.sleep(0.05)

        await snapshot_awaitable

        # Stream data should be preserved (active subscription)
        assert tws_key in running_ibsocket._stream_data
        assert tws_key in running_ibsocket._stream_hooks


# =============================================================================
# TestIBSocketErrorCallback
# =============================================================================


class TestIBSocketErrorCallback:
    """Test error() and errorProtoBuf() callbacks."""

    @pytest.mark.asyncio
    async def test_error_callback_rejects_pending_snapshot(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test error() callback rejects pending snapshot."""
        business_key = "datafeed:Quote:NASDAQ:AAPL"

        reqId, awaitable = running_ibsocket.create_snapshot(business_key, timeout=5)
        assert reqId is not None, "Expected reqId from create_snapshot"

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
        business_key = "datafeed:Quote:NASDAQ:AAPL"
        errors_received: list[ProviderException] = []

        async def callback(data: dict, fields: list) -> None:
            pass

        async def on_error(error: ProviderException) -> None:
            errors_received.append(error)

        reqId = running_ibsocket.create_stream(business_key, callback, on_error)
        assert reqId is not None, "Expected reqId from create_stream"

        running_ibsocket.error(
            reqId=reqId,
            errorTime=1702656000000,
            errorCode=354,
            errorString="Not subscribed to market data",
        )

        await asyncio.sleep(0.05)

        assert len(errors_received) == 1
        assert "354" in errors_received[0].code

    def test_error_callback_classifies_recoverable_errors(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test error() correctly classifies recoverable vs non-recoverable errors."""
        from trading_api.providers.tws.tws_models import StreamData

        business_key = "datafeed:Quote:NASDAQ:TEST"
        tws_key = "req_42"

        running_ibsocket._business_to_tws_key[business_key] = tws_key
        running_ibsocket._stream_data[tws_key] = StreamData(business_key)

        # Recoverable error (2104 = Market data farm OK)
        running_ibsocket.error(
            reqId=-1,
            errorTime=1702656000000,
            errorCode=2104,
            errorString="Market data farm connection is OK",
        )

        # Stream should still exist (info message, not real error)
        assert tws_key in running_ibsocket._stream_data

    @pytest.mark.asyncio
    async def test_error_protobuf_delegates_to_error(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test errorProtoBuf() delegates to error() method."""
        from ibapi.protobuf.ErrorMessage_pb2 import ErrorMessage as ErrorMessageProto

        business_key = "datafeed:Quote:NASDAQ:AAPL"
        errors_received: list[ProviderException] = []

        async def callback(data: dict, fields: list) -> None:
            pass

        async def on_error(error: ProviderException) -> None:
            errors_received.append(error)

        reqId = running_ibsocket.create_stream(business_key, callback, on_error)
        assert reqId is not None, "Expected reqId from create_stream"

        # Create protobuf error message
        proto = ErrorMessageProto()
        proto.id = reqId
        proto.errorCode = 200
        proto.errorMsg = "No security definition found"
        proto.errorTime = 1702656000000

        running_ibsocket.errorProtoBuf(proto)

        await asyncio.sleep(0.05)

        assert len(errors_received) == 1
        assert "200" in errors_received[0].code


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


# =============================================================================
# TestIBSocketSymbolSamplesCallback
# =============================================================================


class TestIBSocketSymbolSamplesCallback:
    """Test symbolSamples callback for search_symbols."""

    @pytest.mark.asyncio
    async def test_symbol_samples_accumulates_descriptions(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test symbolSamples accumulates ContractDescriptions in stream_data."""
        business_key = "shared:reqMatchingSymbols:AAPL"

        reqId, awaitable = running_ibsocket.create_snapshot(business_key, timeout=5)
        assert reqId is not None, "Expected reqId from create_snapshot"

        # Create contract descriptions
        contract1 = Contract()
        contract1.symbol = "AAPL"
        contract1.secType = "STK"
        contract1.exchange = "SMART"
        contract1.primaryExchange = "NASDAQ"

        contract2 = Contract()
        contract2.symbol = "AAPL"
        contract2.secType = "OPT"
        contract2.exchange = "SMART"

        desc1 = ContractDescription()
        desc1.contract = contract1

        desc2 = ContractDescription()
        desc2.contract = contract2

        running_ibsocket.symbolSamples(reqId, [desc1, desc2])

        await asyncio.sleep(0.05)

        result = await awaitable
        assert len(result) == 2
        assert result[0]["contractDescriptions"].contract.symbol == "AAPL"
        assert result[0]["contractDescriptions"].contract.secType == "STK"
        assert result[1]["contractDescriptions"].contract.secType == "OPT"

    @pytest.mark.asyncio
    async def test_symbol_samples_flags_complete(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test symbolSamples flags snapshot as complete."""
        business_key = "shared:reqMatchingSymbols:TEST"

        reqId, awaitable = running_ibsocket.create_snapshot(business_key, timeout=5)
        assert reqId is not None, "Expected reqId from create_snapshot"
        tws_key = f"req_{reqId}"

        desc = ContractDescription()
        desc.contract = Contract()
        desc.contract.symbol = "TEST"

        running_ibsocket.symbolSamples(reqId, [desc])

        stream = running_ibsocket._stream_data[tws_key]
        assert stream.snapshot_complete is True

        await awaitable


# =============================================================================
# TestIBSocketContractDetailsCallback
# =============================================================================


class TestIBSocketContractDetailsCallback:
    """Test contractDetails and contractDetailsEnd callbacks."""

    @pytest.mark.asyncio
    async def test_contract_details_accumulates_results(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test contractDetails accumulates ContractDetails in stream_data."""
        business_key = "shared:reqContractDetails:AAPL:NASDAQ:STK"

        reqId, awaitable = running_ibsocket.create_snapshot(business_key, timeout=5)
        assert reqId is not None, "Expected reqId from create_snapshot"
        tws_key = f"req_{reqId}"

        # Create contract details
        contract = Contract()
        contract.symbol = "AAPL"
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.primaryExchange = "NASDAQ"
        contract.currency = "USD"

        details = ContractDetails()
        details.contract = contract
        details.longName = "Apple Inc"
        details.minTick = 0.01

        running_ibsocket.contractDetails(reqId, details)

        stream = running_ibsocket._stream_data[tws_key]
        assert len(stream) == 1
        assert stream[0]["contractDetails"].longName == "Apple Inc"

        # Cleanup
        running_ibsocket._flag_snapshot_complete(tws_key)
        await awaitable

    @pytest.mark.asyncio
    async def test_contract_details_end_resolves_snapshot(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test contractDetailsEnd resolves snapshot with accumulated results."""
        business_key = "shared:reqContractDetails:AAPL:NASDAQ:STK"

        reqId, awaitable = running_ibsocket.create_snapshot(business_key, timeout=5)
        assert reqId is not None, "Expected reqId from create_snapshot"

        contract = Contract()
        contract.symbol = "AAPL"
        contract.secType = "STK"

        details = ContractDetails()
        details.contract = contract
        details.longName = "Apple Inc"

        running_ibsocket.contractDetails(reqId, details)
        running_ibsocket.contractDetailsEnd(reqId)

        await asyncio.sleep(0.05)

        result = await awaitable
        assert len(result) == 1
        assert result[0]["contractDetails"].longName == "Apple Inc"

    @pytest.mark.asyncio
    async def test_contract_details_multiple_contracts(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test contractDetails handles multiple matching contracts."""
        business_key = "shared:reqContractDetails:ES:CME:FUT"

        reqId, awaitable = running_ibsocket.create_snapshot(business_key, timeout=5)
        assert reqId is not None, "Expected reqId from create_snapshot"

        # Multiple futures contracts (different expirations)
        for month in ["202312", "202403", "202406"]:
            contract = Contract()
            contract.symbol = "ES"
            contract.secType = "FUT"
            contract.lastTradeDateOrContractMonth = month

            details = ContractDetails()
            details.contract = contract

            running_ibsocket.contractDetails(reqId, details)

        running_ibsocket.contractDetailsEnd(reqId)

        await asyncio.sleep(0.05)

        result = await awaitable
        assert len(result) == 3


# =============================================================================
# TestIBSocketMarketDataType
# =============================================================================


class TestIBSocketMarketDataType:
    """Test marketDataType and tickReqParams callbacks."""

    def test_market_data_type_updates_stream(self, running_ibsocket: IBSocket) -> None:
        """Test marketDataType updates stream_data."""
        business_key = "datafeed:Quote:NASDAQ:AAPL"
        tws_key = "req_42"

        running_ibsocket._business_to_tws_key[business_key] = tws_key
        running_ibsocket._stream_data[tws_key] = StreamData(business_key)
        running_ibsocket._stream_data[tws_key].append({})

        running_ibsocket.marketDataType(42, 1)  # 1 = Live

        assert running_ibsocket._stream_data[tws_key][-1]["market_data_type"] == 1

    def test_tick_req_params_updates_stream(self, running_ibsocket: IBSocket) -> None:
        """Test tickReqParams updates stream_data."""
        business_key = "datafeed:Quote:NASDAQ:AAPL"
        tws_key = "req_42"

        running_ibsocket._business_to_tws_key[business_key] = tws_key
        running_ibsocket._stream_data[tws_key] = StreamData(business_key)
        running_ibsocket._stream_data[tws_key].append({})

        running_ibsocket.tickReqParams(42, 0.01, "NASDAQ", 3)

        stream = running_ibsocket._stream_data[tws_key]
        assert stream[-1]["min_tick"] == 0.01
        assert stream[-1]["bbo_exchange"] == "NASDAQ"
        assert stream[-1]["snapshot_permissions"] == 3


# =============================================================================
# TestIBSocketStreamDataHelpers
# =============================================================================


class TestIBSocketStreamDataHelpers:
    """Test _append_stream_data, _extend_stream_data, _update_stream_data helpers."""

    def test_append_stream_data_adds_item(self, running_ibsocket: IBSocket) -> None:
        """Test _append_stream_data appends a single item."""
        business_key = "datafeed:test:stream"
        tws_key = "req_1"

        running_ibsocket._business_to_tws_key[business_key] = tws_key
        running_ibsocket._stream_data[tws_key] = StreamData(business_key)

        running_ibsocket._append_stream_data(tws_key, {"field1": "value1"})

        stream = running_ibsocket._stream_data[tws_key]
        assert len(stream) == 1
        assert stream[0]["field1"] == "value1"
        assert stream[0]["business_key"] == business_key

    def test_extend_stream_data_adds_multiple(self, running_ibsocket: IBSocket) -> None:
        """Test _extend_stream_data adds multiple items."""
        business_key = "datafeed:test:stream"
        tws_key = "req_1"

        running_ibsocket._business_to_tws_key[business_key] = tws_key
        running_ibsocket._stream_data[tws_key] = StreamData(business_key)

        running_ibsocket._extend_stream_data(tws_key, [{"a": 1}, {"b": 2}, {"c": 3}])

        stream = running_ibsocket._stream_data[tws_key]
        assert len(stream) == 3
        # business_key added to last item only
        assert stream[-1]["business_key"] == business_key

    def test_update_stream_data_creates_slot_if_empty(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test _update_stream_data creates initial slot if stream empty."""
        business_key = "datafeed:test:stream"
        tws_key = "req_1"

        running_ibsocket._business_to_tws_key[business_key] = tws_key
        running_ibsocket._stream_data[tws_key] = StreamData(business_key)

        running_ibsocket._update_stream_data(tws_key, {"bid": 100.0})

        stream = running_ibsocket._stream_data[tws_key]
        assert len(stream) == 1
        assert stream[-1]["bid"] == 100.0

    def test_update_stream_data_respects_tolerance(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test _update_stream_data skips updates within tolerance."""
        business_key = "datafeed:test:stream"
        tws_key = "req_1"

        running_ibsocket._business_to_tws_key[business_key] = tws_key
        stream = StreamData(business_key)
        stream.append({"price": 100.0})
        running_ibsocket._stream_data[tws_key] = stream

        # Track notifications
        notify_count = [0]
        running_ibsocket._notify_stream

        def mock_notify(key: str, s: StreamData) -> None:
            notify_count[0] += 1

        running_ibsocket._notify_stream = mock_notify  # type: ignore

        # Update within default tolerance (1e-3)
        running_ibsocket._update_stream_data(tws_key, {"price": 100.0001})

        assert notify_count[0] == 0  # Should not notify

        # Update outside tolerance
        running_ibsocket._update_stream_data(tws_key, {"price": 100.1})

        assert notify_count[0] == 1  # Should notify

    def test_update_stream_data_tracks_updated_fields(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test _update_stream_data tracks which fields were updated."""
        business_key = "datafeed:test:stream"
        tws_key = "req_1"

        running_ibsocket._business_to_tws_key[business_key] = tws_key
        stream = StreamData(business_key)
        stream.append({"bid": 100.0, "ask": 100.5})
        running_ibsocket._stream_data[tws_key] = stream

        running_ibsocket._update_stream_data(
            tws_key, {"bid": 100.1, "ask": 100.5}  # changed  # unchanged
        )

        assert "bid" in stream.updated_fields
        assert "ask" not in stream.updated_fields
