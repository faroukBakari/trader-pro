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

from trading_api.providers.tws.tws_connection import TWSCallback, TWSClient
from trading_api.providers.tws.tws_models import TWSError


class TestTWSClientInitialization:
    """Test TWSClient initialization."""

    def test_client_stores_config(self) -> None:
        """Test TWSClient stores connection config."""
        with patch("trading_api.providers.tws.tws_connection.IBSocket"):
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
        with patch("trading_api.providers.tws.tws_connection.IBSocket"):
            client = TWSClient("127.0.0.1", 7497, 1)

            assert isinstance(client._cb_wrapper, TWSCallback)

    def test_client_default_timeout(self) -> None:
        """Test TWSClient uses default timeout."""
        with patch("trading_api.providers.tws.tws_connection.IBSocket"):
            client = TWSClient("127.0.0.1", 7497, 1)

            assert client._timeout == 10.0

    def test_client_custom_timeout(self) -> None:
        """Test TWSClient accepts custom timeout."""
        with patch("trading_api.providers.tws.tws_connection.IBSocket"):
            client = TWSClient("127.0.0.1", 7497, 1, timeout=30.0)

            assert client._timeout == 30.0


class TestTWSClientConnection:
    """Test TWSClient connection management (mocked)."""

    def test_ibsocket_property_triggers_connect_when_not_running(self) -> None:
        """Test ibsocket property triggers connection when socket not running."""
        with patch("trading_api.providers.tws.tws_connection.IBSocket") as MockIBSocket:
            # First call returns non-running socket, second returns running socket after connect
            mock_ibsocket_initial = MagicMock()
            mock_ibsocket_initial.running = False

            mock_ibsocket_new = MagicMock()
            mock_ibsocket_new.running = True

            # First instantiation returns initial, second returns new
            MockIBSocket.side_effect = [mock_ibsocket_initial, mock_ibsocket_new]

            client = TWSClient("127.0.0.1", 7497, 1, timeout=0.5)

            # Make connect() set the ready event (simulates successful connection)
            def mock_connect(**kwargs: object) -> MagicMock:
                client._cb_wrapper._ready_event.set()
                return MagicMock()

            mock_ibsocket_new.connect.side_effect = mock_connect

            _ = client.ibsocket

            # Connect should be called on the new socket because running=False on initial
            mock_ibsocket_new.connect.assert_called_once()

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
                # Find the registered future and resolve it via accumulator
                req_id = 1
                if req_id in client._cb_wrapper._futures:
                    client._cb_wrapper._accumulators[req_id].append(desc)
                    client._cb_wrapper._resolve_future(req_id)

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
                # Resolve via accumulator pattern (no items = empty result)
                if 42 in client._cb_wrapper._futures:
                    client._cb_wrapper._resolve_future(42)

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
                # Resolve via accumulator pattern
                if 1 in client._cb_wrapper._futures:
                    client._cb_wrapper._accumulators[1].append(details)
                    client._cb_wrapper._resolve_future(1)

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
                # Resolve via accumulator pattern
                if 1 in client._cb_wrapper._futures:
                    client._cb_wrapper._accumulators[1].extend([bar1, bar2])
                    client._cb_wrapper._resolve_future(1)

            asyncio.create_task(resolve_after_send())

            contract = Contract()
            contract.symbol = "AAPL"
            contract.secType = "STK"

            result = await client.reqHistoricalData(
                contract=contract,
                end_date_time="20231215 16:00:00",
                duration_str="1 D",
                barSize_setting="1 min",
            )

            assert len(result) == 2
            assert result[0].open == 150.0


class TestTWSClientCreateRTTicker:
    """Test create_rt_ticker method for unified real-time data subscriptions."""

    def test_create_rt_ticker_returns_rtmarketdata(self) -> None:
        """Test create_rt_ticker returns RTMarketData instance."""
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

            from trading_api.providers.tws.tws_models import RTMarketData

            ticker = client.create_ticker(contract, "5 mins")

            assert isinstance(ticker, RTMarketData)
            assert ticker.contract == contract
            assert ticker.barSize_setting == "5 mins"
            assert ticker.bar_data_reqId is not None
            assert ticker.mkt_data_reqId is not None

    def test_create_rt_ticker_sends_historical_and_mkt_data_messages(self) -> None:
        """Test create_rt_ticker sends both REQ_HISTORICAL_DATA and REQ_MKT_DATA."""
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

            client.create_ticker(contract, "1 min")

            # Verify both messages were sent
            from ibapi.message import OUT

            assert mock_ibsocket.send_message.call_count == 2
            calls = mock_ibsocket.send_message.call_args_list
            # First call: REQ_HISTORICAL_DATA
            assert calls[0][0][0] == OUT.REQ_HISTORICAL_DATA
            # Second call: REQ_MKT_DATA
            assert calls[1][0][0] == OUT.REQ_MKT_DATA


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


class TestTWSClientCancelRTTicker:
    """Test cancel_rt_ticker method."""

    def test_cancel_rt_ticker_sends_cancel_messages(self) -> None:
        """Test cancel_rt_ticker sends CANCEL_REAL_TIME_BARS and CANCEL_MKT_DATA."""
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

            ticker = client.create_ticker(contract, "5 mins")
            mock_ibsocket.send_message.reset_mock()

            client.remove_ticker(ticker)

            # Verify both cancel messages were sent
            from ibapi.message import OUT

            assert mock_ibsocket.send_message.call_count == 2
            calls = mock_ibsocket.send_message.call_args_list
            # First call: CANCEL_HISTORICAL_DATA (for real-time bars via keepUpToDate)
            assert calls[0][0][0] == OUT.CANCEL_HISTORICAL_DATA
            # Second call: CANCEL_MKT_DATA
            assert calls[1][0][0] == OUT.CANCEL_MKT_DATA

    def test_cancel_rt_ticker_removes_ticker_slot(self) -> None:
        """Test cancel_rt_ticker removes ticker from callback wrapper."""
        with patch("trading_api.providers.tws.tws_connection.IBSocket") as MockIBSocket:
            mock_ibsocket = MagicMock()
            mock_ibsocket.running = True
            mock_ibsocket.next_req_id = 1
            MockIBSocket.return_value = mock_ibsocket

            client = TWSClient("127.0.0.1", 7497, 1)
            client._cb_wrapper._ready_event.set()

            contract = Contract()
            contract.symbol = "AAPL"

            ticker = client.create_ticker(contract, "1 min")
            bar_req_id = ticker.bar_data_reqId
            mkt_req_id = ticker.mkt_data_reqId

            # Verify ticker is registered
            assert bar_req_id in client._cb_wrapper._req_id_to_ticker_map
            assert mkt_req_id in client._cb_wrapper._req_id_to_ticker_map

            client.remove_ticker(ticker)

            # Verify ticker is removed
            assert bar_req_id not in client._cb_wrapper._req_id_to_ticker_map
            assert mkt_req_id not in client._cb_wrapper._req_id_to_ticker_map

    def test_cancel_rt_ticker_resets_ticker_state(self) -> None:
        """Test cancel_rt_ticker resets the RTMarketData instance."""
        with patch("trading_api.providers.tws.tws_connection.IBSocket") as MockIBSocket:
            mock_ibsocket = MagicMock()
            mock_ibsocket.running = True
            mock_ibsocket.next_req_id = 1
            MockIBSocket.return_value = mock_ibsocket

            client = TWSClient("127.0.0.1", 7497, 1)
            client._cb_wrapper._ready_event.set()

            contract = Contract()
            contract.symbol = "AAPL"

            ticker = client.create_ticker(contract, "1 min")
            # Simulate some data
            ticker.bid = 150.0
            ticker.ask = 150.05

            ticker = client.remove_ticker(ticker)

            # Verify ticker is reset - bar_data_reqId should be None
            assert ticker.bid is None
            assert ticker.ask is None
