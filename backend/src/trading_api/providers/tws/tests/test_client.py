"""Tests for TWSClient - AsyncIO facade to TWS/IB Gateway.

Test Strategy:
- Focus on business-critical behavior, not trivial delegation
- Test TWSClient-specific logic: caching strategy, TWS protocol rules, parameter transformation
- Mock IBSocket/trackers at boundary - we test how TWSClient orchestrates them, not pass-through

What we DON'T test here (tested elsewhere):
- Tracker internals (test_order_tracker.py, test_position_tracker.py, etc.)
- IBSocket wire protocol (test_ibsocket.py)
- Contract caching logic (test_cached_contract.py, test_contract_tracker.py)
"""

import asyncio
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from ibapi.contract import Contract, ContractDescription, ContractDetails
from ibapi.order import Order

from trading_api.models.exceptions import ProviderException
from trading_api.models.market import Bar
from trading_api.providers.tws.cached_contract import CachedContract
from trading_api.providers.tws.tws_connection import TWSClient

# =============================================================================
# INITIALIZATION & CONNECTION
# =============================================================================


class TestTWSClientInitialization:
    """Test client configuration and lazy connection behavior."""

    def test_stores_connection_parameters(self) -> None:
        """Client stores host/port/client_id for deferred connection."""
        client = TWSClient(host="192.168.1.1", port=4002, client_id=5)

        assert client._host == "192.168.1.1"
        assert client._port == 4002
        assert client._client_id == 5

    def test_default_timeout_is_10_seconds(self) -> None:
        """Default timeout prevents indefinite hangs on TWS requests."""
        client = TWSClient("127.0.0.1", 7497, 1)
        assert client._timeout == 10.0

    def test_custom_timeout_override(self) -> None:
        """Production may need longer timeouts for complex queries."""
        client = TWSClient("127.0.0.1", 7497, 1, timeout=30.0)
        assert client._timeout == 30.0

    def test_lazy_connection_on_first_access(self) -> None:
        """IBSocket connects only when first accessed (not at init)."""
        client = TWSClient("127.0.0.1", 7497, 1, timeout=0.5)

        with patch.object(client, "_TWSClient__ibsocket", create=True) as mock_ibsocket:
            mock_ibsocket.running = False

            new_socket = MagicMock()
            new_socket.running = True
            new_socket._ready_event = MagicMock()
            new_socket._ready_event.wait.return_value = True

            with patch(
                "trading_api.providers.tws.tws_connection.IBSocket",
                return_value=new_socket,
            ):
                _ = client.ibsocket

            new_socket.connect.assert_called_once()

    def test_reuses_running_connection(self) -> None:
        """Multiple ibsocket accesses don't trigger reconnection."""
        client = TWSClient("127.0.0.1", 7497, 1)

        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True
        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        sock1 = client.ibsocket
        sock2 = client.ibsocket

        mock_ibsocket.connect.assert_not_called()
        assert sock1 is sock2

    def test_shutdown_disconnects(self) -> None:
        """Clean shutdown releases TWS connection."""
        client = TWSClient("127.0.0.1", 7497, 1)

        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True
        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        client.shutdown()

        mock_ibsocket.disconnect.assert_called_once()


# =============================================================================
# SYMBOL SEARCH & CONTRACT RESOLUTION
# =============================================================================


class TestSymbolSearch:
    """Test reqMatchingSymbols - symbol autocomplete functionality."""

    @pytest.mark.asyncio
    async def test_returns_from_cache_without_api_call(self) -> None:
        """Cache hit avoids expensive TWS roundtrip."""
        client = TWSClient("127.0.0.1", 7497, 1, timeout=5.0)

        contract = Contract()
        contract.symbol = "AAPL"
        contract.exchange = "SMART"
        contract.secType = "STK"
        contract.conId = 265598
        desc = ContractDescription()
        desc.contract = contract
        cached = CachedContract.from_contract_description(desc)

        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True
        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        # Mock contract_tracker with async get_descriptions
        mock_tracker = MagicMock()
        mock_tracker.get_descriptions = AsyncMock(return_value=[cached])
        client._TWSClient__contract_tracker = mock_tracker  # type: ignore[attr-defined]

        result = await client.reqMatchingSymbols("AAPL")

        assert len(result) == 1
        assert result[0].contract.symbol == "AAPL"
        assert result[0].contract.conId == 265598
        # ContractTracker.get_descriptions called
        mock_tracker.get_descriptions.assert_called_once_with("AAPL", timeout=5.0)

    @pytest.mark.asyncio
    async def test_filters_invalid_contract_ids(self) -> None:
        """Contracts with conId <= 0 are filtered (TWS junk data).

        Note: Filtering now happens inside ContractTracker.get_descriptions,
        so this test verifies TWSClient passes through tracker results correctly.
        """
        client = TWSClient("127.0.0.1", 7497, 1, timeout=5.0)

        valid = Contract()
        valid.symbol = "AAPL"
        valid.exchange = "SMART"
        valid.conId = 265598
        valid_desc = ContractDescription()
        valid_desc.contract = valid

        valid_cached = CachedContract.from_contract_description(valid_desc)

        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True
        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        # ContractTracker already filters invalid (conId <= 0)
        mock_tracker = MagicMock()
        mock_tracker.get_descriptions = AsyncMock(return_value=[valid_cached])
        client._TWSClient__contract_tracker = mock_tracker  # type: ignore[attr-defined]

        result = await client.reqMatchingSymbols("AAPL")

        # Only valid contract returned (filtering done by tracker)
        assert len(result) == 1
        assert result[0].contract.conId == 265598


class TestContractDetails:
    """Test reqContractDetails - full contract specification lookup."""

    @pytest.mark.asyncio
    async def test_returns_from_tracker_cache(self) -> None:
        """Full details returned from ContractTracker without API call."""
        client = TWSClient("127.0.0.1", 7497, 1)

        contract = Contract()
        contract.symbol = "AAPL"
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.conId = 265598

        details = ContractDetails()
        details.contract = contract
        details.longName = "Apple Inc"

        cached = CachedContract.from_contract_details(details)

        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True
        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        # Mock contract_tracker with async get_details
        mock_tracker = MagicMock()
        mock_tracker.get_details = AsyncMock(return_value=cached)
        client._TWSClient__contract_tracker = mock_tracker  # type: ignore[attr-defined]

        query = Contract()
        query.symbol = "AAPL"
        query.exchange = "SMART"
        query.conId = 265598

        result = await client.reqContractDetails(query)

        assert result.has_full_details is True
        assert result.longName == "Apple Inc"
        mock_tracker.get_details.assert_called_once()


class TestTickerDetails:
    """Test reqTickerDetails - ticker string → CachedContract resolution."""

    @pytest.mark.asyncio
    async def test_parses_exchange_symbol_format(self) -> None:
        """Ticker 'EXCHANGE:SYMBOL' parsed into Contract fields."""
        client = TWSClient("127.0.0.1", 7497, 1)

        mock_cached = MagicMock(spec=CachedContract)

        with patch.object(
            client, "reqContractDetails", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = mock_cached

            await client.reqTickerDetails("NASDAQ:AAPL")

            call_args = mock_req.call_args
            contract = call_args[0][0]
            assert contract.symbol == "AAPL"
            assert contract.primaryExchange == "NASDAQ"
            assert contract.secType == "STK"

    @pytest.mark.asyncio
    async def test_raises_when_symbol_not_found(self) -> None:
        """Unknown symbol raises ProviderException with specific code."""
        client = TWSClient("127.0.0.1", 7497, 1)

        with patch.object(
            client, "reqContractDetails", new_callable=AsyncMock
        ) as mock_req:
            mock_req.side_effect = ProviderException(
                provider="tws",
                capability="datafeed",
                message="Contract not found",
                code="PROVIDER_DATAFEED_SYMBOL_NOT_FOUND",
            )

            with pytest.raises(ProviderException) as exc_info:
                await client.reqTickerDetails("NASDAQ:INVALID_SYMBOL")

            assert exc_info.value.code == "PROVIDER_DATAFEED_SYMBOL_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_returns_contract_details(self) -> None:
        """Successfully returns CachedContract when found."""
        client = TWSClient("127.0.0.1", 7497, 1)

        mock_cached = MagicMock(spec=CachedContract)
        mock_cached.contract = Contract()
        mock_cached.contract.conId = 111

        with patch.object(
            client, "reqContractDetails", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = mock_cached

            result = await client.reqTickerDetails("NASDAQ:AAPL")

            assert result is mock_cached


# =============================================================================
# HISTORICAL DATA
# =============================================================================


class TestHistoricalData:
    """Test reqHistoricalData - bar data requests."""

    @pytest.mark.asyncio
    async def test_delegates_to_bars_tracker(self) -> None:
        """Request parameters correctly passed to BarsTracker."""
        client = TWSClient("127.0.0.1", 7497, 1)

        bar1 = Bar(
            time=1702630200000,
            open=150.0,
            high=151.0,
            low=149.5,
            close=150.5,
            volume=1000000,
        )
        bar2 = Bar(
            time=1702630260000,
            open=150.5,
            high=151.0,
            low=150.0,
            close=151.0,
            volume=800000,
        )

        mock_bars_tracker = MagicMock()
        mock_bars_tracker.request = AsyncMock(return_value=[bar1, bar2])
        client._TWSClient__bars_tracker = mock_bars_tracker  # type: ignore[attr-defined]

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
        assert result[0].open == 150.0
        mock_bars_tracker.request.assert_called_once_with(
            contract, "1 min", "20231215 16:00:00", "1 D", timeout=None
        )


# =============================================================================
# ORDER MANAGEMENT - CRITICAL TWS PROTOCOL TESTS
# =============================================================================


class TestCancelOrder:
    """Test cancelOrder - order cancellation logic."""

    @pytest.mark.asyncio
    async def test_cancels_existing_order(self) -> None:
        """Sends cancel request to TWS for tracked order."""
        client = TWSClient("127.0.0.1", 7497, 1)

        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True

        existing = MagicMock()
        existing.orderId = 100

        mock_order_tracker = MagicMock()
        mock_order_tracker.ensure_existing_order.return_value = existing

        cancelled = MagicMock()
        cancelled.orderId = 100
        cancelled.orderState.status = "Cancelled"

        mock_order_tracker.order_update = AsyncMock(return_value=cancelled)
        mock_ibsocket.order_tracker = mock_order_tracker
        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        result = await client.cancelOrder(100)

        mock_ibsocket.cancelOrder.assert_called_once_with(100)
        assert result.orderId == 100

    @pytest.mark.asyncio
    async def test_raises_for_nonexistent_order(self) -> None:
        """Cannot cancel order that doesn't exist in tracker."""
        client = TWSClient("127.0.0.1", 7497, 1)

        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True

        mock_order_tracker = MagicMock()
        mock_order_tracker.ensure_existing_order.side_effect = KeyError(
            "Order not found"
        )
        mock_ibsocket.order_tracker = mock_order_tracker
        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        with pytest.raises(KeyError):
            await client.cancelOrder(999)


class TestPlaceOcaGroup:
    """Test placeOcaGroup - TWS OCA (One-Cancels-All) order groups."""

    @pytest.mark.asyncio
    async def test_empty_orders_returns_empty(self) -> None:
        """No orders → no TWS calls, empty result."""
        client = TWSClient("127.0.0.1", 7497, 1)

        contract = Contract()
        contract.symbol = "AAPL"

        result = await client.placeOcaGroup(contract, [], "test_oca")

        assert result == []

    @pytest.mark.asyncio
    async def test_sets_oca_group_and_type_on_all_orders(self) -> None:
        """All orders in group must share ocaGroup name and ocaType."""
        client = TWSClient("127.0.0.1", 7497, 1)

        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True

        mock_order_tracker = MagicMock()
        mock_order_tracker.next_order_id = 100
        mock_order_tracker.signed_oca_groups.return_value = set()
        mock_order_tracker.find_oca_group.return_value = None
        mock_order_tracker.find_tracked_order.return_value = None
        mock_order_tracker.order_update = AsyncMock(return_value=MagicMock(orderId=100))
        mock_ibsocket.order_tracker = mock_order_tracker
        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

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

        await client.placeOcaGroup(
            contract, [order1, order2], "brackets_oca", oca_type=1
        )

        # OCA attributes set with timestamp suffix
        assert order1.ocaGroup.startswith("brackets_oca")
        assert order1.ocaType == 1
        assert order2.ocaGroup.startswith("brackets_oca")
        assert order2.ocaType == 1
        # Same group name (including timestamp)
        assert order1.ocaGroup == order2.ocaGroup

    @pytest.mark.asyncio
    async def test_transmit_chain_pattern(self) -> None:
        """TWS requires transmit=False for all but last order in group."""
        client = TWSClient("127.0.0.1", 7497, 1)

        place_order_calls: list[tuple[int, Contract, Order]] = []

        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True

        mock_order_tracker = MagicMock()
        order_id_counter = [100]
        mock_order_tracker.signed_oca_groups.return_value = set()
        mock_order_tracker.find_oca_group.return_value = None
        mock_order_tracker.find_tracked_order.return_value = None

        def get_next_id() -> int:
            current = order_id_counter[0]
            order_id_counter[0] += 1
            return current

        type(mock_order_tracker).next_order_id = PropertyMock(side_effect=get_next_id)
        mock_order_tracker.order_update = AsyncMock(
            side_effect=lambda oid, **kw: MagicMock(orderId=oid)
        )
        mock_ibsocket.order_tracker = mock_order_tracker

        def capture_place_order(
            order_id: int, contract: Contract, order: Order
        ) -> None:
            place_order_calls.append((order_id, contract, order))

        mock_ibsocket.placeOrder = capture_place_order
        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        orders: list[Order] = []
        for i in range(3):
            o = Order()
            o.action = "SELL"
            o.totalQuantity = Decimal("100")
            o.orderType = "LMT"
            o.lmtPrice = 150.00 + i * 5
            orders.append(o)

        contract = Contract()
        contract.symbol = "AAPL"

        await client.placeOcaGroup(contract, orders, "brackets_test_oca", oca_type=1)

        # TWS transmit chain: False, False, True
        assert len(place_order_calls) == 3
        assert place_order_calls[0][2].transmit is False
        assert place_order_calls[1][2].transmit is False
        assert place_order_calls[2][2].transmit is True


class TestPlaceOrderGroup:
    """Test placeOrderGroup - bracket orders (parent + stop/limit children)."""

    @pytest.mark.asyncio
    async def test_parent_only_transmits_immediately(self) -> None:
        """Parent without children: transmit=True (immediate submission)."""
        client = TWSClient("127.0.0.1", 7497, 1)

        place_order_calls: list[tuple[int, Contract, Order]] = []

        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True

        mock_order_tracker = MagicMock()
        mock_order_tracker.find_tracked_order.return_value = None
        type(mock_order_tracker).next_order_id = PropertyMock(return_value=100)
        mock_order_tracker.order_update = AsyncMock(return_value=MagicMock(orderId=100))
        mock_ibsocket.order_tracker = mock_order_tracker

        mock_ibsocket.placeOrder = lambda oid, c, o: place_order_calls.append(
            (oid, c, o)
        )
        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        parent = Order()
        parent.action = "BUY"
        parent.totalQuantity = Decimal("100")
        parent.orderType = "LMT"
        parent.lmtPrice = 150.00

        contract = Contract()
        contract.symbol = "AAPL"
        contract.conId = 265598

        parent_tracked, children_tracked = await client.placeOrderGroup(
            contract, parent, children=[]
        )

        assert len(place_order_calls) == 1
        assert place_order_calls[0][2].transmit is True
        assert children_tracked == []

    @pytest.mark.asyncio
    async def test_parent_with_children_uses_transmit_chain(self) -> None:
        """Parent + children: parent transmit=False, last child transmit=True."""
        client = TWSClient("127.0.0.1", 7497, 1)

        place_order_calls: list[tuple[int, Contract, Order]] = []

        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True

        mock_order_tracker = MagicMock()
        mock_order_tracker.find_tracked_order.return_value = None
        mock_order_tracker.find_oca_group.return_value = None
        order_id_counter = [100]

        def get_next_id() -> int:
            current = order_id_counter[0]
            order_id_counter[0] += 1
            return current

        type(mock_order_tracker).next_order_id = PropertyMock(side_effect=get_next_id)
        mock_order_tracker.order_update = AsyncMock(
            side_effect=lambda oid, **kw: MagicMock(orderId=oid)
        )
        mock_ibsocket.order_tracker = mock_order_tracker
        mock_ibsocket.placeOrder = lambda oid, c, o: place_order_calls.append(
            (oid, c, o)
        )
        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        parent = Order()
        parent.action = "BUY"
        parent.totalQuantity = Decimal("100")
        parent.orderType = "LMT"
        parent.lmtPrice = 150.00

        stop_loss = Order()
        stop_loss.action = "SELL"
        stop_loss.totalQuantity = Decimal("100")
        stop_loss.orderType = "STP"
        stop_loss.auxPrice = 145.00

        take_profit = Order()
        take_profit.action = "SELL"
        take_profit.totalQuantity = Decimal("100")
        take_profit.orderType = "LMT"
        take_profit.lmtPrice = 160.00

        contract = Contract()
        contract.symbol = "AAPL"
        contract.conId = 265598

        await client.placeOrderGroup(
            contract, parent, children=[stop_loss, take_profit]
        )

        # Transmit chain: parent=False, child1=False, child2=True
        assert len(place_order_calls) == 3
        assert place_order_calls[0][2].transmit is False  # Parent
        assert place_order_calls[1][2].transmit is False  # First child
        assert place_order_calls[2][2].transmit is True  # Last child triggers all

    @pytest.mark.asyncio
    async def test_creates_bracket_oca_group_for_children(self) -> None:
        """Children share OCA group named 'brackets_{parent_id}@{timestamp}'."""
        client = TWSClient("127.0.0.1", 7497, 1)

        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True

        mock_order_tracker = MagicMock()
        mock_order_tracker.find_tracked_order.return_value = None
        mock_order_tracker.find_oca_group.return_value = None
        order_id_counter = [100]

        def get_next_id() -> int:
            current = order_id_counter[0]
            order_id_counter[0] += 1
            return current

        type(mock_order_tracker).next_order_id = PropertyMock(side_effect=get_next_id)
        mock_order_tracker.order_update = AsyncMock(
            side_effect=lambda oid, **kw: MagicMock(orderId=oid)
        )
        mock_ibsocket.order_tracker = mock_order_tracker
        mock_ibsocket.placeOrder = MagicMock()
        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        parent = Order()
        parent.action = "BUY"
        parent.totalQuantity = Decimal("100")
        parent.orderType = "LMT"
        parent.lmtPrice = 150.00

        child = Order()
        child.action = "SELL"
        child.totalQuantity = Decimal("100")
        child.orderType = "STP"
        child.auxPrice = 145.00

        contract = Contract()
        contract.symbol = "AAPL"
        contract.conId = 265598

        await client.placeOrderGroup(contract, parent, children=[child])

        # OCA group named after parent order ID
        assert child.ocaGroup.startswith("brackets_100@")
        assert child.ocaType == 1

    @pytest.mark.asyncio
    async def test_modification_reuses_existing_order_id(self) -> None:
        """Modifying existing order reuses its ID (TWS protocol requirement)."""
        client = TWSClient("127.0.0.1", 7497, 1)

        place_order_calls: list[tuple[int, Contract, Order]] = []

        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True

        # Existing order in tracker
        existing_tracked = MagicMock()
        existing_tracked.orderId = 50
        existing_tracked.contract = Contract()
        existing_tracked.contract.conId = 265598
        existing_tracked.contract.exchange = "SMART"
        existing_order = Order()
        existing_order.lmtPrice = 148.00
        existing_order.auxPrice = 0.0
        existing_order.totalQuantity = Decimal("100")
        existing_order.parentId = 0
        existing_tracked.clone_order = MagicMock(return_value=existing_order)

        mock_order_tracker = MagicMock()
        mock_order_tracker.find_tracked_order.return_value = existing_tracked
        mock_order_tracker.find_oca_group.return_value = None
        type(mock_order_tracker).next_order_id = PropertyMock(
            return_value=100
        )  # Not used
        mock_order_tracker.order_update = AsyncMock(return_value=MagicMock(orderId=50))
        mock_order_tracker.ensure_existing_order = MagicMock(
            return_value=existing_tracked
        )
        mock_ibsocket.order_tracker = mock_order_tracker

        mock_ibsocket.placeOrder = lambda oid, c, o: place_order_calls.append(
            (oid, c, o)
        )
        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        parent = Order()
        parent.action = "BUY"
        parent.totalQuantity = Decimal("100")
        parent.orderType = "LMT"
        parent.lmtPrice = 150.00  # Modified price

        contract = Contract()
        contract.symbol = "AAPL"
        contract.conId = 265598

        await client.placeOrderGroup(contract, parent, children=[])

        # Existing order ID 50 reused, not new ID 100
        assert len(place_order_calls) == 1
        assert place_order_calls[0][0] == 50


class TestPlaceWhatifOrder:
    """Test placeWhatifOrder - margin preview without execution."""

    @pytest.mark.asyncio
    async def test_forces_whatif_flag_true(self) -> None:
        """whatIf must be True regardless of input."""
        client = TWSClient("127.0.0.1", 7497, 1)

        captured_order: list[Order] = []

        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True

        mock_order_tracker = MagicMock()
        type(mock_order_tracker).next_order_id = PropertyMock(return_value=100)
        mock_order_tracker.order_update = AsyncMock(return_value=MagicMock(orderId=100))
        mock_ibsocket.order_tracker = mock_order_tracker
        mock_ibsocket.placeOrder = lambda oid, c, o: captured_order.append(o)
        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        order = Order()
        order.action = "BUY"
        order.totalQuantity = Decimal("100")
        order.orderType = "LMT"
        order.lmtPrice = 150.00
        order.whatIf = False  # Should be forced to True

        contract = Contract()
        contract.symbol = "AAPL"
        contract.conId = 265598

        await client.placeWhatifOrder(contract, order)

        assert captured_order[0].whatIf is True

    @pytest.mark.asyncio
    async def test_resets_preset_order_id(self) -> None:
        """Pre-set orderId must be reset to -1 for whatIf orders."""
        client = TWSClient("127.0.0.1", 7497, 1)

        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True

        mock_order_tracker = MagicMock()
        type(mock_order_tracker).next_order_id = PropertyMock(return_value=100)
        mock_order_tracker.order_update = AsyncMock(return_value=MagicMock(orderId=100))
        mock_ibsocket.order_tracker = mock_order_tracker
        mock_ibsocket.placeOrder = MagicMock()
        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        order = Order()
        order.orderId = 999  # Pre-set should be reset
        order.action = "BUY"
        order.totalQuantity = Decimal("100")
        order.orderType = "LMT"
        order.lmtPrice = 150.00
        order.whatIf = True

        contract = Contract()
        contract.symbol = "AAPL"
        contract.conId = 265598

        await client.placeWhatifOrder(contract, order)

        assert order.orderId == -1


# =============================================================================
# STREAM SUBSCRIPTION MANAGEMENT
# =============================================================================


class TestDataStreams:
    """Test market data stream subscription/cancellation."""

    def test_bar_stream_delegates_to_bars_tracker(self) -> None:
        """reqBarDataStream registers with BarsTracker."""
        client = TWSClient("127.0.0.1", 7497, 1)

        mock_bars_tracker = MagicMock()
        mock_bars_tracker.subscribe = MagicMock(return_value="AAPL-SMART#uuid")
        client._TWSClient__bars_tracker = mock_bars_tracker  # type: ignore[attr-defined]

        contract = Contract()
        contract.symbol = "AAPL"
        contract.secType = "STK"
        contract.exchange = "SMART"

        async def callback(bar: Bar) -> None:
            pass

        async def on_error(exc: ProviderException) -> None:
            pass

        key = client.reqBarDataStream(contract, "5 mins", callback, on_error)

        assert key == "AAPL-SMART#uuid"
        mock_bars_tracker.subscribe.assert_called_once_with(
            contract, "5 mins", callback, on_error
        )

    def test_quote_stream_delegates_to_quote_tracker(self) -> None:
        """reqMktDataStream registers with QuoteTracker."""
        client = TWSClient("127.0.0.1", 7497, 1)

        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True
        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        mock_quote_tracker = MagicMock()
        mock_quote_tracker.subscribe = MagicMock(return_value="quote_key")
        client._TWSClient__quote_tracker = mock_quote_tracker  # type: ignore[attr-defined]

        mock_contract = MagicMock(spec=CachedContract)

        async def callback(quote: Any) -> None:
            pass

        async def on_error(err: Any) -> None:
            pass

        key = client.reqMktDataStream(mock_contract, callback, on_error)

        assert key == "quote_key"
        mock_quote_tracker.subscribe.assert_called_once_with(
            mock_contract, callback, on_error
        )

    def test_cancel_data_subscription_unsubscribes_all(self) -> None:
        """cancelDataSubscription cleans up both trackers and ibsocket."""
        client = TWSClient("127.0.0.1", 7497, 1)

        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True
        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        mock_quote_tracker = MagicMock()
        mock_bars_tracker = MagicMock()
        client._TWSClient__quote_tracker = mock_quote_tracker  # type: ignore[attr-defined]
        client._TWSClient__bars_tracker = mock_bars_tracker  # type: ignore[attr-defined]

        client.cancelDataSubscription("stream_key")

        mock_quote_tracker.unsubscribe.assert_called_once_with("stream_key")
        mock_bars_tracker.unsubscribe.assert_called_once_with("stream_key")
        mock_ibsocket.remove_stream.assert_called_once_with("stream_key")


class TestBrokerStreams:
    """Test broker data stream subscription/cancellation."""

    def test_order_stream_registers_and_triggers_snapshot(self) -> None:
        """reqOrdersStream sets up callback and requests initial data."""
        client = TWSClient("127.0.0.1", 7497, 1)

        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True

        mock_order_tracker = MagicMock()
        mock_order_tracker.create_stream_hook = MagicMock(return_value="orders_key")
        mock_ibsocket.order_tracker = mock_order_tracker
        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        async def callback(order: Any) -> None:
            pass

        async def on_error(err: Any) -> None:
            pass

        key = client.reqOrdersStream(callback, on_error)

        assert key == "orders_key"
        mock_order_tracker.create_stream_hook.assert_called_once()
        mock_ibsocket.reqOpenOrders.assert_called_once()  # Initial snapshot

    def test_position_stream_registers_and_triggers_snapshot(self) -> None:
        """reqPositionsStream sets up callback and requests initial data."""
        client = TWSClient("127.0.0.1", 7497, 1)

        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True

        mock_position_tracker = MagicMock()
        mock_position_tracker.create_stream_hook = MagicMock(
            return_value="positions_key"
        )
        mock_ibsocket.position_tracker = mock_position_tracker
        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        async def callback(pos: Any) -> None:
            pass

        async def on_error(err: Any) -> None:
            pass

        key = client.reqPositionsStream(callback, on_error)

        assert key == "positions_key"
        mock_position_tracker.create_stream_hook.assert_called_once()
        mock_ibsocket.reqPositions.assert_called_once()

    def test_account_stream_registers_and_triggers_snapshot(self) -> None:
        """reqAccountStream sets up callback and requests initial data."""
        client = TWSClient("127.0.0.1", 7497, 1)

        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True

        mock_account_tracker = MagicMock()
        mock_account_tracker.create_stream_hook = MagicMock(return_value="account_key")
        mock_ibsocket.account_tracker = mock_account_tracker
        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        async def callback(acct: Any) -> None:
            pass

        async def on_error(err: Any) -> None:
            pass

        key = client.reqAccountStream(callback, on_error)

        assert key == "account_key"
        mock_account_tracker.create_stream_hook.assert_called_once()
        mock_ibsocket.reqAccountSummary.assert_called_once()

    def test_execution_stream_registers_and_triggers_snapshot(self) -> None:
        """reqExecutionsStream sets up callback and requests initial data."""
        client = TWSClient("127.0.0.1", 7497, 1)

        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True

        mock_execution_tracker = MagicMock()
        mock_execution_tracker.create_stream_hook = MagicMock(return_value="exec_key")
        mock_ibsocket.execution_tracker = mock_execution_tracker
        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        async def callback(exec_: Any) -> None:
            pass

        async def on_error(err: Any) -> None:
            pass

        key = client.reqExecutionsStream(callback, on_error)

        assert key == "exec_key"
        mock_execution_tracker.create_stream_hook.assert_called_once()
        mock_ibsocket.reqExecutions.assert_called_once()

    def test_cancel_broker_stream_removes_from_all_trackers(self) -> None:
        """cancelBrokerStream cleans up all 4 broker trackers."""
        client = TWSClient("127.0.0.1", 7497, 1)

        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True

        mock_order_tracker = MagicMock()
        mock_position_tracker = MagicMock()
        mock_account_tracker = MagicMock()
        mock_execution_tracker = MagicMock()

        mock_ibsocket.order_tracker = mock_order_tracker
        mock_ibsocket.position_tracker = mock_position_tracker
        mock_ibsocket.account_tracker = mock_account_tracker
        mock_ibsocket.execution_tracker = mock_execution_tracker
        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        client.cancelBrokerStream("broker_key")

        mock_order_tracker.remove_stream_hook.assert_called_once_with("broker_key")
        mock_position_tracker.remove_stream_hook.assert_called_once_with("broker_key")
        mock_account_tracker.remove_stream_hook.assert_called_once_with("broker_key")
        mock_execution_tracker.remove_stream_hook.assert_called_once_with("broker_key")


# =============================================================================
# ERROR HANDLING
# =============================================================================


class TestErrorHandling:
    """Test timeout and error scenarios."""

    @pytest.mark.asyncio
    async def test_timeout_raises_timeout_error(self) -> None:
        """Request that doesn't complete within timeout raises TimeoutError."""
        client = TWSClient("127.0.0.1", 7497, 1, timeout=0.05)

        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True
        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        # Mock contract_tracker.get_descriptions to raise TimeoutError
        mock_tracker = MagicMock()
        mock_tracker.get_descriptions = AsyncMock(
            side_effect=asyncio.TimeoutError("Timeout waiting for TWS response")
        )
        client._TWSClient__contract_tracker = mock_tracker  # type: ignore[attr-defined]

        with pytest.raises(asyncio.TimeoutError):
            await client.reqMatchingSymbols("AAPL")


# =============================================================================
# ORDER SUBMISSION (_submit_order internal logic)
# =============================================================================


class TestSubmitOrder:
    """Test _submit_order - the core order modification/placement logic.

    This method handles 3 resolution paths:
    1. New order (orderId == 0) → use next_order_id
    2. Explicit orderId > 0 → modify existing order
    3. OCA reconciliation → find by OCA group+type+action

    Critical invariants:
    - Immutable fields (conId, exchange, parentId) cannot change
    - Only lmtPrice, auxPrice, totalQuantity are copied to existing orders
    - tif is cleared for existing orders
    - transmit forced True for existing orders
    - No-op detection: skip TWS call if no fields changed
    """

    def _make_client_with_ibsocket(self) -> tuple[TWSClient, MagicMock]:
        """Create TWSClient with mocked IBSocket."""
        client = TWSClient("127.0.0.1", 7497, 1, timeout=5.0)
        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True
        mock_ibsocket.order_tracker = MagicMock()
        mock_ibsocket.order_tracker.next_order_id = 100
        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]
        return client, mock_ibsocket

    def test_new_order_gets_next_available_id(self) -> None:
        """New order (orderId=0) assigned from order_tracker.next_order_id."""
        client, mock_ibsocket = self._make_client_with_ibsocket()
        mock_ibsocket.order_tracker.find_tracked_order.return_value = None
        mock_ibsocket.order_tracker.next_order_id = 42

        contract = Contract()
        contract.conId = 265598
        contract.symbol = "AAPL"

        order = Order()
        order.orderId = 0
        order.orderType = "LMT"
        order.lmtPrice = 150.0

        order_id, placed = client._submit_order(contract, order, transmit=True)

        assert order_id == 42
        assert placed is True
        mock_ibsocket.placeOrder.assert_called_once()
        call_args = mock_ibsocket.placeOrder.call_args
        assert call_args[0][0] == 42  # orderId
        assert call_args[0][2].transmit is True  # order.transmit preserved

    def test_explicit_order_id_reuses_existing_order(self) -> None:
        """Explicit orderId > 0 found in tracker → modifies existing order."""
        client, mock_ibsocket = self._make_client_with_ibsocket()

        # Setup existing tracked order
        existing_contract = Contract()
        existing_contract.conId = 265598
        existing_contract.exchange = "SMART"

        existing_order = Order()
        existing_order.orderId = 55
        existing_order.orderType = "LMT"
        existing_order.lmtPrice = 145.0
        existing_order.auxPrice = 0.0
        existing_order.totalQuantity = Decimal("10")
        existing_order.tif = "GTC"
        existing_order.transmit = False  # staged

        tracked = MagicMock()
        tracked.orderId = 55
        tracked.contract = existing_contract
        tracked.clone_order.return_value = existing_order

        mock_ibsocket.order_tracker.find_tracked_order.return_value = tracked

        # Submit modification with new price
        new_contract = Contract()
        new_contract.conId = 265598

        new_order = Order()
        new_order.orderId = 55
        new_order.orderType = "LMT"
        new_order.lmtPrice = 148.0  # Changed price

        order_id, placed = client._submit_order(new_contract, new_order)

        assert order_id == 55
        assert placed is True
        mock_ibsocket.placeOrder.assert_called_once()
        call_args = mock_ibsocket.placeOrder.call_args
        submitted_order = call_args[0][2]
        assert submitted_order.lmtPrice == 148.0  # New price applied
        assert submitted_order.transmit is True  # Forced True for existing
        assert submitted_order.tif == ""  # Cleared for existing orders

    def test_oca_reconciliation_finds_existing_order(self) -> None:
        """Order with OCA group finds existing order by type+action match."""
        client, mock_ibsocket = self._make_client_with_ibsocket()

        # Setup existing tracked order found via OCA
        existing_contract = Contract()
        existing_contract.conId = 265598
        existing_contract.exchange = "SMART"

        existing_order = Order()
        existing_order.orderId = 77
        existing_order.orderType = "STP"
        existing_order.action = "SELL"
        existing_order.auxPrice = 140.0
        existing_order.lmtPrice = 0.0
        existing_order.totalQuantity = Decimal("5")
        existing_order.ocaGroup = "brackets_123@1704067200000"

        tracked = MagicMock()
        tracked.orderId = 77
        tracked.contract = existing_contract
        tracked.clone_order.return_value = existing_order

        mock_ibsocket.order_tracker.find_tracked_order.return_value = tracked

        # Submit with OCA group (orderId=0 but find via OCA)
        new_contract = Contract()
        new_contract.conId = 265598

        new_order = Order()
        new_order.orderId = 0  # No explicit ID
        new_order.orderType = "STP"
        new_order.action = "SELL"
        new_order.auxPrice = 138.0  # New stop price
        new_order.ocaGroup = "brackets_123"

        order_id, placed = client._submit_order(new_contract, new_order)

        assert order_id == 77  # Found existing order
        assert placed is True
        mock_ibsocket.placeOrder.assert_called_once()

    def test_immutable_field_guard_conid_change_rejected(self) -> None:
        """Cannot change conId when modifying existing order."""
        client, mock_ibsocket = self._make_client_with_ibsocket()

        existing_contract = Contract()
        existing_contract.conId = 265598  # Original conId

        existing_order = Order()
        existing_order.orderId = 55

        tracked = MagicMock()
        tracked.orderId = 55
        tracked.contract = existing_contract
        tracked.clone_order.return_value = existing_order

        mock_ibsocket.order_tracker.find_tracked_order.return_value = tracked

        # Try to change conId
        new_contract = Contract()
        new_contract.conId = 999999  # Different conId

        new_order = Order()
        new_order.orderId = 55

        with pytest.raises(AssertionError, match="Cannot change contract"):
            client._submit_order(new_contract, new_order)

    def test_immutable_field_guard_exchange_change_rejected(self) -> None:
        """Cannot change exchange when modifying existing order."""
        client, mock_ibsocket = self._make_client_with_ibsocket()

        existing_contract = Contract()
        existing_contract.conId = 265598
        existing_contract.exchange = "SMART"  # Original exchange

        existing_order = Order()
        existing_order.orderId = 55

        tracked = MagicMock()
        tracked.orderId = 55
        tracked.contract = existing_contract
        tracked.clone_order.return_value = existing_order

        mock_ibsocket.order_tracker.find_tracked_order.return_value = tracked

        # Try to change exchange
        new_contract = Contract()
        new_contract.conId = 265598
        new_contract.exchange = "NASDAQ"  # Different exchange

        new_order = Order()
        new_order.orderId = 55

        with pytest.raises(AssertionError, match="Cannot change exchange"):
            client._submit_order(new_contract, new_order)

    def test_noop_detection_skips_tws_call(self) -> None:
        """No TWS call when no modifiable fields changed."""
        client, mock_ibsocket = self._make_client_with_ibsocket()

        existing_contract = Contract()
        existing_contract.conId = 265598
        existing_contract.exchange = "SMART"

        existing_order = Order()
        existing_order.orderId = 55
        existing_order.lmtPrice = 150.0
        existing_order.auxPrice = 0.0
        existing_order.totalQuantity = Decimal("10")

        tracked = MagicMock()
        tracked.orderId = 55
        tracked.contract = existing_contract
        tracked.clone_order.return_value = existing_order

        mock_ibsocket.order_tracker.find_tracked_order.return_value = tracked

        # Submit with same values - no change
        new_contract = Contract()
        new_contract.conId = 265598

        new_order = Order()
        new_order.orderId = 55
        new_order.lmtPrice = 150.0  # Same price
        new_order.auxPrice = 0.0  # Same aux
        new_order.totalQuantity = Decimal("10")  # Same qty

        order_id, placed = client._submit_order(new_contract, new_order)

        assert order_id == 55
        assert placed is False  # No-op detected
        mock_ibsocket.placeOrder.assert_not_called()

    def test_selective_field_copy_ignores_unset_values(self) -> None:
        """Only copies fields that are set (not UNSET_DOUBLE/UNSET_DECIMAL)."""
        from ibapi.const import UNSET_DECIMAL, UNSET_DOUBLE

        client, mock_ibsocket = self._make_client_with_ibsocket()

        existing_contract = Contract()
        existing_contract.conId = 265598
        existing_contract.exchange = "SMART"

        existing_order = Order()
        existing_order.orderId = 55
        existing_order.lmtPrice = 150.0
        existing_order.auxPrice = 145.0  # Has stop price
        existing_order.totalQuantity = Decimal("10")

        tracked = MagicMock()
        tracked.orderId = 55
        tracked.contract = existing_contract
        tracked.clone_order.return_value = existing_order

        mock_ibsocket.order_tracker.find_tracked_order.return_value = tracked

        # Submit with lmtPrice changed but auxPrice/totalQuantity unset
        new_contract = Contract()
        new_contract.conId = 265598

        new_order = Order()
        new_order.orderId = 55
        new_order.lmtPrice = 155.0  # Changed
        new_order.auxPrice = UNSET_DOUBLE  # Unset - should not change existing
        new_order.totalQuantity = UNSET_DECIMAL  # Unset - should not change existing

        order_id, placed = client._submit_order(new_contract, new_order)

        assert order_id == 55
        assert placed is True
        call_args = mock_ibsocket.placeOrder.call_args
        submitted_order = call_args[0][2]
        assert submitted_order.lmtPrice == 155.0  # Changed
        assert submitted_order.auxPrice == 145.0  # Preserved
        assert submitted_order.totalQuantity == Decimal("10")  # Preserved

    def test_forces_transmit_true_for_existing_orders(self) -> None:
        """Existing orders always transmitted (override staged orders)."""
        client, mock_ibsocket = self._make_client_with_ibsocket()

        existing_contract = Contract()
        existing_contract.conId = 265598
        existing_contract.exchange = "SMART"

        existing_order = Order()
        existing_order.orderId = 55
        existing_order.lmtPrice = 150.0
        existing_order.transmit = False  # Originally staged

        tracked = MagicMock()
        tracked.orderId = 55
        tracked.contract = existing_contract
        tracked.clone_order.return_value = existing_order

        mock_ibsocket.order_tracker.find_tracked_order.return_value = tracked

        new_contract = Contract()
        new_contract.conId = 265598

        new_order = Order()
        new_order.orderId = 55
        new_order.lmtPrice = 155.0  # Change price
        new_order.transmit = False  # Request staged (should be overridden)

        order_id, placed = client._submit_order(new_contract, new_order, transmit=False)

        assert placed is True
        call_args = mock_ibsocket.placeOrder.call_args
        submitted_order = call_args[0][2]
        assert submitted_order.transmit is True  # Forced to True


# =============================================================================
# BROKER SNAPSHOTS (reqOpenOrders representative)
# =============================================================================


class TestBrokerSnapshots:
    """Test broker snapshot methods - reqOpenOrders as representative pattern."""

    @pytest.mark.asyncio
    async def test_triggers_snapshot_and_awaits_completion(self) -> None:
        """reqOpenOrders triggers IBSocket snapshot and awaits tracker."""
        client = TWSClient("127.0.0.1", 7497, 1, timeout=5.0)

        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True

        tracked1 = MagicMock()
        tracked1.orderId = 1
        tracked2 = MagicMock()
        tracked2.orderId = 2

        mock_order_tracker = MagicMock()
        mock_order_tracker.all_orders = AsyncMock(return_value=[tracked1, tracked2])
        mock_ibsocket.order_tracker = mock_order_tracker
        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        result = await client.reqOpenOrders()

        # Verify IBSocket method called
        mock_ibsocket.reqOpenOrders.assert_called_once()
        # Verify tracker awaited
        mock_order_tracker.all_orders.assert_awaited_once_with(timeout=5.0)
        # Verify returns tracker result
        assert len(result) == 2
        assert result[0].orderId == 1


# =============================================================================
# DATAFEED SNAPSHOTS (reqQuoteSnapshot representative)
# =============================================================================


class TestDatafeedSnapshots:
    """Test datafeed snapshot methods - reqQuoteSnapshot as representative."""

    @pytest.mark.asyncio
    async def test_delegates_to_quote_tracker(self) -> None:
        """reqQuoteSnapshot delegates to quote_tracker.request."""
        client = TWSClient("127.0.0.1", 7497, 1, timeout=5.0)

        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True

        # Mock return value with expected attributes
        mock_quote = MagicMock()
        mock_quote.s = "ok"
        mock_quote.n = "AAPL"

        mock_quote_tracker = MagicMock()
        mock_quote_tracker.request = AsyncMock(return_value=mock_quote)
        client._TWSClient__quote_tracker = mock_quote_tracker  # type: ignore[attr-defined]
        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]

        # Use plain MagicMock for contract since we only need it as an argument
        contract = MagicMock()

        result = await client.reqQuoteSnapshot(contract)

        mock_quote_tracker.request.assert_awaited_once()
        call_args = mock_quote_tracker.request.call_args
        assert call_args[0][0] == contract
        assert result.s == "ok"
        assert result.n == "AAPL"
