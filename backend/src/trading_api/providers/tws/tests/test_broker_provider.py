"""Tests for TWSBrokerProvider - BrokerCapability implementation.

Tests cover:
- Provider initialization and configuration
- Provider capabilities declaration
- Order operations: place_order, cancel_order, modify_order

Note: All tests mock TWSClient to avoid real TWS connections.
Note: PreOrder.symbol uses composite ticker format (e.g., "NASDAQ:AAPL").
"""

from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

import pytest
from ibapi.contract import Contract, ContractDetails
from ibapi.order import Order
from ibapi.order_state import OrderState

from trading_api.models.broker import (
    Brackets,
    OrderStatus,
    OrderType,
    ParentType,
    PlaceOrderResult,
    Position,
    PreOrder,
    Side,
)
from trading_api.models.exceptions import ProviderException
from trading_api.models.providers.tws_configs import TWSBrokerProviderConfig
from trading_api.providers.tws.broker_provider import (
    TWSBrokerProvider,
    _build_bracket_context_from_children,
    _group_and_map_tws_orders,
    _group_orders_by_bracket,
)
from trading_api.providers.tws.cached_contract import CachedContract
from trading_api.providers.tws.order_tracker import TrackedOrder


def _create_mock_contract(
    symbol: str = "AAPL",
    exchange: str = "SMART",
    primary_exchange: str = "NASDAQ",
    sec_type: str = "STK",
    con_id: int = 265598,
) -> Contract:
    """Create a mock TWS Contract for testing."""
    contract = Contract()
    contract.symbol = symbol
    contract.exchange = exchange
    contract.primaryExchange = primary_exchange
    contract.secType = sec_type
    contract.conId = con_id
    return contract


def _create_mock_order(
    action: str = "BUY",
    order_type: str = "MKT",
    total_quantity: Decimal = Decimal("100"),
    lmt_price: float = 0.0,
    aux_price: float = 0.0,
    filled_quantity: Decimal = Decimal("0"),
) -> Order:
    """Create a mock TWS Order for testing."""
    order = Order()
    order.action = action
    order.orderType = order_type
    order.totalQuantity = total_quantity
    order.lmtPrice = lmt_price
    order.auxPrice = aux_price
    order.filledQuantity = filled_quantity
    return order


def _create_mock_order_state(status: str = "Submitted") -> OrderState:
    """Create a mock TWS OrderState for testing."""
    order_state = OrderState()
    order_state.status = status
    return order_state


def _create_tracked_order(
    order_id: int,
    contract: Contract | None = None,
    order: Order | None = None,
    order_state: OrderState | None = None,
) -> TrackedOrder:
    """Create a TrackedOrder for testing."""
    return TrackedOrder(
        orderId=order_id,
        contract=contract or _create_mock_contract(),
        order=order or _create_mock_order(),
        orderState=order_state or _create_mock_order_state(),
        fills=[],
    )


def _create_mock_contract_details(
    contract: Contract | None = None,
    trading_hours: str | None = None,
    valid_exchanges: str = "SMART,NASDAQ",
    overnight_hours: str | None = None,
) -> CachedContract:
    """Create a mock CachedContract for req_ticker_details return value.

    Args:
        contract: Contract to embed (uses default if None)
        trading_hours: Trading hours string (defaults to 24h open market)
        valid_exchanges: Comma-separated list of valid exchanges (default: "SMART,NASDAQ")
        overnight_hours: Overnight trading hours string (for darkpool support)
    """
    from datetime import datetime
    from zoneinfo import ZoneInfo

    details = ContractDetails()
    details.contract = contract or _create_mock_contract()
    details.validExchanges = valid_exchanges
    details.timeZoneId = "US/Eastern"

    # Default to 24h trading (market open) unless specified
    if trading_hours is None:
        now = datetime.now(ZoneInfo("US/Eastern"))
        today_str = now.strftime("%Y%m%d")
        trading_hours = f"{today_str}:0000-{today_str}:2359"
    details.tradingHours = trading_hours

    return CachedContract.from_contract_details(
        details, overnight_hours=overnight_hours
    )


class TestBrokerProviderInitialization:
    """Test TWSBrokerProvider initialization and configuration."""

    def test_provider_default_config(self) -> None:
        """Test TWSBrokerProvider uses default config when none provided."""
        with patch("trading_api.providers.tws.broker_provider.TWSClient"):
            provider = TWSBrokerProvider()

        assert provider.config.host == "127.0.0.1"
        assert provider.config.port == 7497
        assert provider.config.client_id == 2  # Default broker client_id

    def test_provider_with_custom_config(self) -> None:
        """Test TWSBrokerProvider config is stored correctly."""
        config = TWSBrokerProviderConfig(host="192.168.1.1", port=4002, client_id=5)

        with patch("trading_api.providers.tws.broker_provider.TWSClient"):
            provider = TWSBrokerProvider(config=config)

        assert provider.config.host == "192.168.1.1"
        assert provider.config.port == 4002
        assert provider.config.client_id == 5

    def test_provider_capabilities(self) -> None:
        """Test provider capabilities declaration."""
        caps = TWSBrokerProvider.capabilities()

        assert len(caps) == 1
        assert caps[0].name == "broker"

    def test_provider_creates_tws_client(self) -> None:
        """Test provider creates TWSClient with config."""
        with patch("trading_api.providers.tws.broker_provider.TWSClient") as MockClient:
            config = TWSBrokerProviderConfig(host="10.0.0.1", port=4001, client_id=10)
            TWSBrokerProvider(config=config)

        MockClient.assert_called_once_with("10.0.0.1", 4001, 10)


class TestPlaceOrder:
    """Test TWSBrokerProvider.place_order()."""

    @pytest.fixture
    def mock_client(self) -> Mock:
        """Create mock TWSClient with AsyncMock methods."""
        mock = Mock()
        # req_ticker_details returns CachedContract
        contract_details = _create_mock_contract_details()
        mock.req_ticker_details = AsyncMock(return_value=contract_details)
        # placeOrderGroup returns (parent_tracked, children_tracked)
        mock.placeOrderGroup = AsyncMock(
            return_value=(_create_tracked_order(12345), [])
        )
        return mock

    @pytest.fixture
    def provider(self, mock_client: Mock) -> TWSBrokerProvider:
        """Create provider with mocked TWSClient."""
        with patch(
            "trading_api.providers.tws.broker_provider.TWSClient",
            return_value=mock_client,
        ):
            return TWSBrokerProvider(
                config=TWSBrokerProviderConfig(account_id="DU123456")
            )

    @pytest.mark.asyncio
    async def test_place_order_returns_order_id(
        self, provider: TWSBrokerProvider, mock_client: Mock
    ) -> None:
        """Test place_order returns PlaceOrderResult with order ID."""
        pre_order = PreOrder(
            symbol="NASDAQ:AAPL",
            side=Side.BUY,
            type=OrderType.MARKET,
            qty=100.0,
        )

        result = await provider.place_order(pre_order)

        assert isinstance(result, PlaceOrderResult)
        assert result.orderId == "12345"

    @pytest.mark.asyncio
    async def test_place_order_calls_cache_contracts(
        self, provider: TWSBrokerProvider, mock_client: Mock
    ) -> None:
        """Test place_order calls req_ticker_details with symbol."""
        pre_order = PreOrder(
            symbol="NASDAQ:AAPL",
            side=Side.BUY,
            type=OrderType.MARKET,
            qty=100.0,
        )

        await provider.place_order(pre_order)

        mock_client.req_ticker_details.assert_called_once()
        call_args = mock_client.req_ticker_details.call_args
        assert call_args[0][0] == "NASDAQ:AAPL"

    @pytest.mark.asyncio
    async def test_place_order_calls_place_order_group(
        self, provider: TWSBrokerProvider, mock_client: Mock
    ) -> None:
        """Test place_order calls placeOrderGroup with correct args."""
        pre_order = PreOrder(
            symbol="NASDAQ:AAPL",
            side=Side.BUY,
            type=OrderType.LIMIT,
            qty=100.0,
            limitPrice=150.00,
        )

        await provider.place_order(pre_order)

        mock_client.placeOrderGroup.assert_called_once()
        call_args = mock_client.placeOrderGroup.call_args

        # First arg is contract
        contract = call_args[0][0]
        assert isinstance(contract, Contract)

        # Second arg is parent order
        order = call_args[0][1]
        assert isinstance(order, Order)
        assert order.action == "BUY"
        assert order.orderType == "LMT"
        assert order.totalQuantity == Decimal("100")
        assert order.lmtPrice == 150.00

        # Third arg is children list (empty for simple order)
        children = call_args[0][2]
        assert children == []

    @pytest.mark.asyncio
    async def test_place_order_with_stop_order(
        self, provider: TWSBrokerProvider, mock_client: Mock
    ) -> None:
        """Test place_order correctly converts stop order."""
        pre_order = PreOrder(
            symbol="NASDAQ:AAPL",
            side=Side.SELL,
            type=OrderType.STOP,
            qty=50.0,
            stopPrice=140.00,
        )

        await provider.place_order(pre_order)

        call_args = mock_client.placeOrderGroup.call_args
        order = call_args[0][1]
        assert order.orderType == "STP"
        assert order.action == "SELL"
        assert order.auxPrice == 140.00


class TestPlaceOrderWithBrackets:
    """Test TWSBrokerProvider.place_order() with bracket orders."""

    @pytest.fixture
    def mock_client(self) -> Mock:
        """Create mock TWSClient with bracket order support."""
        mock = Mock()
        contract_details = _create_mock_contract_details()
        mock.req_ticker_details = AsyncMock(return_value=contract_details)
        mock.reqContractDetails = AsyncMock(return_value=[contract_details])

        # Parent + 2 children for full bracket
        parent_tracked = _create_tracked_order(100)
        sl_tracked = _create_tracked_order(
            101,
            order=_create_mock_order(action="SELL", order_type="STP", aux_price=145.0),
        )
        tp_tracked = _create_tracked_order(
            102,
            order=_create_mock_order(action="SELL", order_type="LMT", lmt_price=160.0),
        )
        mock.placeOrderGroup = AsyncMock(
            return_value=(parent_tracked, [sl_tracked, tp_tracked])
        )
        # Mock reqOpenOrders to return all tracked orders
        mock.reqOpenOrders = AsyncMock(
            return_value=[parent_tracked, sl_tracked, tp_tracked]
        )
        return mock

    @pytest.fixture
    def provider(self, mock_client: Mock) -> TWSBrokerProvider:
        """Create provider with mocked TWSClient."""
        with patch(
            "trading_api.providers.tws.broker_provider.TWSClient",
            return_value=mock_client,
        ):
            return TWSBrokerProvider()

    @pytest.mark.asyncio
    async def test_place_order_with_brackets_creates_children(
        self, provider: TWSBrokerProvider, mock_client: Mock
    ) -> None:
        """Test place_order with brackets passes child orders to placeOrderGroup."""
        pre_order = PreOrder(
            symbol="NASDAQ:AAPL",
            side=Side.BUY,
            type=OrderType.LIMIT,
            qty=100.0,
            limitPrice=150.00,
            stopLoss=145.00,
            takeProfit=160.00,
        )

        await provider.place_order(pre_order)

        call_args = mock_client.placeOrderGroup.call_args
        children = call_args[0][2]

        # Should have 2 child orders (stop loss + take profit)
        assert len(children) == 2

    @pytest.mark.asyncio
    async def test_place_order_with_brackets_returns_parent_id(
        self, provider: TWSBrokerProvider, mock_client: Mock
    ) -> None:
        """Test place_order with brackets returns parent order ID."""
        pre_order = PreOrder(
            symbol="NASDAQ:AAPL",
            side=Side.BUY,
            type=OrderType.LIMIT,
            qty=100.0,
            limitPrice=150.00,
            stopLoss=145.00,
            takeProfit=160.00,
        )

        result = await provider.place_order(pre_order)

        # Parent order ID returned
        assert result.orderId == "100"

    @pytest.mark.asyncio
    async def test_place_order_with_brackets_orders_retrievable(
        self, provider: TWSBrokerProvider, mock_client: Mock
    ) -> None:
        """Test placed bracket orders can be retrieved via get_orders."""
        pre_order = PreOrder(
            symbol="NASDAQ:AAPL",
            side=Side.BUY,
            type=OrderType.LIMIT,
            qty=100.0,
            limitPrice=150.00,
            stopLoss=145.00,
            takeProfit=160.00,
        )

        await provider.place_order(pre_order)

        # Retrieve orders via public API
        orders = await provider.get_orders()

        # Should have parent + 2 children (3 total)
        assert len(orders) == 3
        order_ids = {o.id for o in orders}
        assert "100" in order_ids  # Parent
        assert "101" in order_ids  # Stop loss child
        assert "102" in order_ids  # Take profit child

    @pytest.mark.asyncio
    async def test_place_order_with_stop_loss_only(
        self, provider: TWSBrokerProvider, mock_client: Mock
    ) -> None:
        """Test place_order with only stop loss creates one child."""
        # Reconfigure mock for single child
        parent_tracked = _create_tracked_order(200)
        sl_tracked = _create_tracked_order(201)
        mock_client.placeOrderGroup = AsyncMock(
            return_value=(parent_tracked, [sl_tracked])
        )

        pre_order = PreOrder(
            symbol="NASDAQ:AAPL",
            side=Side.BUY,
            type=OrderType.MARKET,
            qty=100.0,
            stopLoss=145.00,
        )

        await provider.place_order(pre_order)

        call_args = mock_client.placeOrderGroup.call_args
        children = call_args[0][2]
        assert len(children) == 1

    @pytest.mark.asyncio
    async def test_place_order_with_take_profit_only(
        self, provider: TWSBrokerProvider, mock_client: Mock
    ) -> None:
        """Test place_order with only take profit creates one child."""
        parent_tracked = _create_tracked_order(300)
        tp_tracked = _create_tracked_order(301)
        mock_client.placeOrderGroup = AsyncMock(
            return_value=(parent_tracked, [tp_tracked])
        )

        pre_order = PreOrder(
            symbol="NASDAQ:AAPL",
            side=Side.BUY,
            type=OrderType.MARKET,
            qty=100.0,
            takeProfit=160.00,
        )

        await provider.place_order(pre_order)

        call_args = mock_client.placeOrderGroup.call_args
        children = call_args[0][2]
        assert len(children) == 1


class TestModifyOrder:
    """Test TWSBrokerProvider.modify_order()."""

    @pytest.fixture
    def mock_client(self) -> Mock:
        """Create mock TWSClient with AsyncMock methods."""
        mock = Mock()
        contract_details = _create_mock_contract_details()
        mock.req_ticker_details = AsyncMock(return_value=contract_details)
        mock.reqContractDetails = AsyncMock(return_value=[contract_details])
        mock.placeOrderGroup = AsyncMock(
            return_value=(_create_tracked_order(12345), [])
        )
        return mock

    @pytest.fixture
    def provider(self, mock_client: Mock) -> TWSBrokerProvider:
        """Create provider with mocked TWSClient."""
        with patch(
            "trading_api.providers.tws.broker_provider.TWSClient",
            return_value=mock_client,
        ):
            return TWSBrokerProvider(
                config=TWSBrokerProviderConfig(account_id="DU123456")
            )

    @pytest.mark.asyncio
    async def test_modify_order_uses_existing_order_id(
        self, provider: TWSBrokerProvider, mock_client: Mock
    ) -> None:
        """Test modify_order passes existing order ID to placeOrderGroup."""
        pre_order = PreOrder(
            symbol="NASDAQ:AAPL",
            side=Side.BUY,
            type=OrderType.LIMIT,
            qty=100.0,
            limitPrice=155.00,
        )

        await provider.modify_order("12345", pre_order)

        call_args = mock_client.placeOrderGroup.call_args
        parent_order = call_args[0][1]
        # Order should have the existing order ID set
        assert parent_order.orderId == 12345

    @pytest.mark.asyncio
    async def test_modify_order_updates_order(
        self, provider: TWSBrokerProvider, mock_client: Mock
    ) -> None:
        """Test modify_order updates the order via TWS."""
        # First place an order
        place_order = PreOrder(
            symbol="NASDAQ:AAPL",
            side=Side.BUY,
            type=OrderType.LIMIT,
            qty=100.0,
            limitPrice=150.00,
        )
        await provider.place_order(place_order)

        # Reconfigure mock for modify - returns updated tracked order
        modified_order = _create_mock_order(
            order_type="LMT", lmt_price=155.00, total_quantity=Decimal("100")
        )
        modified_tracked = _create_tracked_order(12345, order=modified_order)
        mock_client.placeOrderGroup = AsyncMock(return_value=(modified_tracked, []))
        # Mock reqOpenOrders to return the modified order
        mock_client.reqOpenOrders = AsyncMock(return_value=[modified_tracked])

        # Modify with new price
        modify_order = PreOrder(
            symbol="NASDAQ:AAPL",
            side=Side.BUY,
            type=OrderType.LIMIT,
            qty=100.0,
            limitPrice=155.00,
        )
        await provider.modify_order("12345", modify_order)

        # Verify order can be retrieved with updated price
        orders = await provider.get_orders()
        assert len(orders) == 1
        assert orders[0].id == "12345"
        assert orders[0].limitPrice == 155.00


class TestModifyOrderWithBrackets:
    """Test TWSBrokerProvider.modify_order() with bracket modifications."""

    @pytest.fixture
    def mock_client(self) -> Mock:
        """Create mock TWSClient for bracket modification."""
        mock = Mock()
        contract_details = _create_mock_contract_details()
        mock.req_ticker_details = AsyncMock(return_value=contract_details)
        mock.reqContractDetails = AsyncMock(return_value=[contract_details])

        parent_tracked = _create_tracked_order(100)
        sl_tracked = _create_tracked_order(103)  # New child IDs
        tp_tracked = _create_tracked_order(104)
        mock.placeOrderGroup = AsyncMock(
            return_value=(parent_tracked, [sl_tracked, tp_tracked])
        )
        # Mock reqOpenOrders to return all tracked orders
        mock.reqOpenOrders = AsyncMock(
            return_value=[parent_tracked, sl_tracked, tp_tracked]
        )
        return mock

    @pytest.fixture
    def provider(self, mock_client: Mock) -> TWSBrokerProvider:
        """Create provider with mocked TWSClient."""
        with patch(
            "trading_api.providers.tws.broker_provider.TWSClient",
            return_value=mock_client,
        ):
            return TWSBrokerProvider()

    @pytest.mark.asyncio
    async def test_modify_order_with_new_brackets(
        self, provider: TWSBrokerProvider, mock_client: Mock
    ) -> None:
        """Test modify_order with brackets creates new child orders."""
        pre_order = PreOrder(
            symbol="NASDAQ:AAPL",
            side=Side.BUY,
            type=OrderType.LIMIT,
            qty=100.0,
            limitPrice=150.00,
            stopLoss=140.00,  # New brackets
            takeProfit=165.00,
        )

        await provider.modify_order("100", pre_order)

        call_args = mock_client.placeOrderGroup.call_args
        parent = call_args[0][1]
        children = call_args[0][2]

        assert parent.orderId == 100
        assert len(children) == 2

        # New children can be retrieved via get_orders
        orders = await provider.get_orders()
        order_ids = {o.id for o in orders}
        assert "103" in order_ids
        assert "104" in order_ids


class TestCancelOrder:
    """Test TWSBrokerProvider.cancel_order()."""

    @pytest.fixture
    def mock_client(self) -> Mock:
        """Create mock TWSClient with cancelOrder."""
        mock = Mock()
        contract_details = _create_mock_contract_details()
        mock.reqContractDetails = AsyncMock(return_value=[contract_details])
        cancelled_tracked = _create_tracked_order(
            12345,
            order_state=_create_mock_order_state("Cancelled"),
        )
        mock.cancelOrder = AsyncMock(return_value=cancelled_tracked)
        # Mock reqOpenOrders to return cancelled order
        mock.reqOpenOrders = AsyncMock(return_value=[cancelled_tracked])
        return mock

    @pytest.fixture
    def provider(self, mock_client: Mock) -> TWSBrokerProvider:
        """Create provider with mocked TWSClient."""
        with patch(
            "trading_api.providers.tws.broker_provider.TWSClient",
            return_value=mock_client,
        ):
            return TWSBrokerProvider()

    @pytest.mark.asyncio
    async def test_cancel_order_calls_tws_client(
        self, provider: TWSBrokerProvider, mock_client: Mock
    ) -> None:
        """Test cancel_order calls TWSClient.cancelOrder."""
        await provider.cancel_order("12345")

        mock_client.cancelOrder.assert_called_once_with(12345)

    @pytest.mark.asyncio
    async def test_cancel_order_returns_cancelled_status(
        self, provider: TWSBrokerProvider, mock_client: Mock
    ) -> None:
        """Test cancelled order has CANCELED status when retrieved."""
        await provider.cancel_order("12345")

        # Retrieve orders via public API
        orders = await provider.get_orders()
        assert len(orders) == 1
        assert orders[0].id == "12345"
        assert orders[0].status == OrderStatus.CANCELED


class TestResolveTradingContract:
    """Test TWSBrokerProvider._resolve_trading_contract() session/darkpool selection."""

    @pytest.fixture
    def mock_client(self) -> Mock:
        """Create mock TWSClient."""
        return Mock()

    @pytest.fixture
    def provider(self, mock_client: Mock) -> TWSBrokerProvider:
        """Create provider with mocked TWSClient."""
        with patch(
            "trading_api.providers.tws.broker_provider.TWSClient",
            return_value=mock_client,
        ):
            return TWSBrokerProvider()

    @pytest.mark.asyncio
    async def test_uses_session_when_market_open(
        self, provider: TWSBrokerProvider, mock_client: Mock
    ) -> None:
        """Test uses SMART exchange when market is open."""
        from datetime import datetime
        from zoneinfo import ZoneInfo

        # Create contract with market open (24h trading) and OVERNIGHT available
        contract = _create_mock_contract(exchange="SMART")
        now = datetime.now(ZoneInfo("US/Eastern"))
        today_str = now.strftime("%Y%m%d")
        session_details = _create_mock_contract_details(
            contract=contract,
            trading_hours=f"{today_str}:0000-{today_str}:2359",
            valid_exchanges="SMART,NASDAQ,OVERNIGHT",
            overnight_hours=f"{today_str}:0000-{today_str}:2359",  # darkpool also open
        )

        mock_client.req_ticker_details = AsyncMock(return_value=session_details)

        result = await provider._resolve_trading_contract("NASDAQ:AAPL")

        assert result.exchange == "SMART"

    @pytest.mark.asyncio
    async def test_uses_darkpool_when_closed_and_available(
        self, provider: TWSBrokerProvider, mock_client: Mock
    ) -> None:
        """Test uses OVERNIGHT exchange when session closed and darkpool available."""
        from datetime import datetime
        from zoneinfo import ZoneInfo

        # Create contract with session CLOSED but OVERNIGHT available and open
        contract = _create_mock_contract(exchange="SMART")
        now = datetime.now(ZoneInfo("US/Eastern"))
        today_str = now.strftime("%Y%m%d")
        session_details = _create_mock_contract_details(
            contract=contract,
            trading_hours="20260109:CLOSED",  # session closed
            valid_exchanges="SMART,NASDAQ,OVERNIGHT",
            overnight_hours=f"{today_str}:0000-{today_str}:2359",  # darkpool open
        )

        mock_client.req_ticker_details = AsyncMock(return_value=session_details)

        result = await provider._resolve_trading_contract("NASDAQ:AAPL")

        assert result.exchange == "OVERNIGHT"

    @pytest.mark.asyncio
    async def test_uses_session_when_closed_but_no_darkpool(
        self, provider: TWSBrokerProvider, mock_client: Mock
    ) -> None:
        """Test uses SMART exchange when market closed but no OVERNIGHT exchange available."""
        # Create contract with session CLOSED and no OVERNIGHT in validExchanges
        contract = _create_mock_contract(exchange="SMART")
        session_details = _create_mock_contract_details(
            contract=contract,
            trading_hours="20260109:CLOSED",
            valid_exchanges="SMART,NASDAQ",  # No OVERNIGHT available
        )

        mock_client.req_ticker_details = AsyncMock(return_value=session_details)

        result = await provider._resolve_trading_contract("NASDAQ:AAPL")

        # Should fall back to SMART
        assert result.exchange == "SMART"

    @pytest.mark.asyncio
    async def test_raises_when_contract_not_found(
        self, provider: TWSBrokerProvider, mock_client: Mock
    ) -> None:
        """Test raises ProviderException when req_ticker_details fails."""
        # Mock req_ticker_details to raise ProviderException (symbol not found)
        mock_client.req_ticker_details = AsyncMock(
            side_effect=ProviderException(
                code="PROVIDER_DATAFEED_SYMBOL_NOT_FOUND",
                message="Symbol not found: EXCHANGE:INVALID",
                provider="tws",
                capability="datafeed",
            )
        )

        with pytest.raises(ProviderException) as exc_info:
            await provider._resolve_trading_contract("EXCHANGE:INVALID")

        assert "SYMBOL_NOT_FOUND" in str(exc_info.value.code)


class TestEditPositionBrackets:
    """Test TWSBrokerProvider.edit_position_brackets() with OCA groups."""

    @pytest.fixture
    def mock_client(self) -> Mock:
        """Create mock TWSClient for edit_position_brackets."""
        mock = Mock()

        # Mock req_ticker_details
        contract_details = _create_mock_contract_details()
        mock.req_ticker_details = AsyncMock(return_value=contract_details)

        # Mock placeOcaGroup to return tracked orders with unique IDs
        def create_oca_result(
            contract: Contract,
            orders: list[Order],
            oca_group: str,
            oca_type: int = 1,
        ) -> list[TrackedOrder]:
            """Create TrackedOrder for each order with sequential IDs."""
            result = []
            for i, order in enumerate(orders):
                tracked = _create_tracked_order(200 + i, order=order)
                result.append(tracked)
            return result

        mock.placeOcaGroup = AsyncMock(side_effect=create_oca_result)
        mock.cancelOrder = AsyncMock()
        mock.reqContractDetails = AsyncMock(return_value=[contract_details])
        mock.reqOpenOrders = AsyncMock(return_value=[])
        return mock

    @pytest.fixture
    def provider(self, mock_client: Mock) -> TWSBrokerProvider:
        """Create provider with mocked TWSClient and a test position."""
        with patch(
            "trading_api.providers.tws.broker_provider.TWSClient",
            return_value=mock_client,
        ):
            provider = TWSBrokerProvider()
            # Add a test position for bracket operations
            provider._positions["pos_123"] = Position(
                id="pos_123",
                symbol="NASDAQ:AAPL",
                side=Side.BUY,
                qty=100.0,
                avgPrice=150.00,
            )
            return provider

    @pytest.mark.asyncio
    async def test_edit_position_brackets_raises_for_unknown_position(
        self, provider: TWSBrokerProvider
    ) -> None:
        """Test raises ProviderException when position not found."""
        brackets = Brackets(stopLoss=140.00, takeProfit=160.00)

        with pytest.raises(ProviderException) as exc_info:
            await provider.edit_position_brackets("unknown_pos", brackets)

        assert "PROVIDER_BROKER_POSITION_NOT_FOUND" in str(exc_info.value.code)

    @pytest.mark.asyncio
    async def test_edit_position_brackets_calls_place_oca_group(
        self, provider: TWSBrokerProvider, mock_client: Mock
    ) -> None:
        """Test edit_position_brackets calls placeOcaGroup with brackets."""
        brackets = Brackets(stopLoss=140.00, takeProfit=160.00)

        await provider.edit_position_brackets("pos_123", brackets)

        mock_client.placeOcaGroup.assert_called_once()
        call_args = mock_client.placeOcaGroup.call_args
        orders = call_args[0][1]
        oca_group = call_args[0][2]
        oca_type = call_args[1].get(
            "oca_type", call_args[0][3] if len(call_args[0]) > 3 else 1
        )

        # Should have 2 orders: stop loss + take profit
        assert len(orders) == 2
        # OCA group should contain position ID
        assert oca_group == "brackets_pos_123"
        # OCA type should be CANCEL_WITH_BLOCK (1)
        assert oca_type == 1

    @pytest.mark.asyncio
    async def test_edit_position_brackets_creates_correct_stop_order(
        self, provider: TWSBrokerProvider, mock_client: Mock
    ) -> None:
        """Test stop loss order has correct type and price."""
        brackets = Brackets(stopLoss=140.00)

        await provider.edit_position_brackets("pos_123", brackets)

        call_args = mock_client.placeOcaGroup.call_args
        orders = call_args[0][1]

        assert len(orders) == 1
        stop_order = orders[0]
        assert stop_order.orderType == "STP"
        assert stop_order.auxPrice == 140.00
        assert stop_order.action == "SELL"  # Opposite of BUY position

    @pytest.mark.asyncio
    async def test_edit_position_brackets_creates_correct_tp_order(
        self, provider: TWSBrokerProvider, mock_client: Mock
    ) -> None:
        """Test take profit order has correct type and price."""
        brackets = Brackets(takeProfit=165.00)

        await provider.edit_position_brackets("pos_123", brackets)

        call_args = mock_client.placeOcaGroup.call_args
        orders = call_args[0][1]

        assert len(orders) == 1
        tp_order = orders[0]
        assert tp_order.orderType == "LMT"
        assert tp_order.lmtPrice == 165.00
        assert tp_order.action == "SELL"  # Opposite of BUY position

    @pytest.mark.asyncio
    async def test_edit_position_brackets_trailing_stop_sets_trail_stop_price(
        self, provider: TWSBrokerProvider, mock_client: Mock
    ) -> None:
        """Test trailing stop sets trailStopPrice when stopLoss provided."""
        brackets = Brackets(stopLoss=145.00, trailingStopPips=2.50)

        await provider.edit_position_brackets("pos_123", brackets)

        call_args = mock_client.placeOcaGroup.call_args
        orders = call_args[0][1]

        assert len(orders) == 1
        trail_order = orders[0]
        assert trail_order.orderType == "TRAIL"
        assert trail_order.auxPrice == 2.50  # Trail amount
        assert trail_order.trailStopPrice == 145.00  # Initial trigger price

    @pytest.mark.asyncio
    async def test_edit_position_brackets_orders_retrievable(
        self, provider: TWSBrokerProvider, mock_client: Mock
    ) -> None:
        """Test bracket orders can be retrieved via get_orders."""
        # Setup mock to return the placed OCA orders
        sl_tracked = _create_tracked_order(200)
        tp_tracked = _create_tracked_order(201)
        mock_client.reqOpenOrders = AsyncMock(return_value=[sl_tracked, tp_tracked])

        brackets = Brackets(stopLoss=140.00, takeProfit=160.00)

        await provider.edit_position_brackets("pos_123", brackets)

        # Should be able to retrieve 2 orders via get_orders
        orders = await provider.get_orders()
        order_ids = {o.id for o in orders}
        assert "200" in order_ids
        assert "201" in order_ids


class TestPreviewOrder:
    """Test TWSBrokerProvider.preview_order() with TWS whatIf mode."""

    def _create_whatif_order_state(
        self,
        init_margin_change: str = "5000.00",
        maint_margin_change: str = "2500.00",
        commission: float = 1.50,
        warning_text: str = "",
    ) -> OrderState:
        """Create an OrderState with whatIf data."""
        order_state = OrderState()
        order_state.status = "PreSubmitted"
        order_state.initMarginChange = init_margin_change
        order_state.maintMarginChange = maint_margin_change
        order_state.equityWithLoanChange = "-5000.00"
        order_state.initMarginAfter = "10000.00"
        order_state.commissionAndFees = commission
        order_state.minCommissionAndFees = commission
        order_state.maxCommissionAndFees = commission
        order_state.marginCurrency = "USD"
        order_state.commissionAndFeesCurrency = "USD"
        order_state.warningText = warning_text
        order_state.rejectReason = ""
        return order_state

    @pytest.fixture
    def mock_client(self) -> Mock:
        """Create mock TWSClient with whatIf support."""
        mock = Mock()

        # Mock req_ticker_details
        contract_details = _create_mock_contract_details()
        mock.req_ticker_details = AsyncMock(return_value=contract_details)

        return mock

    @pytest.fixture
    def provider(self, mock_client: Mock) -> TWSBrokerProvider:
        """Create provider with mocked TWSClient."""
        with patch(
            "trading_api.providers.tws.broker_provider.TWSClient",
            return_value=mock_client,
        ):
            return TWSBrokerProvider()

    @pytest.mark.asyncio
    async def test_preview_order_calls_place_order_with_what_if(
        self, provider: TWSBrokerProvider, mock_client: Mock
    ) -> None:
        """Test preview_order calls placeOrder with whatIf=True."""
        # Setup mock to return TrackedOrder with whatIf data
        whatif_order_state = self._create_whatif_order_state()
        tracked = _create_tracked_order(999, order_state=whatif_order_state)
        mock_client.placeOrder = AsyncMock(return_value=tracked)

        pre_order = PreOrder(
            symbol="NASDAQ:AAPL",
            side=Side.BUY,
            type=OrderType.LIMIT,
            qty=100.0,
            limitPrice=150.00,
        )

        await provider.preview_order(pre_order)

        # Verify placeOrder was called
        mock_client.placeOrder.assert_called_once()
        call_args = mock_client.placeOrder.call_args

        # Second arg is order
        order = call_args[0][1]
        assert order.whatIf is True

    @pytest.mark.asyncio
    async def test_preview_order_returns_preview_result(
        self, provider: TWSBrokerProvider, mock_client: Mock
    ) -> None:
        """Test preview_order returns OrderPreviewResult with TWS data."""
        whatif_order_state = self._create_whatif_order_state(
            init_margin_change="7500.00",
            commission=2.50,
        )
        tracked = _create_tracked_order(999, order_state=whatif_order_state)
        mock_client.placeOrder = AsyncMock(return_value=tracked)

        pre_order = PreOrder(
            symbol="NASDAQ:AAPL",
            side=Side.BUY,
            type=OrderType.LIMIT,
            qty=100.0,
            limitPrice=150.00,
        )

        result = await provider.preview_order(pre_order)

        # Verify result structure
        assert result.confirmId is not None
        assert len(result.sections) >= 2

        # Check margin section has TWS data
        margin_section = next(
            (s for s in result.sections if s.header == "Margin Requirements"), None
        )
        assert margin_section is not None
        row_dict = {row.title: row.value for row in margin_section.rows}
        assert "Initial Margin Required" in row_dict
        assert "7,500.00" in row_dict["Initial Margin Required"]

    @pytest.mark.asyncio
    async def test_preview_order_with_tws_warning(
        self, provider: TWSBrokerProvider, mock_client: Mock
    ) -> None:
        """Test preview_order includes TWS warning text."""
        whatif_order_state = self._create_whatif_order_state(
            warning_text="Order will be held until market opens"
        )
        tracked = _create_tracked_order(999, order_state=whatif_order_state)
        mock_client.placeOrder = AsyncMock(return_value=tracked)

        pre_order = PreOrder(
            symbol="NASDAQ:AAPL",
            side=Side.BUY,
            type=OrderType.MARKET,
            qty=100.0,
        )

        result = await provider.preview_order(pre_order)

        assert result.warnings is not None
        assert any("market opens" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_preview_order_propagates_tws_error(
        self, provider: TWSBrokerProvider, mock_client: Mock
    ) -> None:
        """Test preview_order propagates TWS errors to caller.

        When TWS placeOrder (whatIf mode) fails, the error should propagate
        rather than being silently swallowed. The caller (BFF layer) decides
        how to handle the error.
        """
        # Simulate TWS connection error during whatIf order
        mock_client.placeOrder = AsyncMock(side_effect=Exception("TWS connection lost"))

        pre_order = PreOrder(
            symbol="NASDAQ:AAPL",
            side=Side.BUY,
            type=OrderType.LIMIT,
            qty=100.0,
            limitPrice=150.00,
        )

        # Error should propagate - provider doesn't swallow TWS errors
        with pytest.raises(Exception, match="TWS connection lost"):
            await provider.preview_order(pre_order)

    @pytest.mark.asyncio
    async def test_preview_order_fallback_on_contract_not_found(
        self, provider: TWSBrokerProvider, mock_client: Mock
    ) -> None:
        """Test preview_order raises ProviderException when contract not found."""
        # Mock req_ticker_details to raise ProviderException (symbol not found)
        mock_client.req_ticker_details = AsyncMock(
            side_effect=ProviderException(
                code="PROVIDER_DATAFEED_SYMBOL_NOT_FOUND",
                message="Symbol not found: EXCHANGE:INVALID",
                provider="tws",
                capability="datafeed",
            )
        )

        pre_order = PreOrder(
            symbol="EXCHANGE:INVALID",
            side=Side.BUY,
            type=OrderType.MARKET,
            qty=100.0,
        )

        with pytest.raises(ProviderException) as exc_info:
            await provider.preview_order(pre_order)

        assert "SYMBOL_NOT_FOUND" in str(exc_info.value.code)

    @pytest.mark.asyncio
    async def test_preview_order_with_brackets(
        self, provider: TWSBrokerProvider, mock_client: Mock
    ) -> None:
        """Test preview_order includes bracket info in result."""
        whatif_order_state = self._create_whatif_order_state()
        tracked = _create_tracked_order(999, order_state=whatif_order_state)
        mock_client.placeOrder = AsyncMock(return_value=tracked)

        pre_order = PreOrder(
            symbol="NASDAQ:AAPL",
            side=Side.BUY,
            type=OrderType.LIMIT,
            qty=100.0,
            limitPrice=150.00,
            stopLoss=145.00,
            takeProfit=160.00,
        )

        result = await provider.preview_order(pre_order)

        # Should have Risk Management section
        risk_section = next(
            (s for s in result.sections if s.header == "Risk Management"), None
        )
        assert risk_section is not None
        row_dict = {row.title: row.value for row in risk_section.rows}
        assert "Stop Loss" in row_dict
        assert "Take Profit" in row_dict

    @pytest.mark.asyncio
    async def test_preview_order_does_not_place_bracket_orders(
        self, provider: TWSBrokerProvider, mock_client: Mock
    ) -> None:
        """Test preview_order only previews entry order, not brackets."""
        whatif_order_state = self._create_whatif_order_state()
        tracked = _create_tracked_order(999, order_state=whatif_order_state)
        mock_client.placeOrder = AsyncMock(return_value=tracked)

        pre_order = PreOrder(
            symbol="NASDAQ:AAPL",
            side=Side.BUY,
            type=OrderType.LIMIT,
            qty=100.0,
            limitPrice=150.00,
            stopLoss=145.00,
            takeProfit=160.00,
        )

        await provider.preview_order(pre_order)

        # placeOrder should only be called once (for entry order)
        assert mock_client.placeOrder.call_count == 1

        # placeOrderGroup should NOT be called (no actual bracket placement)
        assert not hasattr(mock_client, "placeOrderGroup") or (
            hasattr(mock_client.placeOrderGroup, "call_count")
            and mock_client.placeOrderGroup.call_count == 0
        )


# =============================================================================
# Bracket Order Grouping Helpers Tests
# =============================================================================


def _create_tws_order(
    order_id: int,
    order_type: str = "LMT",
    action: str = "BUY",
    quantity: float = 100.0,
    lmt_price: float | None = None,
    aux_price: float | None = None,
    trail_stop_price: float | None = None,
    parent_id: int = 0,
    oca_group: str = "",
) -> Order:
    """Create a mock TWS Order for testing."""
    order = Order()
    order.orderId = order_id
    order.orderType = order_type
    order.action = action
    order.totalQuantity = Decimal(str(quantity))
    order.lmtPrice = lmt_price if lmt_price else 0.0
    order.auxPrice = aux_price if aux_price else 0.0
    order.trailStopPrice = trail_stop_price if trail_stop_price else 0.0
    order.parentId = parent_id
    order.ocaGroup = oca_group
    order.tif = "GTC"
    return order


class TestGroupOrdersByBracket:
    """Tests for _group_orders_by_bracket helper function."""

    def test_standalone_orders_go_to_parents_map(self) -> None:
        """Standalone orders (no parent, no OCA) go to parents_map."""
        contract = _create_mock_contract()
        order_state = OrderState()
        order_state.status = "Submitted"

        # Create standalone order
        order = _create_tws_order(100, order_type="LMT")
        tracked = TrackedOrder(
            orderId=100, contract=contract, order=order, orderState=order_state
        )

        parents, order_children, position_children = _group_orders_by_bracket([tracked])

        assert 100 in parents
        assert parents[100] == tracked
        assert len(order_children) == 0
        assert len(position_children) == 0

    def test_child_with_parent_id_grouped_as_order_child(self) -> None:
        """Orders with parentId > 0 are grouped as order bracket children."""
        contract = _create_mock_contract()
        order_state = OrderState()
        order_state.status = "Submitted"

        # Create parent order
        parent_order = _create_tws_order(100, order_type="LMT")
        parent = TrackedOrder(
            orderId=100, contract=contract, order=parent_order, orderState=order_state
        )

        # Create child order with parentId set
        child_order = _create_tws_order(101, order_type="STP", parent_id=100)
        child = TrackedOrder(
            orderId=101, contract=contract, order=child_order, orderState=order_state
        )

        parents, order_children, position_children = _group_orders_by_bracket(
            [parent, child]
        )

        assert 100 in parents
        assert "100" in order_children
        assert child in order_children["100"]
        assert len(position_children) == 0

    def test_child_with_numeric_oca_grouped_as_order_child(self) -> None:
        """Orders with brackets_<numeric> OCA are grouped as order bracket children."""
        contract = _create_mock_contract()
        order_state = OrderState()
        order_state.status = "Submitted"

        # Create parent order
        parent_order = _create_tws_order(100, order_type="LMT")
        parent = TrackedOrder(
            orderId=100, contract=contract, order=parent_order, orderState=order_state
        )

        # Create child with OCA group (no parentId)
        child_order = _create_tws_order(101, order_type="STP", oca_group="brackets_100")
        child = TrackedOrder(
            orderId=101, contract=contract, order=child_order, orderState=order_state
        )

        parents, order_children, position_children = _group_orders_by_bracket(
            [parent, child]
        )

        assert 100 in parents
        assert "100" in order_children
        assert child in order_children["100"]
        assert len(position_children) == 0

    def test_position_bracket_with_symbol_oca(self) -> None:
        """Orders with brackets_<symbol> OCA are grouped as position bracket children."""
        contract = _create_mock_contract()
        order_state = OrderState()
        order_state.status = "Submitted"

        # Create position bracket child (OCA with symbol string)
        child_order = _create_tws_order(
            101, order_type="STP", oca_group="brackets_AAPL:NASDAQ:STK"
        )
        child = TrackedOrder(
            orderId=101, contract=contract, order=child_order, orderState=order_state
        )

        parents, order_children, position_children = _group_orders_by_bracket([child])

        assert len(parents) == 0  # No parent order
        assert len(order_children) == 0
        assert "AAPL:NASDAQ:STK" in position_children
        assert child in position_children["AAPL:NASDAQ:STK"]

    def test_mixed_orders_grouped_correctly(self) -> None:
        """Mixed standalone, order brackets, and position brackets are grouped."""
        contract = _create_mock_contract()
        order_state = OrderState()
        order_state.status = "Submitted"

        # Standalone order
        standalone = TrackedOrder(
            orderId=1,
            contract=contract,
            order=_create_tws_order(1, order_type="MKT"),
            orderState=order_state,
        )

        # Order bracket parent
        parent = TrackedOrder(
            orderId=100,
            contract=contract,
            order=_create_tws_order(100, order_type="LMT"),
            orderState=order_state,
        )

        # Order bracket children
        order_child1 = TrackedOrder(
            orderId=101,
            contract=contract,
            order=_create_tws_order(101, order_type="STP", parent_id=100),
            orderState=order_state,
        )
        order_child2 = TrackedOrder(
            orderId=102,
            contract=contract,
            order=_create_tws_order(102, order_type="LMT", parent_id=100),
            orderState=order_state,
        )

        # Position bracket children
        pos_child = TrackedOrder(
            orderId=200,
            contract=contract,
            order=_create_tws_order(
                200, order_type="STP", oca_group="brackets_MSFT:NASDAQ:STK"
            ),
            orderState=order_state,
        )

        parents, order_children, position_children = _group_orders_by_bracket(
            [standalone, parent, order_child1, order_child2, pos_child]
        )

        # Verify grouping
        assert len(parents) == 2  # standalone + parent
        assert 1 in parents
        assert 100 in parents
        assert "100" in order_children
        assert len(order_children["100"]) == 2
        assert "MSFT:NASDAQ:STK" in position_children
        assert len(position_children["MSFT:NASDAQ:STK"]) == 1


class TestBuildBracketContextFromChildren:
    """Tests for _build_bracket_context_from_children helper function."""

    def test_extract_take_profit_from_lmt(self) -> None:
        """LMT orders are mapped to takeProfit."""
        contract = _create_mock_contract()
        order_state = OrderState()
        order_state.status = "Submitted"

        tp_order = _create_tws_order(101, order_type="LMT", lmt_price=160.0)
        tp = TrackedOrder(
            orderId=101, contract=contract, order=tp_order, orderState=order_state
        )

        context = _build_bracket_context_from_children([tp])

        assert context.take_profit == 160.0
        assert context.stop_loss is None
        assert 101 in context.child_order_ids

    def test_extract_stop_loss_from_stp(self) -> None:
        """STP orders are mapped to stopLoss."""
        contract = _create_mock_contract()
        order_state = OrderState()
        order_state.status = "Submitted"

        sl_order = _create_tws_order(101, order_type="STP", aux_price=145.0)
        sl = TrackedOrder(
            orderId=101, contract=contract, order=sl_order, orderState=order_state
        )

        context = _build_bracket_context_from_children([sl])

        assert context.stop_loss == 145.0
        assert context.stop_type == 0  # StopType.STOP_LOSS
        assert context.take_profit is None
        assert 101 in context.child_order_ids

    def test_extract_trailing_stop_from_trail(self) -> None:
        """TRAIL orders are mapped to trailingStopPips and stopLoss."""
        contract = _create_mock_contract()
        order_state = OrderState()
        order_state.status = "Submitted"

        trail_order = _create_tws_order(
            101, order_type="TRAIL", aux_price=5.0, trail_stop_price=145.0
        )
        trail = TrackedOrder(
            orderId=101, contract=contract, order=trail_order, orderState=order_state
        )

        context = _build_bracket_context_from_children([trail])

        assert context.trailing_stop_pips == 5.0
        assert context.stop_loss == 145.0
        assert context.stop_type == 1  # StopType.TRAILING_STOP
        assert 101 in context.child_order_ids

    def test_full_bracket_sl_and_tp(self) -> None:
        """Full bracket with SL and TP extracts both prices."""
        contract = _create_mock_contract()
        order_state = OrderState()
        order_state.status = "Submitted"

        sl_order = _create_tws_order(101, order_type="STP", aux_price=145.0)
        sl = TrackedOrder(
            orderId=101, contract=contract, order=sl_order, orderState=order_state
        )

        tp_order = _create_tws_order(102, order_type="LMT", lmt_price=160.0)
        tp = TrackedOrder(
            orderId=102, contract=contract, order=tp_order, orderState=order_state
        )

        context = _build_bracket_context_from_children([sl, tp])

        assert context.stop_loss == 145.0
        assert context.take_profit == 160.0
        assert 101 in context.child_order_ids
        assert 102 in context.child_order_ids


class TestGroupAndMapTwsOrders:
    """Tests for _group_and_map_tws_orders main orchestration function."""

    def test_standalone_order_mapped_without_bracket_fields(self) -> None:
        """Standalone orders are mapped without parentId/parentType."""
        contract = _create_mock_contract()
        order_state = OrderState()
        order_state.status = "Submitted"

        order = _create_tws_order(100, order_type="LMT", lmt_price=150.0)
        tracked = TrackedOrder(
            orderId=100, contract=contract, order=order, orderState=order_state
        )

        result = _group_and_map_tws_orders([tracked], {contract.conId: contract})

        assert len(result) == 1
        placed = result[0]
        assert placed.id == "100"
        assert placed.parentId is None
        assert placed.parentType is None

    def test_order_bracket_parent_enriched_with_bracket_prices(self) -> None:
        """Parent orders are enriched with stopLoss/takeProfit from children."""
        contract = _create_mock_contract()
        order_state = OrderState()
        order_state.status = "Submitted"

        # Parent order
        parent_order = _create_tws_order(100, order_type="LMT", lmt_price=150.0)
        parent = TrackedOrder(
            orderId=100, contract=contract, order=parent_order, orderState=order_state
        )

        # SL child with parentId
        sl_order = _create_tws_order(
            101, order_type="STP", aux_price=145.0, parent_id=100
        )
        sl = TrackedOrder(
            orderId=101, contract=contract, order=sl_order, orderState=order_state
        )

        # TP child with parentId
        tp_order = _create_tws_order(
            102, order_type="LMT", lmt_price=160.0, parent_id=100
        )
        tp = TrackedOrder(
            orderId=102, contract=contract, order=tp_order, orderState=order_state
        )

        result = _group_and_map_tws_orders([parent, sl, tp], {contract.conId: contract})

        # Find the parent order in result
        parent_result = next((o for o in result if o.id == "100"), None)
        assert parent_result is not None
        assert parent_result.stopLoss == 145.0
        assert parent_result.takeProfit == 160.0
        assert parent_result.parentId is None  # Parent has no parent
        assert parent_result.parentType is None

    def test_order_bracket_children_linked_with_parent_type_order(self) -> None:
        """Order bracket children have parentId and parentType=ORDER."""
        contract = _create_mock_contract()
        order_state = OrderState()
        order_state.status = "Submitted"

        # Parent order
        parent_order = _create_tws_order(100, order_type="LMT", lmt_price=150.0)
        parent = TrackedOrder(
            orderId=100, contract=contract, order=parent_order, orderState=order_state
        )

        # SL child
        sl_order = _create_tws_order(
            101, order_type="STP", aux_price=145.0, parent_id=100
        )
        sl = TrackedOrder(
            orderId=101, contract=contract, order=sl_order, orderState=order_state
        )

        result = _group_and_map_tws_orders([parent, sl], {contract.conId: contract})

        # Find the child order in result
        child_result = next((o for o in result if o.id == "101"), None)
        assert child_result is not None
        assert child_result.parentId == "100"
        assert child_result.parentType == ParentType.ORDER

    def test_position_bracket_children_linked_with_parent_type_position(self) -> None:
        """Position bracket children have parentId (symbol) and parentType=POSITION."""
        contract = _create_mock_contract()
        order_state = OrderState()
        order_state.status = "Submitted"

        # Position bracket child (OCA with symbol string)
        sl_order = _create_tws_order(
            101, order_type="STP", aux_price=145.0, oca_group="brackets_AAPL:NASDAQ:STK"
        )
        sl = TrackedOrder(
            orderId=101, contract=contract, order=sl_order, orderState=order_state
        )

        result = _group_and_map_tws_orders([sl], {contract.conId: contract})

        assert len(result) == 1
        placed = result[0]
        assert placed.id == "101"
        assert placed.parentId == "AAPL:NASDAQ:STK"
        assert placed.parentType == ParentType.POSITION

    def test_mixed_orders_all_mapped_correctly(self) -> None:
        """Mixed standalone, order brackets, position brackets all mapped."""
        contract = _create_mock_contract()
        order_state = OrderState()
        order_state.status = "Submitted"

        # Standalone
        standalone_order = _create_tws_order(1, order_type="MKT")
        standalone = TrackedOrder(
            orderId=1, contract=contract, order=standalone_order, orderState=order_state
        )

        # Order bracket parent
        parent_order = _create_tws_order(100, order_type="LMT", lmt_price=150.0)
        parent = TrackedOrder(
            orderId=100, contract=contract, order=parent_order, orderState=order_state
        )

        # Order bracket child
        order_child_order = _create_tws_order(
            101, order_type="STP", aux_price=145.0, parent_id=100
        )
        order_child = TrackedOrder(
            orderId=101,
            contract=contract,
            order=order_child_order,
            orderState=order_state,
        )

        # Position bracket child
        pos_child_order = _create_tws_order(
            200, order_type="LMT", lmt_price=50.0, oca_group="brackets_MSFT:NASDAQ:STK"
        )
        pos_child = TrackedOrder(
            orderId=200,
            contract=contract,
            order=pos_child_order,
            orderState=order_state,
        )

        result = _group_and_map_tws_orders(
            [standalone, parent, order_child, pos_child], {contract.conId: contract}
        )

        assert len(result) == 4

        # Verify standalone
        standalone_result = next((o for o in result if o.id == "1"), None)
        assert standalone_result is not None
        assert standalone_result.parentId is None

        # Verify parent enriched
        parent_result = next((o for o in result if o.id == "100"), None)
        assert parent_result is not None
        assert parent_result.stopLoss == 145.0

        # Verify order child linked
        order_child_result = next((o for o in result if o.id == "101"), None)
        assert order_child_result is not None
        assert order_child_result.parentId == "100"
        assert order_child_result.parentType == ParentType.ORDER

        # Verify position child linked
        pos_child_result = next((o for o in result if o.id == "200"), None)
        assert pos_child_result is not None
        assert pos_child_result.parentId == "MSFT:NASDAQ:STK"
        assert pos_child_result.parentType == ParentType.POSITION
