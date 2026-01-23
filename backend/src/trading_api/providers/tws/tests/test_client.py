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
from unittest.mock import AsyncMock, MagicMock, patch

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
        """TWSClient.cancelOrder delegates to order_tracker.cancelOrder."""
        client = TWSClient("127.0.0.1", 7497, 1)

        cancelled = MagicMock()
        cancelled.orderId = 100
        cancelled.orderState.status = "Cancelled"

        mock_order_tracker = MagicMock()
        mock_order_tracker.cancelOrder = AsyncMock(return_value=cancelled)
        client._TWSClient__order_tracker = mock_order_tracker  # type: ignore[attr-defined]

        result = await client.cancelOrder(100)

        mock_order_tracker.cancelOrder.assert_called_once_with(100, timeout=10.0)
        assert result.orderId == 100

    @pytest.mark.asyncio
    async def test_raises_for_nonexistent_order(self) -> None:
        """Cannot cancel order that doesn't exist in tracker."""
        client = TWSClient("127.0.0.1", 7497, 1)

        mock_order_tracker = MagicMock()
        mock_order_tracker.cancelOrder = AsyncMock(
            side_effect=KeyError("Order not found")
        )
        client._TWSClient__order_tracker = mock_order_tracker  # type: ignore[attr-defined]

        with pytest.raises(KeyError):
            await client.cancelOrder(999)


class TestPlaceOcaGroup:
    """Test placeOcaGroup - delegates to OrderTracker.placeOcaGroup."""

    @pytest.mark.asyncio
    async def test_empty_orders_returns_empty(self) -> None:
        """Empty orders list delegates to order_tracker and returns empty."""
        client = TWSClient("127.0.0.1", 7497, 1)

        mock_order_tracker = MagicMock()
        mock_order_tracker.placeOcaGroup = AsyncMock(return_value=[])
        client._TWSClient__order_tracker = mock_order_tracker  # type: ignore[attr-defined]

        contract = Contract()
        contract.symbol = "AAPL"

        result = await client.placeOcaGroup(contract, [], "brackets_oca")

        assert result == []
        mock_order_tracker.placeOcaGroup.assert_called_once()

    @pytest.mark.asyncio
    async def test_delegates_to_order_tracker(self) -> None:
        """TWSClient.placeOcaGroup delegates to order_tracker.placeOcaGroup."""
        client = TWSClient("127.0.0.1", 7497, 1)

        tracked1, tracked2 = MagicMock(orderId=100), MagicMock(orderId=101)
        mock_order_tracker = MagicMock()
        mock_order_tracker.placeOcaGroup = AsyncMock(return_value=[tracked1, tracked2])
        client._TWSClient__order_tracker = mock_order_tracker  # type: ignore[attr-defined]

        order1 = Order()
        order1.action = "SELL"
        order1.orderType = "STP"

        order2 = Order()
        order2.action = "SELL"
        order2.orderType = "LMT"

        contract = Contract()
        contract.symbol = "AAPL"

        result = await client.placeOcaGroup(
            contract, [order1, order2], "brackets_oca", oca_type=2, timeout=15.0
        )

        assert result == [tracked1, tracked2]
        mock_order_tracker.placeOcaGroup.assert_called_once_with(
            contract, [order1, order2], "brackets_oca", 2, timeout=15.0
        )

    @pytest.mark.asyncio
    async def test_uses_default_timeout(self) -> None:
        """Uses client default timeout when not specified."""
        client = TWSClient("127.0.0.1", 7497, 1, timeout=25.0)

        mock_order_tracker = MagicMock()
        mock_order_tracker.placeOcaGroup = AsyncMock(return_value=[])
        client._TWSClient__order_tracker = mock_order_tracker  # type: ignore[attr-defined]

        contract = Contract()
        await client.placeOcaGroup(contract, [], "brackets_oca")

        mock_order_tracker.placeOcaGroup.assert_called_once_with(
            contract, [], "brackets_oca", 1, timeout=25.0
        )


class TestPlaceOrderGroup:
    """Test placeOrderGroup - delegates to OrderTracker.placeOrderGroup."""

    @pytest.mark.asyncio
    async def test_parent_only_delegates_to_order_tracker(self) -> None:
        """Parent without children delegates to order_tracker."""
        client = TWSClient("127.0.0.1", 7497, 1)

        parent_tracked = MagicMock(orderId=100)
        mock_order_tracker = MagicMock()
        mock_order_tracker.placeOrderGroup = AsyncMock(
            return_value=(parent_tracked, [])
        )
        client._TWSClient__order_tracker = mock_order_tracker  # type: ignore[attr-defined]

        parent = Order()
        parent.action = "BUY"
        parent.totalQuantity = Decimal("100")
        parent.orderType = "LMT"
        parent.lmtPrice = 150.00

        contract = Contract()
        contract.symbol = "AAPL"
        contract.conId = 265598

        result_parent, result_children = await client.placeOrderGroup(
            contract, parent, children=[]
        )

        assert result_parent.orderId == 100
        assert result_children == []
        mock_order_tracker.placeOrderGroup.assert_called_once()

    @pytest.mark.asyncio
    async def test_parent_with_children_delegates_to_order_tracker(self) -> None:
        """Parent + children delegates to order_tracker.placeOrderGroup."""
        client = TWSClient("127.0.0.1", 7497, 1)

        parent_tracked = MagicMock(orderId=100)
        child1_tracked = MagicMock(orderId=101)
        child2_tracked = MagicMock(orderId=102)

        mock_order_tracker = MagicMock()
        mock_order_tracker.placeOrderGroup = AsyncMock(
            return_value=(parent_tracked, [child1_tracked, child2_tracked])
        )
        client._TWSClient__order_tracker = mock_order_tracker  # type: ignore[attr-defined]

        parent = Order()
        parent.action = "BUY"
        parent.orderType = "LMT"

        stop_loss = Order()
        stop_loss.action = "SELL"
        stop_loss.orderType = "STP"

        take_profit = Order()
        take_profit.action = "SELL"
        take_profit.orderType = "LMT"

        contract = Contract()
        contract.symbol = "AAPL"

        result_parent, result_children = await client.placeOrderGroup(
            contract, parent, children=[stop_loss, take_profit]
        )

        assert result_parent.orderId == 100
        assert len(result_children) == 2
        mock_order_tracker.placeOrderGroup.assert_called_once_with(
            contract, parent, [stop_loss, take_profit], timeout=10.0
        )

    @pytest.mark.asyncio
    async def test_uses_custom_timeout(self) -> None:
        """Uses custom timeout when specified."""
        client = TWSClient("127.0.0.1", 7497, 1, timeout=5.0)

        mock_order_tracker = MagicMock()
        mock_order_tracker.placeOrderGroup = AsyncMock(
            return_value=(MagicMock(orderId=100), [])
        )
        client._TWSClient__order_tracker = mock_order_tracker  # type: ignore[attr-defined]

        parent = Order()
        contract = Contract()

        await client.placeOrderGroup(contract, parent, children=[], timeout=20.0)

        mock_order_tracker.placeOrderGroup.assert_called_once_with(
            contract, parent, [], timeout=20.0
        )


class TestPlaceWhatifOrder:
    """Test placeWhatifOrder - delegates to OrderTracker.placeWhatifOrder."""

    @pytest.mark.asyncio
    async def test_delegates_to_order_tracker(self) -> None:
        """TWSClient.placeWhatifOrder delegates to order_tracker.placeWhatifOrder."""
        client = TWSClient("127.0.0.1", 7497, 1)

        whatif_result = MagicMock(orderId=100)
        mock_order_tracker = MagicMock()
        mock_order_tracker.placeWhatifOrder = AsyncMock(return_value=whatif_result)
        client._TWSClient__order_tracker = mock_order_tracker  # type: ignore[attr-defined]

        order = Order()
        order.action = "BUY"
        order.totalQuantity = Decimal("100")
        order.orderType = "LMT"
        order.lmtPrice = 150.00

        contract = Contract()
        contract.symbol = "AAPL"
        contract.conId = 265598

        result = await client.placeWhatifOrder(contract, order)

        assert result.orderId == 100
        mock_order_tracker.placeWhatifOrder.assert_called_once_with(
            contract, order, timeout=10.0
        )

    @pytest.mark.asyncio
    async def test_uses_custom_timeout(self) -> None:
        """Uses custom timeout when specified."""
        client = TWSClient("127.0.0.1", 7497, 1, timeout=5.0)

        mock_order_tracker = MagicMock()
        mock_order_tracker.placeWhatifOrder = AsyncMock(
            return_value=MagicMock(orderId=100)
        )
        client._TWSClient__order_tracker = mock_order_tracker  # type: ignore[attr-defined]

        order = Order()
        contract = Contract()

        await client.placeWhatifOrder(contract, order, timeout=30.0)

        mock_order_tracker.placeWhatifOrder.assert_called_once_with(
            contract, order, timeout=30.0
        )


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
        """cancelDataSubscription cleans up both trackers."""
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


class TestBrokerStreams:
    """Test broker data stream subscription/cancellation."""

    def test_order_stream_registers_and_triggers_snapshot(self) -> None:
        """reqOrdersStream sets up callback with order_tracker."""
        client = TWSClient("127.0.0.1", 7497, 1)

        mock_order_tracker = MagicMock()
        mock_order_tracker.create_stream_hook = MagicMock(return_value="orders_key")
        # order_tracker is now on TWSClient, not IBSocket
        client._TWSClient__order_tracker = mock_order_tracker  # type: ignore[attr-defined]

        async def callback(order: Any) -> None:
            pass

        async def on_error(err: Any) -> None:
            pass

        key = client.reqOrdersStream(callback, on_error)

        assert key == "orders_key"
        mock_order_tracker.create_stream_hook.assert_called_once()

    def test_position_stream_registers_and_triggers_snapshot(self) -> None:
        """reqPositionsStream sets up callback and requests initial data."""
        client = TWSClient("127.0.0.1", 7497, 1)

        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True

        mock_position_tracker = MagicMock()
        mock_position_tracker.create_stream_hook = MagicMock(
            return_value="positions_key"
        )
        # position_tracker is now on TWSClient, not IBSocket
        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]
        client._TWSClient__position_tracker = mock_position_tracker  # type: ignore[attr-defined]

        async def callback(pos: Any) -> None:
            pass

        async def on_error(err: Any) -> None:
            pass

        key = client.reqPositionsStream(callback, on_error)

        assert key == "positions_key"
        mock_position_tracker.create_stream_hook.assert_called_once()

    def test_account_stream_registers_and_triggers_snapshot(self) -> None:
        """reqAccountStream sets up callback and requests initial data."""
        client = TWSClient("127.0.0.1", 7497, 1)

        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True

        mock_account_tracker = MagicMock()
        mock_account_tracker.create_stream_hook = MagicMock(return_value="account_key")
        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]
        # account_tracker is now on TWSClient, not IBSocket
        client._TWSClient__account_tracker = mock_account_tracker  # type: ignore[attr-defined]

        async def callback(acct: Any) -> None:
            pass

        async def on_error(err: Any) -> None:
            pass

        key = client.reqAccountStream(callback, on_error)

        assert key == "account_key"
        mock_account_tracker.create_stream_hook.assert_called_once()
        # Note: ensure_summary_requested is called internally by create_stream_hook

    def test_execution_stream_registers_and_triggers_snapshot(self) -> None:
        """reqExecutionsStream sets up callback and requests initial data."""
        client = TWSClient("127.0.0.1", 7497, 1)

        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True

        mock_execution_tracker = MagicMock()
        mock_execution_tracker.create_stream_hook = MagicMock(return_value="exec_key")
        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]
        # execution_tracker is now on TWSClient, not IBSocket
        client._TWSClient__execution_tracker = mock_execution_tracker  # type: ignore[attr-defined]

        async def callback(exec_: Any) -> None:
            pass

        async def on_error(err: Any) -> None:
            pass

        key = client.reqExecutionsStream(callback, on_error)

        assert key == "exec_key"
        mock_execution_tracker.create_stream_hook.assert_called_once()

    def test_cancel_broker_stream_removes_from_all_trackers(self) -> None:
        """cancelBrokerStream cleans up all 4 broker trackers."""
        client = TWSClient("127.0.0.1", 7497, 1)

        mock_ibsocket = MagicMock()
        mock_ibsocket.running = True

        mock_order_tracker = MagicMock()
        mock_position_tracker = MagicMock()
        mock_account_tracker = MagicMock()
        mock_execution_tracker = MagicMock()

        client._TWSClient__ibsocket = mock_ibsocket  # type: ignore[attr-defined]
        # All trackers are now on TWSClient
        client._TWSClient__order_tracker = mock_order_tracker  # type: ignore[attr-defined]
        client._TWSClient__position_tracker = mock_position_tracker  # type: ignore[attr-defined]
        client._TWSClient__account_tracker = mock_account_tracker  # type: ignore[attr-defined]
        client._TWSClient__execution_tracker = mock_execution_tracker  # type: ignore[attr-defined]

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
# BROKER SNAPSHOTS (reqOpenOrders representative)
# =============================================================================


class TestBrokerSnapshots:
    """Test broker snapshot methods - reqOpenOrders as representative pattern."""

    @pytest.mark.asyncio
    async def test_triggers_snapshot_and_awaits_completion(self) -> None:
        """TWSClient.reqOpenOrders delegates to order_tracker.reqOpenOrders."""
        client = TWSClient("127.0.0.1", 7497, 1, timeout=5.0)

        tracked1 = MagicMock()
        tracked1.orderId = 1
        tracked2 = MagicMock()
        tracked2.orderId = 2

        mock_order_tracker = MagicMock()
        mock_order_tracker.reqOpenOrders = AsyncMock(return_value=[tracked1, tracked2])
        # order_tracker is now on TWSClient, not IBSocket
        client._TWSClient__order_tracker = mock_order_tracker  # type: ignore[attr-defined]

        result = await client.reqOpenOrders()

        # Verify order_tracker method called with default timeout
        mock_order_tracker.reqOpenOrders.assert_awaited_once_with(timeout=5.0)
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
