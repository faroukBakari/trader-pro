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
from unittest.mock import MagicMock, patch

import pytest
from ibapi.contract import Contract, ContractDescription, ContractDetails

from trading_api.providers.tws.cached_contract import CachedContract
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
        """Test reqMatchingSymbols returns CachedContract list."""
        client = TWSClient("127.0.0.1", 7497, 1, timeout=5.0)

        # Create mock ibsocket with contract_tracker
        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True
        mock_ibsocket.get_cached_data.return_value = None  # No cache hit

        # Create test contract
        contract = Contract()
        contract.symbol = "AAPL"
        contract.exchange = "SMART"
        contract.secType = "STK"
        contract.conId = 265598  # Valid conId required by filter
        desc = ContractDescription()
        desc.contract = contract

        # Create CachedContract for tracker response
        cached_contract = CachedContract.from_contract_description(desc)

        # Mock contract_tracker - first call returns empty (cache miss), second returns data
        call_count = [0]

        def get_by_symbol_prefix_side_effect(pattern: str) -> list[CachedContract]:
            call_count[0] += 1
            if call_count[0] == 1:
                return []  # First call: cache miss
            return [cached_contract]  # Second call: after API fetch

        mock_ibsocket.contract_tracker.get_by_symbol_prefix.side_effect = (
            get_by_symbol_prefix_side_effect
        )

        # Setup create_snapshot mock that returns (reqId, awaitable)
        def create_snapshot_side_effect(
            business_key: str, *, timeout: float | None = 5
        ) -> tuple[int | None, Awaitable[Any]]:
            loop = asyncio.get_running_loop()
            future: asyncio.Future[list[dict[str, Any]]] = loop.create_future()

            async def resolve() -> None:
                await asyncio.sleep(0.01)
                future.set_result([{"contractDescriptions": desc}])

            asyncio.create_task(resolve())
            return (1, asyncio.wait_for(future, timeout))

        mock_ibsocket.create_snapshot = create_snapshot_side_effect
        mock_ibsocket.reqMatchingSymbols = MagicMock()

        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        result = await client.reqMatchingSymbols("AAPL")

        assert len(result) == 1
        assert result[0].contract.symbol == "AAPL"
        mock_ibsocket.reqMatchingSymbols.assert_called_once_with(1, "AAPL")

    @pytest.mark.asyncio
    async def test_req_matching_symbols_sends_correct_message(self) -> None:
        """Test reqMatchingSymbols sends correct message format."""
        client = TWSClient("127.0.0.1", 7497, 1)

        # Create mock ibsocket with contract_tracker
        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True
        mock_ibsocket.get_cached_data.return_value = None  # No cache hit

        # Mock contract_tracker - always return empty to trigger API call
        mock_ibsocket.contract_tracker.get_by_symbol_prefix.return_value = []

        # Setup create_snapshot mock
        def create_snapshot_side_effect(
            business_key: str, *, timeout: float | None = 5
        ) -> tuple[int | None, Awaitable[Any]]:
            loop = asyncio.get_running_loop()
            future: asyncio.Future[list[Any]] = loop.create_future()

            async def resolve() -> None:
                await asyncio.sleep(0.01)
                future.set_result([])

            asyncio.create_task(resolve())
            return (42, asyncio.wait_for(future, timeout))

        mock_ibsocket.create_snapshot = create_snapshot_side_effect
        mock_ibsocket.reqMatchingSymbols = MagicMock()

        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        await client.reqMatchingSymbols("MSFT")

        # Verify reqMatchingSymbols was called with correct args
        mock_ibsocket.reqMatchingSymbols.assert_called_once_with(42, "MSFT")

    @pytest.mark.asyncio
    async def test_req_matching_symbols_cache_hit_returns_cached_data(self) -> None:
        """Test reqMatchingSymbols returns cached data from ContractTracker."""
        client = TWSClient("127.0.0.1", 7497, 1, timeout=5.0)

        # Create mock ibsocket with contract_tracker
        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True

        # Create cached contract
        contract = Contract()
        contract.symbol = "AAPL"
        contract.exchange = "SMART"
        contract.secType = "STK"
        contract.conId = 265598
        desc = ContractDescription()
        desc.contract = contract

        cached_contract = CachedContract.from_contract_description(desc)

        # Mock contract_tracker to return cached data (cache hit)
        mock_ibsocket.contract_tracker.get_by_symbol_prefix.return_value = [
            cached_contract
        ]

        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        result = await client.reqMatchingSymbols("AAPL")

        assert len(result) == 1
        assert result[0].contract.symbol == "AAPL"
        assert result[0].contract.conId == 265598
        # create_snapshot should NOT be called on cache hit
        mock_ibsocket.create_snapshot.assert_not_called()
        mock_ibsocket.reqMatchingSymbols.assert_not_called()

    @pytest.mark.asyncio
    async def test_req_matching_symbols_populates_contracts_tracker(self) -> None:
        """Test reqMatchingSymbols returns CachedContract list after API call."""
        client = TWSClient("127.0.0.1", 7497, 1, timeout=5.0)

        # Create mock ibsocket with contract_tracker
        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True
        mock_ibsocket.get_cached_data.return_value = None  # No cache hit

        # Create test contract
        contract = Contract()
        contract.symbol = "AAPL"
        contract.exchange = "SMART"
        contract.secType = "STK"
        contract.conId = 265598
        desc = ContractDescription()
        desc.contract = contract

        cached_contract = CachedContract.from_contract_description(desc)

        # Mock contract_tracker - first call returns empty (cache miss), second returns data
        call_count = [0]

        def get_by_symbol_prefix_side_effect(pattern: str) -> list[CachedContract]:
            call_count[0] += 1
            if call_count[0] == 1:
                return []  # First call: cache miss
            return [cached_contract]  # Second call: after API fetch

        mock_ibsocket.contract_tracker.get_by_symbol_prefix.side_effect = (
            get_by_symbol_prefix_side_effect
        )

        # Setup create_snapshot mock
        def create_snapshot_side_effect(
            business_key: str, *, timeout: float | None = 5
        ) -> tuple[int | None, Awaitable[Any]]:
            loop = asyncio.get_running_loop()
            future: asyncio.Future[list[dict[str, Any]]] = loop.create_future()

            async def resolve() -> None:
                await asyncio.sleep(0.01)
                future.set_result([{"contractDescriptions": desc}])

            asyncio.create_task(resolve())
            return (1, asyncio.wait_for(future, timeout))

        mock_ibsocket.create_snapshot = create_snapshot_side_effect
        mock_ibsocket.reqMatchingSymbols = MagicMock()

        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        result = await client.reqMatchingSymbols("AAPL")

        # Verify we got results and API was called
        assert len(result) == 1
        assert result[0].contract.conId == 265598
        assert result[0].contract.symbol == "AAPL"
        assert result[0].has_full_details is False  # Partial from description
        mock_ibsocket.reqMatchingSymbols.assert_called_once()

    @pytest.mark.asyncio
    async def test_req_matching_symbols_filters_invalid_conids(self) -> None:
        """Test reqMatchingSymbols filters out contracts with conId <= 0."""
        client = TWSClient("127.0.0.1", 7497, 1, timeout=5.0)

        # Create mock ibsocket with contract_tracker
        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True
        mock_ibsocket.get_cached_data.return_value = None

        # Create contracts - one valid, one invalid
        valid_contract = Contract()
        valid_contract.symbol = "AAPL"
        valid_contract.exchange = "SMART"
        valid_contract.secType = "STK"
        valid_contract.conId = 265598
        valid_desc = ContractDescription()
        valid_desc.contract = valid_contract

        invalid_contract = Contract()
        invalid_contract.symbol = "INVALID"
        invalid_contract.exchange = "SMART"
        invalid_contract.secType = "STK"
        invalid_contract.conId = 0  # Invalid
        invalid_desc = ContractDescription()
        invalid_desc.contract = invalid_contract

        # Only valid contract should be cached
        valid_cached = CachedContract.from_contract_description(valid_desc)

        # Mock contract_tracker - first call returns empty (cache miss), second returns only valid
        call_count = [0]

        def get_by_symbol_prefix_side_effect(pattern: str) -> list[CachedContract]:
            call_count[0] += 1
            if call_count[0] == 1:
                return []  # First call: cache miss
            return [valid_cached]  # Second call: only valid contracts in tracker

        mock_ibsocket.contract_tracker.get_by_symbol_prefix.side_effect = (
            get_by_symbol_prefix_side_effect
        )

        # Setup create_snapshot mock - returns both valid and invalid
        def create_snapshot_side_effect(
            business_key: str, *, timeout: float | None = 5
        ) -> tuple[int | None, Awaitable[Any]]:
            loop = asyncio.get_running_loop()
            future: asyncio.Future[list[dict[str, Any]]] = loop.create_future()

            async def resolve() -> None:
                await asyncio.sleep(0.01)
                future.set_result(
                    [
                        {"contractDescriptions": valid_desc},
                        {"contractDescriptions": invalid_desc},
                    ]
                )

            asyncio.create_task(resolve())
            return (1, asyncio.wait_for(future, timeout))

        mock_ibsocket.create_snapshot = create_snapshot_side_effect
        mock_ibsocket.reqMatchingSymbols = MagicMock()

        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        result = await client.reqMatchingSymbols("AAPL")

        # Only valid contract should be returned (filtering happens in symbolSamples callback)
        assert len(result) == 1
        assert result[0].contract.conId == 265598


class TestTWSClientReqContractDetails:
    """Test reqContractDetails async method."""

    @pytest.mark.asyncio
    async def test_req_contract_details_returns_list(self) -> None:
        """Test reqContractDetails returns CachedContract list from ContractTracker cache."""
        client = TWSClient("127.0.0.1", 7497, 1)

        # Create test contract and details
        contract = Contract()
        contract.symbol = "AAPL"
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.conId = 265598

        details = ContractDetails()
        details.contract = contract
        details.longName = "Apple Inc"

        # Create cached contract with full details
        cached_contract = CachedContract.from_contract_details(details)

        # Create mock ibsocket with contract_tracker
        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True

        # Mock contract_tracker.get_full_details to return cached data (cache hit)
        mock_ibsocket.contract_tracker.get_full_details.return_value = cached_contract
        mock_ibsocket.contract_tracker._details = {265598: cached_contract}

        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        # Query by conId (direct cache hit)
        query_contract = Contract()
        query_contract.symbol = "AAPL"
        query_contract.exchange = "SMART"
        query_contract.conId = 265598

        result = await client.reqContractDetails(query_contract)

        assert len(result) == 1
        assert result[0].longName == "Apple Inc"
        assert result[0].contract.symbol == "AAPL"
        # No API calls should be made (cache hit)
        mock_ibsocket.create_snapshot.assert_not_called()

    @pytest.mark.asyncio
    async def test_req_contract_details_cache_hit_returns_cached_data(self) -> None:
        """Test reqContractDetails returns cached data from ContractTracker."""
        client = TWSClient("127.0.0.1", 7497, 1)

        # Create test contract and details
        contract = Contract()
        contract.symbol = "AAPL"
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.conId = 265598

        details = ContractDetails()
        details.contract = contract
        details.longName = "Apple Inc (Cached)"

        cached_contract = CachedContract.from_contract_details(details)

        # Create mock ibsocket with contract_tracker
        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True

        # Mock contract_tracker.get_full_details to return cached data
        mock_ibsocket.contract_tracker.get_full_details.return_value = cached_contract
        mock_ibsocket.contract_tracker._details = {265598: cached_contract}

        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        query_contract = Contract()
        query_contract.symbol = "AAPL"
        query_contract.secType = "STK"
        query_contract.exchange = "SMART"
        query_contract.conId = 265598

        result = await client.reqContractDetails(query_contract)

        assert len(result) == 1
        assert result[0].longName == "Apple Inc (Cached)"
        # create_snapshot should NOT be called on cache hit
        mock_ibsocket.create_snapshot.assert_not_called()
        mock_ibsocket.reqContractDetails.assert_not_called()

    @pytest.mark.asyncio
    async def test_req_contract_details_uses_contract_tracker(self) -> None:
        """Test reqContractDetails returns from ContractTracker when has_full_details=True."""
        from trading_api.providers.tws.cached_contract import CachedContract

        client = TWSClient("127.0.0.1", 7497, 1)

        # Create mock ibsocket with contract_tracker
        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True

        # Pre-populate tracker with full details
        contract = Contract()
        contract.symbol = "AAPL"
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.primaryExchange = "SMART"
        contract.conId = 265598
        details = ContractDetails()
        details.contract = contract
        details.longName = "Apple Inc (From Tracker)"

        cached_contract = CachedContract.from_contract_details(details)

        # Mock contract_tracker.get_full_details to return cached data
        mock_ibsocket.contract_tracker.get_full_details.return_value = cached_contract
        mock_ibsocket.contract_tracker._details = {265598: cached_contract}

        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        # Query with matching ticker and conId (direct cache hit)
        query_contract = Contract()
        query_contract.symbol = "AAPL"
        query_contract.secType = "STK"
        query_contract.exchange = "SMART"
        query_contract.conId = 265598  # Provide conId for direct cache lookup

        result = await client.reqContractDetails(query_contract)

        assert len(result) == 1
        assert result[0].longName == "Apple Inc (From Tracker)"
        # Neither ibsocket cache nor API should be called
        mock_ibsocket.get_cached_data.assert_not_called()
        mock_ibsocket.create_snapshot.assert_not_called()


class TestTWSClientReqHistoricalData:
    """Test reqHistoricalData async method."""

    @pytest.mark.asyncio
    async def test_req_historical_data_returns_bars(self) -> None:
        """Test reqHistoricalData returns BarData list."""
        client = TWSClient("127.0.0.1", 7497, 1)

        # Create mock ibsocket
        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True

        # Create test bars as dicts (reqHistoricalData returns list[dict[str, Any]])
        bar1 = {
            "date": "20231215 09:30:00",
            "open": 150.0,
            "high": 151.0,
            "low": 149.5,
            "close": 150.5,
        }

        bar2 = {
            "date": "20231215 09:31:00",
            "open": 150.5,
            "close": 151.0,
        }

        # Mock get_cached_data to return None (no cache)
        mock_ibsocket.get_cached_data = MagicMock(return_value=None)

        # Setup create_snapshot mock
        def create_snapshot_side_effect(
            business_key: str, *, timeout: float | None = 5
        ) -> tuple[int | None, Awaitable[Any]]:
            loop = asyncio.get_running_loop()
            future: asyncio.Future[list[dict[str, Any]]] = loop.create_future()

            async def resolve() -> None:
                await asyncio.sleep(0.01)
                future.set_result([bar1, bar2])

            asyncio.create_task(resolve())
            return (1, asyncio.wait_for(future, timeout))

        mock_ibsocket.create_snapshot = create_snapshot_side_effect
        mock_ibsocket.reqBars = MagicMock()

        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        contract = Contract()
        contract.symbol = "AAPL"
        contract.secType = "STK"
        contract.exchange = "SMART"

        result = await client.reqHistoricalData(
            contract=contract,
            end_date_time="20231215 16:00:00",
            duration_str="1 D",
            bar_size="1 min",
        )

        assert len(result) == 2
        assert result[0]["open"] == 150.0
        mock_ibsocket.reqBars.assert_called_once()


class TestTWSClientStreamMethods:
    """Test stream subscription methods."""

    def test_req_bar_data_stream_registers_callback(self) -> None:
        """Test reqBarDataStream registers stream with callback."""
        from trading_api.models.exceptions import ProviderException

        client = TWSClient("127.0.0.1", 7497, 1)

        # Create mock ibsocket
        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True
        mock_ibsocket.create_stream = MagicMock(return_value=1)  # Returns reqId
        mock_ibsocket.reqBars = MagicMock()

        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        contract = Contract()
        contract.symbol = "AAPL"
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"

        async def callback(data: dict[str, Any], fields: list[str]) -> None:
            pass

        async def on_error(exc: ProviderException) -> None:
            pass

        stream_key = client.reqBarDataStream(contract, "5 mins", callback, on_error)

        assert isinstance(stream_key, str)
        mock_ibsocket.create_stream.assert_called_once()
        mock_ibsocket.reqBars.assert_called_once()

    def test_cancel_bar_data_stream_sends_cancel(self) -> None:
        """Test cancelDataSubscription sends cancel message."""
        from trading_api.models.exceptions import ProviderException

        client = TWSClient("127.0.0.1", 7497, 1)

        # Create mock ibsocket
        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True
        mock_ibsocket.create_stream = MagicMock(return_value=1)
        mock_ibsocket.reqBars = MagicMock()
        mock_ibsocket.remove_stream = MagicMock()

        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        contract = Contract()
        contract.symbol = "AAPL"
        contract.secType = "STK"
        contract.exchange = "SMART"

        async def callback(data: dict[str, Any], fields: list[str]) -> None:
            pass

        async def on_error(exc: ProviderException) -> None:
            pass

        # First create a stream
        stream_key = client.reqBarDataStream(contract, "5 mins", callback, on_error)

        # Cancel the stream
        client.cancelDataSubscription(stream_key)

        mock_ibsocket.remove_stream.assert_called_once_with(stream_key)


class TestTWSClientErrorHandling:
    """Test error handling in async methods."""

    @pytest.mark.asyncio
    async def test_timeout_raises_timeout_error(self) -> None:
        """Test TimeoutError is raised when request times out."""
        client = TWSClient("127.0.0.1", 7497, 1, timeout=0.05)

        # Create mock ibsocket with contract_tracker
        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True
        mock_ibsocket.get_cached_data.return_value = None  # No cache hit

        # Mock contract_tracker to return empty (cache miss) - triggers API call
        mock_ibsocket.contract_tracker.get_by_symbol_prefix.return_value = []

        # Setup create_snapshot that returns a future that never resolves
        def create_snapshot_side_effect(
            business_key: str, *, timeout: float | None = 5
        ) -> tuple[int | None, Awaitable[Any]]:
            loop = asyncio.get_running_loop()
            future: asyncio.Future[Any] = loop.create_future()
            # Return future wrapped with timeout - will timeout since never resolved
            return (1, asyncio.wait_for(future, timeout))

        mock_ibsocket.create_snapshot = create_snapshot_side_effect
        mock_ibsocket.reqMatchingSymbols = MagicMock()

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


class TestTWSClientPlaceOcaGroup:
    """Test placeOcaGroup method for OCA order groups."""

    @pytest.mark.asyncio
    async def test_place_oca_group_empty_orders_returns_empty(self) -> None:
        """Test placeOcaGroup with empty orders returns empty list."""
        client = TWSClient("127.0.0.1", 7497, 1)

        contract = Contract()
        contract.symbol = "AAPL"

        result = await client.placeOcaGroup(contract, [], "brackets_test_oca")

        assert result == []

    @pytest.mark.asyncio
    async def test_place_oca_group_sets_oca_attributes(self) -> None:
        """Test placeOcaGroup sets ocaGroup and ocaType on all orders."""
        from decimal import Decimal

        from ibapi.order import Order

        client = TWSClient("127.0.0.1", 7497, 1)

        # Create mock ibsocket
        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True

        # Mock order_tracker with next_order_id
        mock_order_tracker = MagicMock()
        mock_order_tracker.next_order_id = 100
        mock_order_tracker.signed_oca_groups.return_value = set()
        mock_order_tracker.find_oca_group.return_value = None
        mock_order_tracker.find_tracked_order.return_value = None

        # Mock order_update to return immediately
        async def mock_order_update(
            order_id: int, timeout: float | None = None
        ) -> MagicMock:
            tracked = MagicMock()
            tracked.orderId = order_id
            return tracked

        mock_order_tracker.order_update = mock_order_update
        mock_ibsocket.order_tracker = mock_order_tracker

        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        # Create test orders
        order1 = Order()
        order1.action = "SELL"
        order1.totalQuantity = Decimal("100")
        order1.orderType = "STP"
        order1.auxPrice = 145.00

        order2 = Order()
        order2.action = "SELL"
        order2.totalQuantity = Decimal("100")
        order2.orderType = "LMT"
        order2.lmtPrice = 160.00

        contract = Contract()
        contract.symbol = "AAPL"

        # Execute
        await client.placeOcaGroup(
            contract, [order1, order2], "brackets_test_oca_group", oca_type=1
        )

        # Verify OCA attributes were set (with timestamp appended)
        assert order1.ocaGroup.startswith("brackets_test_oca_group")
        assert order1.ocaType == 1
        assert order2.ocaGroup.startswith("brackets_test_oca_group")
        assert order2.ocaType == 1

    @pytest.mark.asyncio
    async def test_place_oca_group_uses_transmit_chain(self) -> None:
        """Test placeOcaGroup uses transmit=False for all but last order."""
        from decimal import Decimal
        from unittest.mock import PropertyMock

        from ibapi.order import Order

        client = TWSClient("127.0.0.1", 7497, 1)

        # Track placeOrder calls
        place_order_calls: list[tuple[int, Contract, Order]] = []

        # Create mock ibsocket
        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True

        # Mock order_tracker
        mock_order_tracker = MagicMock()
        order_id_counter = [100]
        mock_order_tracker.signed_oca_groups.return_value = set()
        mock_order_tracker.find_oca_group.return_value = None
        mock_order_tracker.find_tracked_order.return_value = None

        def get_next_order_id() -> int:
            current = order_id_counter[0]
            order_id_counter[0] += 1
            return current

        type(mock_order_tracker).next_order_id = PropertyMock(
            side_effect=get_next_order_id
        )

        async def mock_order_update(
            order_id: int, timeout: float | None = None
        ) -> MagicMock:
            tracked = MagicMock()
            tracked.orderId = order_id
            return tracked

        mock_order_tracker.order_update = mock_order_update
        mock_ibsocket.order_tracker = mock_order_tracker

        # Capture placeOrder calls
        def mock_place_order(order_id: int, contract: Contract, order: Order) -> None:
            place_order_calls.append((order_id, contract, order))

        mock_ibsocket.placeOrder = mock_place_order

        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        # Create three test orders
        orders = []
        for i in range(3):
            order = Order()
            order.action = "SELL"
            order.totalQuantity = Decimal("100")
            order.orderType = "LMT"
            order.lmtPrice = 150.00 + i * 5
            orders.append(order)

        contract = Contract()
        contract.symbol = "AAPL"

        # Execute
        await client.placeOcaGroup(contract, orders, "brackets_oca_test", oca_type=1)

        # Verify transmit chain pattern: all False except last
        assert len(place_order_calls) == 3
        assert place_order_calls[0][2].transmit is False  # First order
        assert place_order_calls[1][2].transmit is False  # Second order
        assert place_order_calls[2][2].transmit is True  # Last order triggers all
