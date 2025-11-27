"""Tests for TWSClient - AsyncIO bridge facade.

Tests cover:
- Client initialization
- Lazy connection via ibsocket property
- Async request methods (with mocked IBSocket)
- Request ID generation
- Timeout handling

Note: All tests mock IBSocket to avoid real TWS connections.
"""

import asyncio
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from ibapi.common import BarData
from ibapi.contract import Contract, ContractDescription, ContractDetails

from trading_api.providers.tws.tws_connection import TWSCallback, TWSClient, TWSError


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

    def test_client_creates_callback_wrapper(self) -> None:
        """Test TWSClient creates TWSCallback instance."""
        client = TWSClient("127.0.0.1", 7497, 1)

        assert isinstance(client._cb_wrapper, TWSCallback)

    def test_client_default_timeout(self) -> None:
        """Test TWSClient uses default timeout."""
        client = TWSClient("127.0.0.1", 7497, 1)

        assert client._timeout == 10.0

    def test_client_custom_timeout(self) -> None:
        """Test TWSClient accepts custom timeout."""
        client = TWSClient("127.0.0.1", 7497, 1, timeout=30.0)

        assert client._timeout == 30.0


class TestTWSClientConnection:
    """Test TWSClient connection management (mocked)."""

    def test_ibsocket_property_triggers_connect_when_not_running(self) -> None:
        """Test ibsocket property triggers connection when socket not running."""
        client = TWSClient("127.0.0.1", 7497, 1, timeout=0.5)

        # Replace the internal IBSocket with a mock
        mock_ibsocket = MagicMock()
        mock_ibsocket.running = False
        mock_ibsocket.ready = True  # Ready = socket unused, can connect

        # Make connect() set the ready event (simulates successful connection)
        def mock_connect(**kwargs: object) -> MagicMock:
            client._cb_wrapper._ready_event.set()
            return MagicMock()

        mock_ibsocket.connect.side_effect = mock_connect

        # Inject mock (bypass private attribute via name mangling)
        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        _ = client.ibsocket

        # Connect should be called because running=False
        mock_ibsocket.connect.assert_called_once()

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
        with patch("trading_api.providers.tws.tws_connection.IBSocket") as MockIBSocket:
            mock_ibsocket = MagicMock()
            mock_ibsocket.running = True
            mock_ibsocket.next_req_id = 1
            MockIBSocket.return_value = mock_ibsocket

            client = TWSClient("127.0.0.1", 7497, 1, timeout=5.0)
            client._cb_wrapper._ready_event.set()
            # Set the loop
            client._cb_wrapper._loop = asyncio.get_running_loop()

            # Create test response
            contract = Contract()
            contract.symbol = "AAPL"
            contract.exchange = "SMART"
            desc = ContractDescription()
            desc.contract = contract

            # Schedule callback resolution
            async def resolve_after_send() -> None:
                await asyncio.sleep(0.01)
                # Find the registered future and resolve it
                req_id = 1
                if req_id in client._cb_wrapper._futures:
                    client._cb_wrapper._resolve_future(req_id, [desc])

            asyncio.create_task(resolve_after_send())

            result = await client.reqMatchingSymbols("AAPL")

            assert len(result) == 1
            assert result[0].contract.symbol == "AAPL"
            mock_ibsocket.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_req_matching_symbols_sends_correct_message(self) -> None:
        """Test reqMatchingSymbols sends correct message format."""
        with patch("trading_api.providers.tws.tws_connection.IBSocket") as MockIBSocket:
            mock_ibsocket = MagicMock()
            mock_ibsocket.running = True
            mock_ibsocket.next_req_id = 42
            MockIBSocket.return_value = mock_ibsocket

            client = TWSClient("127.0.0.1", 7497, 1)
            client._cb_wrapper._ready_event.set()
            client._cb_wrapper._loop = asyncio.get_running_loop()

            # Schedule callback
            async def resolve_after_send() -> None:
                await asyncio.sleep(0.01)
                client._cb_wrapper._resolve_future(42, [])

            asyncio.create_task(resolve_after_send())

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
        with patch("trading_api.providers.tws.tws_connection.IBSocket") as MockIBSocket:
            mock_ibsocket = MagicMock()
            mock_ibsocket.running = True
            mock_ibsocket.next_req_id = 1
            MockIBSocket.return_value = mock_ibsocket

            client = TWSClient("127.0.0.1", 7497, 1)
            client._cb_wrapper._ready_event.set()
            client._cb_wrapper._loop = asyncio.get_running_loop()

            # Create test response
            contract = Contract()
            contract.symbol = "AAPL"
            details = ContractDetails()
            details.contract = contract
            details.longName = "Apple Inc"

            async def resolve_after_send() -> None:
                await asyncio.sleep(0.01)
                client._cb_wrapper._resolve_future(1, [details])

            asyncio.create_task(resolve_after_send())

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
        with patch("trading_api.providers.tws.tws_connection.IBSocket") as MockIBSocket:
            mock_ibsocket = MagicMock()
            mock_ibsocket.running = True
            mock_ibsocket.next_req_id = 1
            MockIBSocket.return_value = mock_ibsocket

            client = TWSClient("127.0.0.1", 7497, 1)
            client._cb_wrapper._ready_event.set()
            client._cb_wrapper._loop = asyncio.get_running_loop()

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

            async def resolve_after_send() -> None:
                await asyncio.sleep(0.01)
                client._cb_wrapper._resolve_future(1, [bar1, bar2])

            asyncio.create_task(resolve_after_send())

            contract = Contract()
            contract.symbol = "AAPL"
            contract.secType = "STK"

            result = await client.reqHistoricalData(
                contract=contract,
                end_date_time="20231215 16:00:00",
                duration_str="1 D",
                bar_size_setting="1 min",
            )

            assert len(result) == 2
            assert result[0].open == 150.0


class TestTWSClientReqMktDataSnapshot:
    """Test reqMktDataSnapshot async method."""

    @pytest.mark.asyncio
    async def test_req_mkt_data_snapshot_returns_ticks(self) -> None:
        """Test reqMktDataSnapshot returns tick dictionary."""
        with patch("trading_api.providers.tws.tws_connection.IBSocket") as MockIBSocket:
            mock_ibsocket = MagicMock()
            mock_ibsocket.running = True
            mock_ibsocket.next_req_id = 1
            MockIBSocket.return_value = mock_ibsocket

            client = TWSClient("127.0.0.1", 7497, 1)
            client._cb_wrapper._ready_event.set()
            client._cb_wrapper._loop = asyncio.get_running_loop()

            # Create test tick data
            ticks = {
                "BID": 150.25,
                "ASK": 150.30,
                "LAST": 150.28,
                "VOLUME": 1000000,
            }

            async def resolve_after_send() -> None:
                await asyncio.sleep(0.01)
                client._cb_wrapper._resolve_future(1, ticks)

            asyncio.create_task(resolve_after_send())

            contract = Contract()
            contract.symbol = "AAPL"
            contract.secType = "STK"

            result = await client.reqMktDataSnapshot(contract)

            assert result["BID"] == 150.25
            assert result["ASK"] == 150.30
            assert result["VOLUME"] == 1000000


class TestTWSClientNextReqId:
    """Test next_req_id property."""

    def test_next_req_id_increments(self) -> None:
        """Test next_req_id increments on each access."""
        with patch("trading_api.providers.tws.tws_connection.IBSocket") as MockIBSocket:
            mock_ibsocket = MagicMock()
            mock_ibsocket.running = True
            # Use PropertyMock for next_req_id
            type(mock_ibsocket).next_req_id = PropertyMock(side_effect=[1, 2, 3])
            MockIBSocket.return_value = mock_ibsocket

            client = TWSClient("127.0.0.1", 7497, 1)
            client._cb_wrapper._ready_event.set()

            id1 = client.next_req_id
            id2 = client.next_req_id
            id3 = client.next_req_id

            assert id1 == 1
            assert id2 == 2
            assert id3 == 3


class TestTWSClientErrorHandling:
    """Test error handling in async methods."""

    @pytest.mark.asyncio
    async def test_error_during_request_raises_tws_error(self) -> None:
        """Test TWSError is raised when TWS returns error."""
        with patch("trading_api.providers.tws.tws_connection.IBSocket") as MockIBSocket:
            mock_ibsocket = MagicMock()
            mock_ibsocket.running = True
            mock_ibsocket.next_req_id = 1
            MockIBSocket.return_value = mock_ibsocket

            client = TWSClient("127.0.0.1", 7497, 1)
            client._cb_wrapper._ready_event.set()
            client._cb_wrapper._loop = asyncio.get_running_loop()

            async def reject_after_send() -> None:
                await asyncio.sleep(0.01)
                error = TWSError(
                    reqId=1,
                    errorCode=200,
                    errorString="No security definition",
                    errorTime=1234567890,
                )
                client._cb_wrapper._reject_future(1, error)

            asyncio.create_task(reject_after_send())

            with pytest.raises(TWSError) as exc_info:
                await client.reqMatchingSymbols("INVALID")

            assert exc_info.value.errorCode == 200

    @pytest.mark.asyncio
    async def test_timeout_raises_timeout_error(self) -> None:
        """Test TimeoutError is raised when request times out."""
        with patch("trading_api.providers.tws.tws_connection.IBSocket") as MockIBSocket:
            mock_ibsocket = MagicMock()
            mock_ibsocket.running = True
            mock_ibsocket.next_req_id = 1
            MockIBSocket.return_value = mock_ibsocket

            # Very short timeout
            client = TWSClient("127.0.0.1", 7497, 1, timeout=0.05)
            client._cb_wrapper._ready_event.set()
            client._cb_wrapper._loop = asyncio.get_running_loop()

            # Don't resolve the future - let it timeout
            with pytest.raises(asyncio.TimeoutError):
                await client.reqMatchingSymbols("AAPL")


class TestTWSClientRealtimeBarSubscription:
    """Test real-time bar subscription methods."""

    def test_subscribe_realtime_bars_returns_queue(self) -> None:
        """Test subscribe_realtime_bars returns reqId and queue."""
        with patch("trading_api.providers.tws.tws_connection.IBSocket") as MockIBSocket:
            mock_ibsocket = MagicMock()
            mock_ibsocket.running = True
            mock_ibsocket.next_req_id = 1
            MockIBSocket.return_value = mock_ibsocket

            client = TWSClient("127.0.0.1", 7497, 1)
            client._cb_wrapper._ready_event.set()

            contract = Contract()
            contract.symbol = "AAPL"
            contract.secType = "STK"
            contract.exchange = "SMART"
            contract.currency = "USD"

            req_id, queue = client.subscribe_realtime_bars(contract)

            assert req_id == 1
            assert isinstance(queue, asyncio.Queue)
            # Queue should be registered in _sub_queues
            assert req_id in client._cb_wrapper._sub_queues
            assert client._cb_wrapper._sub_queues[req_id] is queue

    def test_subscribe_realtime_bars_sends_correct_message(self) -> None:
        """Test subscribe_realtime_bars sends correct TWS message."""
        with patch("trading_api.providers.tws.tws_connection.IBSocket") as MockIBSocket:
            mock_ibsocket = MagicMock()
            mock_ibsocket.running = True
            mock_ibsocket.next_req_id = 1
            MockIBSocket.return_value = mock_ibsocket

            client = TWSClient("127.0.0.1", 7497, 1)
            client._cb_wrapper._ready_event.set()

            contract = Contract()
            contract.symbol = "AAPL"
            contract.secType = "STK"
            contract.exchange = "SMART"
            contract.currency = "USD"

            client.subscribe_realtime_bars(
                contract, bar_size=5, what_to_show="TRADES", use_rth=False
            )

            # Verify send_message was called with REQ_REAL_TIME_BARS
            from ibapi.message import OUT

            mock_ibsocket.send_message.assert_called_once()
            call_args = mock_ibsocket.send_message.call_args
            assert call_args[0][0] == OUT.REQ_REAL_TIME_BARS

    def test_cancel_realtime_bars_removes_queue(self) -> None:
        """Test cancel_realtime_bars removes queue from registry."""
        with patch("trading_api.providers.tws.tws_connection.IBSocket") as MockIBSocket:
            mock_ibsocket = MagicMock()
            mock_ibsocket.running = True
            mock_ibsocket.next_req_id = 1
            MockIBSocket.return_value = mock_ibsocket

            client = TWSClient("127.0.0.1", 7497, 1)
            client._cb_wrapper._ready_event.set()

            contract = Contract()
            contract.symbol = "AAPL"

            req_id, queue = client.subscribe_realtime_bars(contract)
            assert req_id in client._cb_wrapper._sub_queues

            client.cancel_realtime_bars(req_id)

            # Queue should be removed
            assert req_id not in client._cb_wrapper._sub_queues

    def test_cancel_realtime_bars_sends_cancel_message(self) -> None:
        """Test cancel_realtime_bars sends CANCEL_REAL_TIME_BARS message."""
        with patch("trading_api.providers.tws.tws_connection.IBSocket") as MockIBSocket:
            mock_ibsocket = MagicMock()
            mock_ibsocket.running = True
            mock_ibsocket.next_req_id = 1
            MockIBSocket.return_value = mock_ibsocket

            client = TWSClient("127.0.0.1", 7497, 1)
            client._cb_wrapper._ready_event.set()

            contract = Contract()
            contract.symbol = "AAPL"

            req_id, _ = client.subscribe_realtime_bars(contract)
            mock_ibsocket.send_message.reset_mock()

            client.cancel_realtime_bars(req_id)

            from ibapi.message import OUT

            mock_ibsocket.send_message.assert_called_once()
            call_args = mock_ibsocket.send_message.call_args
            assert call_args[0][0] == OUT.CANCEL_REAL_TIME_BARS
            assert call_args[0][1] == [1, req_id]  # VERSION=1, reqId
