"""Tests for TWSClient - TWS protocol layer with async bridge.

Tests cover:
- Initialization and configuration
- symbolSamples callback dispatch (search_symbols POC)
- Error handling

Note: Tests use TWSClientHelper directly with mocked IBSocket to avoid
spawning threads that attempt real TWS connections.
"""

import asyncio
import threading
from unittest.mock import Mock

import pytest

from trading_api.providers.tws.tws_connection import TWSClientHelper, TWSError


def create_test_client() -> TWSClientHelper:
    """Create a TWSClientHelper with mocked IBSocket for testing.

    No real socket connection, no background thread trying to connect.
    """
    mock_ibsocket = Mock()
    mock_ibsocket._host = "127.0.0.1"
    mock_ibsocket._port = 7497
    mock_ibsocket._client_id = 1

    # Create a stopped thread (won't run)
    stopped_event = threading.Event()
    stopped_event.clear()  # Thread loop won't run

    # Dummy thread that does nothing
    dummy_thread = threading.Thread(target=lambda: None, daemon=True)

    return TWSClientHelper(
        ibsocket=mock_ibsocket,
        client_thread=dummy_thread,
        running=stopped_event,
        loop=asyncio.get_event_loop(),
    )


class TestTWSClientHelperInitialization:
    """Test TWSClientHelper initialization."""

    def test_client_initialization(self) -> None:
        """Test TWSClientHelper initializes with mocked IBSocket."""
        client = create_test_client()

        assert client._ibsocket._host == "127.0.0.1"
        assert client._ibsocket._port == 7497
        assert client._ibsocket._client_id == 1
        assert client._futures == {}
        assert client._next_req_id == 0

    def test_next_req_id_increments(self) -> None:
        """Test request ID generation increments."""
        client = create_test_client()

        id1 = client.next_req_id
        id2 = client.next_req_id
        id3 = client.next_req_id

        assert id1 == 0
        assert id2 == 1
        assert id3 == 2

    def test_curr_req_id_does_not_increment(self) -> None:
        """Test curr_req_id returns current ID without incrementing."""
        client = create_test_client()

        # Get current ID multiple times
        curr1 = client.curr_req_id
        curr2 = client.curr_req_id

        assert curr1 == curr2 == 0

        # After next_req_id, curr_req_id should reflect the new value
        _ = client.next_req_id
        assert client.curr_req_id == 1


class TestSymbolSamplesCallback:
    """Test symbolSamples callback - core of search_symbols POC."""

    @pytest.mark.asyncio
    async def test_symbol_samples_resolves_future(self) -> None:
        """Test symbolSamples callback resolves the pending future."""
        from ibapi.contract import Contract, ContractDescription

        client = create_test_client()
        # Update loop to current running loop
        client._loop = asyncio.get_running_loop()

        # Create a future and register it
        loop = asyncio.get_running_loop()
        future: asyncio.Future[list[ContractDescription]] = loop.create_future()
        req_id = 1
        client._futures[req_id] = future

        # Create proper ContractDescription objects
        contract1 = Contract()
        contract1.symbol = "AAPL"
        contract1.exchange = "NASDAQ"
        desc1 = ContractDescription()
        desc1.contract = contract1

        contract2 = Contract()
        contract2.symbol = "AAPL"
        contract2.exchange = "NYSE"
        desc2 = ContractDescription()
        desc2.contract = contract2

        descriptions = [desc1, desc2]

        # Call the callback (simulates TWS response)
        client.symbolSamples(req_id, descriptions)

        # Future should be resolved
        result = await future
        assert result == descriptions
        assert req_id not in client._futures  # Cleaned up


class TestErrorHandling:
    """Test error callback handling."""

    def test_tws_error_dataclass(self) -> None:
        """Test TWSError dataclass structure."""
        error = TWSError(
            reqId=1,
            errorCode=200,
            errorString="No security definition",
            errorTime=1234567890,
        )

        assert error.reqId == 1
        assert error.errorCode == 200
        assert error.errorString == "No security definition"
        assert "TWS error 200" in str(error)

    @pytest.mark.asyncio
    async def test_error_rejects_future(self) -> None:
        """Test error callback rejects the pending future."""
        client = create_test_client()
        # Update loop to current running loop
        client._loop = asyncio.get_running_loop()

        # Create a future and register it
        loop = asyncio.get_running_loop()
        future: asyncio.Future[list[object]] = loop.create_future()
        req_id = 1
        client._futures[req_id] = future

        # Simulate TWS error callback
        client.error(req_id, 1234567890, 200, "No security definition")

        # Future should be rejected with TWSError
        with pytest.raises(TWSError) as exc_info:
            await future

        assert exc_info.value.errorCode == 200
        assert "No security definition" in exc_info.value.errorString

    def test_general_error_no_future(self) -> None:
        """Test general error (reqId=-1) doesn't crash when no future."""
        client = create_test_client()

        # Should not raise - general errors have reqId=-1
        client.error(-1, 1234567890, 502, "Couldn't connect to TWS")
