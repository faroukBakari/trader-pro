"""Tests for TWSClient - AsyncIO bridge facade.

Tests cover:
- Client initialization
- Lazy connection via ibsocket property
- Async request methods (with mocked IBSocket)
- Request ID generation
- Stream management (reqBarDataStream, reqMktDataStream)
- Cancellation methods

Note: All tests mock IBSocket to avoid real TWS connections.
"""

import asyncio
from typing import Any, Awaitable
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from ibapi.common import BarData
from ibapi.contract import Contract, ContractDescription, ContractDetails

from trading_api.providers.tws.tws_connection import TWSClient


class TestTWSClientInitialization:
    """Test TWSClient initialization."""

    def test_client_stores_config(self) -> None:
        """Test TWSClient stores connection config."""
        client = TWSClient(
            host="192.168.1.1",
            port=4002,
            client_id=5,
        )

        assert client._host == "192.168.1.1"
        assert client._port == 4002
        assert client._client_id == 5

    def test_client_default_timeout(self) -> None:
        """Test TWSClient uses default timeout."""
        client = TWSClient("127.0.0.1", 7497, 1)

        assert client._timeout == 10.0

    def test_client_custom_timeout(self) -> None:
        """Test TWSClient accepts custom timeout."""
        client = TWSClient("127.0.0.1", 7497, 1, timeout=30.0)

        assert client._timeout == 30.0

    def test_client_creates_ibsocket(self) -> None:
        """Test TWSClient creates IBSocket instance."""
        client = TWSClient("127.0.0.1", 7497, 1)

        # Private attribute should exist (IBSocket is created lazily but attribute exists)
        assert hasattr(client, "_TWSClient__ibsocket")


class TestTWSClientConnection:
    """Test TWSClient connection management (mocked)."""

    def test_ibsocket_property_triggers_connect_when_not_running(self) -> None:
        """Test ibsocket property triggers connection when socket not running."""
        client = TWSClient("127.0.0.1", 7497, 1, timeout=0.5)

        # Mock the IBSocket to simulate connection
        with patch.object(client, "_TWSClient__ibsocket", create=True) as mock_ibsocket:
            mock_ibsocket.running = False

            # Create a new mock for the replacement socket
            new_mock_ibsocket = MagicMock()
            new_mock_ibsocket.running = True
            new_mock_ibsocket._ready_event = MagicMock()
            new_mock_ibsocket._ready_event.wait.return_value = True

            with patch(
                "trading_api.providers.tws.tws_connection.IBSocket",
                return_value=new_mock_ibsocket,
            ):
                _ = client.ibsocket

            # Connect should be called on the new socket
            new_mock_ibsocket.connect.assert_called_once()

    def test_ibsocket_property_reuses_running_connection(self) -> None:
        """Test ibsocket property reuses existing running connection."""
        client = TWSClient("127.0.0.1", 7497, 1)

        # Replace with mock that is already running
        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True

        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        # Access twice
        sock1 = client.ibsocket
        sock2 = client.ibsocket

        # Should not call connect (already running)
        mock_ibsocket.connect.assert_not_called()
        assert sock1 is sock2


class TestTWSClientReqMatchingSymbols:
    """Test reqMatchingSymbols async method."""

    @pytest.mark.asyncio
    async def test_req_matching_symbols_returns_descriptions(self) -> None:
        """Test reqMatchingSymbols returns ContractDescription list."""
        client = TWSClient("127.0.0.1", 7497, 1, timeout=5.0)

        # Create mock ibsocket
        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True
        mock_ibsocket.next_req_id = 1

        # Create test response
        contract = Contract()
        contract.symbol = "AAPL"
        contract.exchange = "SMART"
        desc = ContractDescription()
        desc.contract = contract

        # Setup future resolution
        loop = asyncio.get_running_loop()
        future: asyncio.Future[list[ContractDescription]] = loop.create_future()

        def create_future_side_effect(
            reqId: int, *, capability: str, timeout: float | None = None
        ) -> Awaitable[Any]:
            # Schedule resolution
            async def resolve() -> None:
                await asyncio.sleep(0.01)
                future.set_result([desc])

            asyncio.create_task(resolve())
            return future

        mock_ibsocket.create_future = create_future_side_effect
        mock_ibsocket.send_message = MagicMock()

        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        result = await client.reqMatchingSymbols("AAPL")

        assert len(result) == 1
        assert result[0].contract.symbol == "AAPL"
        mock_ibsocket.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_req_matching_symbols_sends_correct_message(self) -> None:
        """Test reqMatchingSymbols sends correct message format."""
        client = TWSClient("127.0.0.1", 7497, 1)

        # Create mock ibsocket
        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True
        mock_ibsocket.next_req_id = 42

        # Setup future resolution
        loop = asyncio.get_running_loop()
        future: asyncio.Future[list[Any]] = loop.create_future()

        def create_future_side_effect(
            reqId: int, *, capability: str, timeout: float | None = None
        ) -> Awaitable[Any]:
            async def resolve() -> None:
                await asyncio.sleep(0.01)
                future.set_result([])

            asyncio.create_task(resolve())
            return future

        mock_ibsocket.create_future = create_future_side_effect
        mock_ibsocket.send_message = MagicMock()

        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        await client.reqMatchingSymbols("MSFT")

        # Verify message format
        call_args = mock_ibsocket.send_message.call_args
        assert call_args is not None
        # First arg is msgId (REQ_MATCHING_SYMBOLS), second is values
        values = call_args[0][1]
        assert 42 in values  # reqId
        assert "MSFT" in values  # pattern


class TestTWSClientReqContractDetails:
    """Test reqContractDetails async method."""

    @pytest.mark.asyncio
    async def test_req_contract_details_returns_list(self) -> None:
        """Test reqContractDetails returns ContractDetails list."""
        client = TWSClient("127.0.0.1", 7497, 1)

        # Create mock ibsocket
        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True
        mock_ibsocket.next_req_id = 1

        # Create test response
        contract = Contract()
        contract.symbol = "AAPL"
        details = ContractDetails()
        details.contract = contract
        details.longName = "Apple Inc"

        # Setup future resolution
        loop = asyncio.get_running_loop()
        future: asyncio.Future[list[ContractDetails]] = loop.create_future()

        def create_future_side_effect(
            reqId: int, *, capability: str, timeout: float | None = None
        ) -> Awaitable[Any]:
            async def resolve() -> None:
                await asyncio.sleep(0.01)
                future.set_result([details])

            asyncio.create_task(resolve())
            return future

        mock_ibsocket.create_future = create_future_side_effect
        mock_ibsocket.send_message = MagicMock()

        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        query_contract = Contract()
        query_contract.symbol = "AAPL"
        query_contract.secType = "STK"
        query_contract.exchange = "SMART"

        result = await client.reqContractDetails(query_contract)

        assert len(result) == 1
        assert result[0].longName == "Apple Inc"


class TestTWSClientReqHistoricalData:
    """Test reqHistoricalData async method."""

    @pytest.mark.asyncio
    async def test_req_historical_data_returns_bars(self) -> None:
        """Test reqHistoricalData returns BarData list."""
        client = TWSClient("127.0.0.1", 7497, 1)

        # Create mock ibsocket
        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True
        mock_ibsocket.next_req_id = 1

        # Create test bars
        bar1 = BarData()
        bar1.date = "20231215 09:30:00"
        bar1.open = 150.0
        bar1.high = 151.0
        bar1.low = 149.5
        bar1.close = 150.5

        bar2 = BarData()
        bar2.date = "20231215 09:31:00"
        bar2.open = 150.5
        bar2.close = 151.0

        # Setup future resolution
        loop = asyncio.get_running_loop()
        future: asyncio.Future[list[BarData]] = loop.create_future()

        def create_future_side_effect(
            reqId: int, *, capability: str, timeout: float | None = None
        ) -> Awaitable[Any]:
            async def resolve() -> None:
                await asyncio.sleep(0.01)
                future.set_result([bar1, bar2])

            asyncio.create_task(resolve())
            return future

        mock_ibsocket.create_future = create_future_side_effect
        mock_ibsocket.send_message = MagicMock()

        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        contract = Contract()
        contract.symbol = "AAPL"
        contract.secType = "STK"

        result = await client.reqHistoricalData(
            contract=contract,
            end_date_time="20231215 16:00:00",
            duration_str="1 D",
            bar_size="1 min",
        )

        assert len(result) == 2
        assert result[0].open == 150.0


class TestTWSClientStreamMethods:
    """Test stream subscription methods."""

    def test_req_bar_data_stream_registers_callback(self) -> None:
        """Test reqBarDataStream registers stream with callback."""
        client = TWSClient("127.0.0.1", 7497, 1)

        # Create mock ibsocket
        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True
        mock_ibsocket.next_req_id = 1
        mock_ibsocket.register_stream = MagicMock()
        mock_ibsocket.send_message = MagicMock()

        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        contract = Contract()
        contract.symbol = "AAPL"
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"

        async def callback(data: dict[str, Any], fields: list[str]) -> None:
            pass

        stream_key = client.reqBarDataStream(contract, "5 mins", callback)

        assert isinstance(stream_key, str)
        mock_ibsocket.register_stream.assert_called_once()
        mock_ibsocket.send_message.assert_called_once()

    def test_req_mkt_data_stream_registers_callback(self) -> None:
        """Test reqMktDataStream registers stream with callback."""
        client = TWSClient("127.0.0.1", 7497, 1)

        # Create mock ibsocket
        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True
        mock_ibsocket.next_req_id = 1
        mock_ibsocket.register_stream = MagicMock()
        mock_ibsocket.send_message = MagicMock()

        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        contract = Contract()
        contract.symbol = "AAPL"
        contract.secType = "STK"

        async def callback(data: dict[str, Any], fields: list[str]) -> None:
            pass

        stream_key = client.reqMktDataStream(contract, callback)

        assert isinstance(stream_key, str)
        mock_ibsocket.register_stream.assert_called_once()
        mock_ibsocket.send_message.assert_called_once()

    def test_cancel_bar_data_stream_sends_cancel(self) -> None:
        """Test cancelBarDataStream sends cancel message."""
        client = TWSClient("127.0.0.1", 7497, 1)

        # Create mock ibsocket
        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True
        mock_ibsocket.next_req_id = 1
        mock_ibsocket.register_stream = MagicMock()
        mock_ibsocket.unregister_stream = MagicMock()
        mock_ibsocket.send_message = MagicMock()

        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        contract = Contract()
        contract.symbol = "AAPL"
        contract.secType = "STK"

        async def callback(data: dict[str, Any], fields: list[str]) -> None:
            pass

        # First create a stream
        stream_key = client.reqBarDataStream(contract, "5 mins", callback)

        # Reset mock to check cancel call
        mock_ibsocket.send_message.reset_mock()

        # Cancel the stream
        client.cancelBarDataStream(stream_key)

        mock_ibsocket.send_message.assert_called_once()
        mock_ibsocket.unregister_stream.assert_called_once()

    def test_cancel_mkt_data_stream_sends_cancel(self) -> None:
        """Test cancelMktDataStream sends cancel message."""
        client = TWSClient("127.0.0.1", 7497, 1)

        # Create mock ibsocket
        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True
        mock_ibsocket.next_req_id = 1
        mock_ibsocket.register_stream = MagicMock()
        mock_ibsocket.unregister_stream = MagicMock()
        mock_ibsocket.send_message = MagicMock()

        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        contract = Contract()
        contract.symbol = "AAPL"
        contract.secType = "STK"

        async def callback(data: dict[str, Any], fields: list[str]) -> None:
            pass

        # First create a stream
        stream_key = client.reqMktDataStream(contract, callback)

        # Reset mock to check cancel call
        mock_ibsocket.send_message.reset_mock()

        # Cancel the stream
        client.cancelMktDataStream(stream_key)

        mock_ibsocket.send_message.assert_called_once()
        mock_ibsocket.unregister_stream.assert_called_once()


class TestTWSClientNextReqId:
    """Test next_req_id property."""

    def test_next_req_id_delegates_to_ibsocket(self) -> None:
        """Test next_req_id delegates to ibsocket."""
        client = TWSClient("127.0.0.1", 7497, 1)

        # Create mock ibsocket
        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True
        type(mock_ibsocket).next_req_id = PropertyMock(side_effect=[1, 2, 3])

        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        id1 = client.next_req_id
        id2 = client.next_req_id
        id3 = client.next_req_id

        assert id1 == 1
        assert id2 == 2
        assert id3 == 3


class TestTWSClientErrorHandling:
    """Test error handling in async methods."""

    @pytest.mark.asyncio
    async def test_timeout_raises_timeout_error(self) -> None:
        """Test TimeoutError is raised when request times out."""
        client = TWSClient("127.0.0.1", 7497, 1, timeout=0.05)

        # Create mock ibsocket
        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True
        mock_ibsocket.next_req_id = 1

        # Setup future that never resolves
        def create_future_side_effect(
            reqId: int, *, capability: str, timeout: float | None = None
        ) -> Awaitable[Any]:
            loop = asyncio.get_running_loop()
            future: asyncio.Future[Any] = loop.create_future()
            # Return future wrapped with timeout
            return asyncio.wait_for(future, timeout)

        mock_ibsocket.create_future = create_future_side_effect
        mock_ibsocket.send_message = MagicMock()

        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        # Don't resolve the future - let it timeout
        with pytest.raises(asyncio.TimeoutError):
            await client.reqMatchingSymbols("AAPL")


class TestTWSClientShutdown:
    """Test shutdown method."""

    def test_shutdown_disconnects_ibsocket(self) -> None:
        """Test shutdown disconnects the IBSocket."""
        client = TWSClient("127.0.0.1", 7497, 1)

        # Create mock ibsocket
        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True
        mock_ibsocket.disconnect = MagicMock()

        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        client.shutdown()

        mock_ibsocket.disconnect.assert_called_once()
