"""Tests for TWSClient - TWS protocol layer with async bridge.

Tests cover:
- Initialization and configuration
- symbolSamples callback dispatch (search_symbols)
- contractDetails callback dispatch (get_symbol_info)
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
        assert client._accumulators == {}
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
    """Test symbolSamples callback - core of search_symbols."""

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


class TestContractDetailsCallback:
    """Test contractDetails callback - streaming accumulation pattern."""

    @pytest.mark.asyncio
    async def test_contract_details_accumulates_results(self) -> None:
        """Test contractDetails accumulates multiple callbacks before end signal."""
        from ibapi.contract import Contract, ContractDetails

        client = create_test_client()
        client._loop = asyncio.get_running_loop()

        # Create a future and register it
        loop = asyncio.get_running_loop()
        future: asyncio.Future[list[ContractDetails]] = loop.create_future()
        req_id = 1
        client._futures[req_id] = future
        client._accumulators[req_id] = []

        # Create ContractDetails objects
        contract1 = Contract()
        contract1.symbol = "AAPL"
        contract1.exchange = "NASDAQ"
        details1 = ContractDetails()
        details1.contract = contract1
        details1.longName = "Apple Inc"

        contract2 = Contract()
        contract2.symbol = "AAPL"
        contract2.exchange = "NYSE"
        details2 = ContractDetails()
        details2.contract = contract2
        details2.longName = "Apple Inc"

        # Simulate TWS sending multiple contractDetails callbacks
        client.contractDetails(req_id, details1)
        client.contractDetails(req_id, details2)

        # Check accumulator has both results
        assert len(client._accumulators[req_id]) == 2

        # End signal resolves the future
        client.contractDetailsEnd(req_id)

        # Future should be resolved with accumulated results
        result = await future
        assert len(result) == 2
        assert result[0].longName == "Apple Inc"
        assert req_id not in client._futures  # Cleaned up
        assert req_id not in client._accumulators  # Cleaned up

    @pytest.mark.asyncio
    async def test_contract_details_single_result(self) -> None:
        """Test contractDetails works with single result (common case)."""
        from ibapi.contract import Contract, ContractDetails

        client = create_test_client()
        client._loop = asyncio.get_running_loop()

        loop = asyncio.get_running_loop()
        future: asyncio.Future[list[ContractDetails]] = loop.create_future()
        req_id = 1
        client._futures[req_id] = future
        client._accumulators[req_id] = []

        # Single contract details
        contract = Contract()
        contract.symbol = "MSFT"
        contract.exchange = "SMART"
        details = ContractDetails()
        details.contract = contract
        details.longName = "Microsoft Corporation"
        details.minTick = 0.01

        client.contractDetails(req_id, details)
        client.contractDetailsEnd(req_id)

        result = await future
        assert len(result) == 1
        assert result[0].contract.symbol == "MSFT"
        assert result[0].minTick == 0.01

    @pytest.mark.asyncio
    async def test_contract_details_empty_result(self) -> None:
        """Test contractDetailsEnd with no results (symbol not found)."""
        client = create_test_client()
        client._loop = asyncio.get_running_loop()

        loop = asyncio.get_running_loop()
        future: asyncio.Future[list[object]] = loop.create_future()
        req_id = 1
        client._futures[req_id] = future
        client._accumulators[req_id] = []

        # End signal with no contractDetails calls
        client.contractDetailsEnd(req_id)

        result = await future
        assert result == []


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
