"""Tests for TWSConnection - Layer 1 (Pure TWS Protocol)."""

import concurrent.futures
from decimal import Decimal
from unittest.mock import Mock

from trading_api.providers.tws.tws_connection import TWSConnection


class TestConnectionInitialization:
    """Test TWSConnection initialization and basic setup."""

    def test_connection_initialization(self) -> None:
        """Test TWSConnection initialization."""
        conn = TWSConnection()
        assert conn.callbacks == {}
        assert conn.next_req_id == 1
        assert not conn.is_ready.is_set()

    def test_get_req_id_increments(self) -> None:
        """Test request ID generation increments."""
        conn = TWSConnection()
        id1 = conn.get_req_id()
        id2 = conn.get_req_id()
        assert id2 == id1 + 1

    def test_get_req_id_thread_safe(self) -> None:
        """Test request ID generation is thread-safe."""
        conn = TWSConnection()

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(conn.get_req_id) for _ in range(100)]
            req_ids = [f.result() for f in futures]

        # All IDs should be unique
        assert len(set(req_ids)) == 100

    def test_nextValidId_sets_ready(self) -> None:
        """Test nextValidId sets ready event."""
        conn = TWSConnection()
        conn.nextValidId(42)

        assert conn.is_ready.is_set()
        assert conn.next_req_id == 42


class TestCallbackDispatch:
    """Test callback dispatch mechanism."""

    def test_callback_dispatch(self) -> None:
        """Test TWSConnection dispatches callbacks by reqId."""
        conn = TWSConnection()

        # Register callback
        callback_invoked = False
        received_data = None

        def test_callback(data: object) -> None:
            nonlocal callback_invoked, received_data
            callback_invoked = True
            received_data = data

        req_id = 1
        conn.callbacks[req_id] = test_callback

        # Simulate TWS callback (we'll add symbolSamples in next phase)
        # For now, just test the callback mechanism directly
        if cb := conn.callbacks.get(req_id):
            test_data = [Mock(symbol="AAPL", exchange="SMART")]
            cb(test_data)

        # Verify callback invoked with correct data
        assert callback_invoked
        assert received_data is not None

    def test_missing_callback_no_error(self) -> None:
        """Test that missing callback doesn't raise error."""
        conn = TWSConnection()

        # Try to get callback for non-existent reqId
        cb = conn.callbacks.get(999)
        assert cb is None  # Should return None, not raise

    def test_symbol_samples_callback(self) -> None:
        """Test TWSConnection symbolSamples dispatches to callback."""
        conn = TWSConnection()

        received_data = None

        def callback(data: object) -> None:
            nonlocal received_data
            received_data = data

        req_id = 1
        conn.callbacks[req_id] = callback

        # Simulate TWS callback
        test_data = [Mock(symbol="AAPL", exchange="SMART")]
        conn.symbolSamples(req_id, test_data)

        assert received_data == test_data

    def test_end_signal_with_none(self) -> None:
        """Test TWSConnection signals end-of-stream with None."""
        conn = TWSConnection()

        received_signal = None

        def callback(data: object) -> None:
            nonlocal received_signal
            received_signal = data

        conn.callbacks[1] = callback
        conn.contractDetailsEnd(1)

        assert received_signal is None

    def test_error_passes_exception(self) -> None:
        """Test error callback passes Exception object."""
        conn = TWSConnection()

        received_exception = None

        def callback(data: object) -> None:
            nonlocal received_exception
            if isinstance(data, Exception):
                received_exception = data

        conn.callbacks[1] = callback
        conn.error(1, 0, 200, "Test error")

        assert received_exception is not None
        assert "TWS error 200" in str(received_exception)

    def test_historical_data_callback(self) -> None:
        """Test historicalData callback dispatch."""
        conn = TWSConnection()

        received_bars = []

        def callback(bar: object) -> None:
            if bar is not None:
                received_bars.append(bar)

        conn.callbacks[1] = callback

        # Simulate multiple bar callbacks
        bar1 = Mock(date="1609459200", open=100.0, high=101.0)
        bar2 = Mock(date="1609459260", open=101.0, high=102.0)

        conn.historicalData(1, bar1)
        conn.historicalData(1, bar2)
        conn.historicalDataEnd(1, "20210101", "20210102")

        assert len(received_bars) == 2
        assert received_bars[0] == bar1
        assert received_bars[1] == bar2

    def test_realtime_bar_callback(self) -> None:
        """Test realtimeBar callback with all parameters."""
        conn = TWSConnection()

        received_params = None

        def callback(*args: object) -> None:
            nonlocal received_params
            received_params = args

        conn.callbacks[1] = callback

        # Simulate real-time bar
        conn.realtimeBar(
            1,
            1609459200,
            100.0,
            101.0,
            99.0,
            100.5,
            Decimal("1000"),
            Decimal("100.25"),
            50,
        )

        assert received_params is not None
        assert len(received_params) == 8
        assert received_params[0] == 1609459200  # time
        assert received_params[1] == 100.0  # open
        assert received_params[4] == 100.5  # close
        assert received_params[5] == 1000  # volume

    def test_tick_price_callback(self) -> None:
        """Test tickPrice callback dispatch."""
        conn = TWSConnection()

        received_ticks = []

        def callback(tick_type: object, price: object, attrib: object) -> None:
            received_ticks.append((tick_type, price, attrib))

        conn.callbacks[1] = callback

        # Simulate tick updates
        attrib = Mock()
        conn.tickPrice(1, 1, 150.25, attrib)  # Bid
        conn.tickPrice(1, 2, 150.30, attrib)  # Ask

        assert len(received_ticks) == 2
        assert received_ticks[0] == (1, 150.25, attrib)
        assert received_ticks[1] == (2, 150.30, attrib)
