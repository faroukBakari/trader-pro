"""Tests for IBSocket - TWS callback handler and state management.

Tests cover:
- State machine management (READY→CONNECTING→CONNECTED→RUNNING→CLOSED)
- Error handling (_log_handled_error: orphan error logging)
- Historical callbacks (historicalData/End routed to wired BarsTracker)
- Symbol/Contract callbacks (symbolSamples, contractDetails routed to wired ContractTracker)
- Wire protocol encoding (to_str, make_fields, decode_data)

Note: All tests test IBSocket in isolation without real TWS connections.
Legacy snapshot/stream management has been moved to dedicated Tracker classes
(QuoteTracker, BarsTracker, ContractTracker).
"""

from decimal import Decimal
from unittest.mock import MagicMock, Mock

import pytest
from ibapi.common import BarData
from ibapi.contract import Contract, ContractDescription, ContractDetails

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


# =============================================================================
# TestIBSocketErrorHandling
# =============================================================================


class TestIBSocketErrorHandling:
    """Test _log_handled_error for orphan error logging."""

    def test_handle_error_orphan_error_logged(self, running_ibsocket: IBSocket) -> None:
        """Test _log_handled_error logs orphan errors (no hooks registered)."""
        # No snapshot or stream registered for this tws_key
        tws_key = "req_99999"

        # Should not raise - just log
        running_ibsocket._log_handled_error(
            category="API",
            detail="ORPHAN_ERROR",
            tws_key=tws_key,
            message="Orphan error message",
        )


# =============================================================================
# TestIBSocketHistoricalCallbacks
# =============================================================================


class TestIBSocketHistoricalCallbacks:
    """Test historicalData and historicalDataEnd route to wired BarsTracker.

    With the dependency inversion pattern, IBSocket receives callbacks from
    BarsTracker via wire_bars_tracker(). These tests verify that TWS callbacks
    are properly routed to the wired BarsTrackerCBWiringInterface.
    """

    def test_historical_data_calls_bars_tracker_update(self) -> None:
        """Test historicalData routes to wired bars_tracker.update()."""
        mock_bars_tracker = MagicMock()
        sock = IBSocket()
        sock.wire_bars_tracker(mock_bars_tracker)
        sock._state = IBSocketState.RUNNING

        bar = BarData()
        bar.date = "20231215"
        bar.open = 150.0
        bar.high = 151.0
        bar.low = 149.0
        bar.close = 150.5

        sock.historicalData(123, bar)

        mock_bars_tracker.update.assert_called_once_with(123, bar)

    def test_historical_data_does_nothing_without_wired_tracker(self) -> None:
        """Test historicalData does nothing when bars_tracker not wired."""
        sock = IBSocket()  # No wire_bars_tracker called
        sock._state = IBSocketState.RUNNING

        bar = BarData()
        bar.date = "20231215"
        bar.open = 150.0

        # Should not raise
        sock.historicalData(123, bar)

    def test_historical_data_end_calls_bars_tracker_flag_complete(self) -> None:
        """Test historicalDataEnd routes to wired bars_tracker.flag_complete()."""
        mock_bars_tracker = MagicMock()
        sock = IBSocket()
        sock.wire_bars_tracker(mock_bars_tracker)
        sock._state = IBSocketState.RUNNING

        sock.historicalDataEnd(123, "20231215", "20231216")

        mock_bars_tracker.flag_complete.assert_called_once_with(
            123, "20231215", "20231216"
        )

    def test_historical_data_update_calls_bars_tracker_update(self) -> None:
        """Test historicalDataUpdate routes to wired bars_tracker.update() for real-time."""
        mock_bars_tracker = MagicMock()
        sock = IBSocket()
        sock.wire_bars_tracker(mock_bars_tracker)
        sock._state = IBSocketState.RUNNING

        bar = BarData()
        bar.date = "20231215 16:00:00"
        bar.open = 150.0
        bar.high = 151.0
        bar.low = 149.5
        bar.close = 150.75
        bar.volume = Decimal("1000")

        sock.historicalDataUpdate(123, bar)

        mock_bars_tracker.update.assert_called_once_with(123, bar)


# =============================================================================
# TestIBSocketErrorCallback
# =============================================================================


class TestIBSocketErrorCallback:
    """Test error() and errorProtoBuf() callbacks."""

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

    def test_system_error_with_tracked_order_routes_to_order(
        self, running_ibsocket: IBSocket
    ) -> None:
        """SYSTEM error with valid reqId matching tracked order → raise_error_for_order."""
        # Wire a mock order tracker that knows about order 42
        mock_order_tracker = MagicMock()
        mock_order_tracker.has_order.return_value = True
        mock_order_tracker.raise_error_for_order.return_value = True
        running_ibsocket._IBSocket__order_tracker = mock_order_tracker  # type: ignore[attr-defined]

        # Send a SYSTEM-nature error with reqId=42 (e.g. an unknown 2xxx code)
        # Use code 2199 which is not in any classified set, falls to SYSTEM via heuristic
        running_ibsocket.error(
            reqId=42,
            errorTime=1702656000000,
            errorCode=2199,
            errorString="Some unknown system warning",
        )

        mock_order_tracker.has_order.assert_called_once_with(42)
        mock_order_tracker.raise_error_for_order.assert_called_once()
        call_args = mock_order_tracker.raise_error_for_order.call_args
        assert call_args[0][0] == 42
        exc = call_args[0][1]
        assert isinstance(exc, ProviderException)
        assert exc.code == "PROVIDER_TWS_2199"

    def test_system_error_without_tracked_order_falls_through(
        self, running_ibsocket: IBSocket
    ) -> None:
        """SYSTEM error with reqId not matching any order → falls to datafeed path."""
        mock_order_tracker = MagicMock()
        mock_order_tracker.has_order.return_value = False
        running_ibsocket._IBSocket__order_tracker = mock_order_tracker  # type: ignore[attr-defined]

        # Should not raise — falls through to datafeed/legacy handling
        running_ibsocket.error(
            reqId=42,
            errorTime=1702656000000,
            errorCode=2199,
            errorString="Some unknown system warning",
        )

        mock_order_tracker.has_order.assert_called_once_with(42)
        mock_order_tracker.raise_error_for_order.assert_not_called()


# =============================================================================
# TestIBSocketManagedAccounts
# =============================================================================


class TestIBSocketManagedAccounts:
    """Test managedAccounts and nextValidId callbacks."""

    def test_managed_accounts_stores_list_before_wiring(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test managedAccounts stores account list during connection setup.

        managedAccounts is called by TWS during connection, before any tracker
        wiring. The accounts list is stored for later retrieval when
        wire_account_tracker is called.
        """
        # Simulate TWS connection callback (before wiring)
        running_ibsocket.managedAccounts("U123,U456,U789")

        # Wire tracker - should return the stored accounts list
        mock_account_tracker = Mock()
        accounts_list = running_ibsocket.wire_account_tracker(mock_account_tracker)

        assert accounts_list == "U123,U456,U789"

    def test_managed_accounts_routes_to_tracker_when_wired(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test managedAccounts routes to tracker if already wired.

        If tracker is wired and managedAccounts is called again (e.g., reconnect),
        it should route accounts to the tracker.
        """
        # First call during connection setup
        running_ibsocket.managedAccounts("U123,U456")

        # Wire the tracker
        mock_account_tracker = Mock()
        running_ibsocket.wire_account_tracker(mock_account_tracker)

        # Subsequent call (e.g., reconnect scenario) routes to tracker
        running_ibsocket.managedAccounts("U123,U456,U789")

        # Verify upsert_account was called for each account
        assert mock_account_tracker.upsert_account.call_count == 3
        mock_account_tracker.upsert_account.assert_any_call("U123")
        mock_account_tracker.upsert_account.assert_any_call("U456")
        mock_account_tracker.upsert_account.assert_any_call("U789")

    def test_next_valid_id_sets_ready_event(self, running_ibsocket: IBSocket) -> None:
        """Test nextValidId sets the ready event and stores order ID."""
        assert not running_ibsocket._ready_event.is_set()

        running_ibsocket.nextValidId(100)

        # Order ID is stored internally for later wiring to OrderTracker
        assert running_ibsocket._IBSocket__next_order_id == 100  # type: ignore[attr-defined]
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
    """Test symbolSamples callback routing to ContractTracker."""

    def test_symbol_samples_routes_to_contract_tracker(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test symbolSamples routes descriptions to wired ContractTracker."""
        # Wire a mock ContractTracker
        mock_tracker = MagicMock()
        running_ibsocket.wire_contract_tracker(mock_tracker)

        reqId = 42

        # Create contract descriptions
        contract1 = Contract()
        contract1.symbol = "AAPL"
        contract1.secType = "STK"
        contract1.exchange = "SMART"
        contract1.primaryExchange = "NASDAQ"

        desc1 = ContractDescription()
        desc1.contract = contract1

        running_ibsocket.symbolSamples(reqId, [desc1])

        # Verify ContractTracker.update_descriptions was called
        mock_tracker.update_descriptions.assert_called_once()
        call_args = mock_tracker.update_descriptions.call_args
        assert call_args[0][0] == reqId  # reqId
        assert len(call_args[0][1]) == 1  # descriptions list
        assert call_args[0][1][0].contract.symbol == "AAPL"

    def test_symbol_samples_noop_without_wired_tracker(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test symbolSamples is no-op when no ContractTracker is wired."""
        # No tracker wired - callback should not error
        desc = ContractDescription()
        desc.contract = Contract()
        desc.contract.symbol = "TEST"

        # Should not raise
        running_ibsocket.symbolSamples(1, [desc])


# =============================================================================
# TestIBSocketContractDetailsCallback
# =============================================================================


class TestIBSocketContractDetailsCallback:
    """Test contractDetails and contractDetailsEnd callbacks routing to ContractTracker."""

    def test_contract_details_routes_to_contract_tracker(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test contractDetails routes to wired ContractTracker.update_details."""
        # Wire a mock ContractTracker
        mock_tracker = MagicMock()
        running_ibsocket.wire_contract_tracker(mock_tracker)

        reqId = 42

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

        # Verify ContractTracker.update_details was called
        mock_tracker.update_details.assert_called_once()
        call_args = mock_tracker.update_details.call_args
        assert call_args[0][0] == reqId
        assert call_args[0][1].longName == "Apple Inc"

    def test_contract_details_end_routes_to_contract_tracker(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test contractDetailsEnd routes to wired ContractTracker.flag_details_complete."""
        # Wire a mock ContractTracker
        mock_tracker = MagicMock()
        running_ibsocket.wire_contract_tracker(mock_tracker)

        reqId = 42
        running_ibsocket.contractDetailsEnd(reqId)

        # Verify ContractTracker.flag_details_complete was called
        mock_tracker.flag_details_complete.assert_called_once_with(reqId)

    def test_contract_details_noop_without_wired_tracker(
        self, running_ibsocket: IBSocket
    ) -> None:
        """Test contractDetails is no-op when no ContractTracker is wired."""
        # No tracker wired - callbacks should not error
        contract = Contract()
        contract.symbol = "AAPL"

        details = ContractDetails()
        details.contract = contract

        # Should not raise
        running_ibsocket.contractDetails(1, details)
        running_ibsocket.contractDetailsEnd(1)
