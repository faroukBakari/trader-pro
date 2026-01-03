"""Tests for TWSBrokerProvider - BrokerCapability implementation.

Tests cover:
- Provider initialization and configuration
- Provider capabilities declaration
- Order operations: place_order, cancel_order, modify_order

Note: All tests mock TWSClient to avoid real TWS connections.
Note: PreOrder.symbol uses composite ticker format (e.g., "AAPL:NASDAQ:STK").
"""

from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

import pytest
from ibapi.contract import Contract
from ibapi.order import Order
from ibapi.order_state import OrderState

from trading_api.models.broker import (
    OrderStatus,
    OrderType,
    PlacedOrder,
    PlaceOrderResult,
    PreOrder,
    Side,
)
from trading_api.models.providers.tws_configs import TWSBrokerProviderConfig
from trading_api.providers.tws.broker_provider import TWSBrokerProvider
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
        # qualify_contract returns list with contract details
        mock_qualified = Mock()
        mock_qualified.contract = _create_mock_contract()
        mock.qualify_contract = AsyncMock(return_value=[mock_qualified])
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
            symbol="AAPL:NASDAQ:STK",
            side=Side.BUY,
            type=OrderType.MARKET,
            qty=100.0,
        )

        result = await provider.place_order(pre_order)

        assert isinstance(result, PlaceOrderResult)
        assert result.orderId == "12345"

    @pytest.mark.asyncio
    async def test_place_order_calls_qualify_contract(
        self, provider: TWSBrokerProvider, mock_client: Mock
    ) -> None:
        """Test place_order calls qualify_contract with symbol."""
        pre_order = PreOrder(
            symbol="AAPL:NASDAQ:STK",
            side=Side.BUY,
            type=OrderType.MARKET,
            qty=100.0,
        )

        await provider.place_order(pre_order)

        mock_client.qualify_contract.assert_called_once()
        call_args = mock_client.qualify_contract.call_args
        assert call_args[0][0] == "AAPL:NASDAQ:STK"

    @pytest.mark.asyncio
    async def test_place_order_calls_place_order_group(
        self, provider: TWSBrokerProvider, mock_client: Mock
    ) -> None:
        """Test place_order calls placeOrderGroup with correct args."""
        pre_order = PreOrder(
            symbol="AAPL:NASDAQ:STK",
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
            symbol="AAPL:NASDAQ:STK",
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

    @pytest.mark.asyncio
    async def test_place_order_stores_in_orders_dict(
        self, provider: TWSBrokerProvider, mock_client: Mock
    ) -> None:
        """Test place_order stores result in internal _orders dict."""
        pre_order = PreOrder(
            symbol="AAPL:NASDAQ:STK",
            side=Side.BUY,
            type=OrderType.MARKET,
            qty=100.0,
        )

        await provider.place_order(pre_order)

        assert "12345" in provider._orders
        stored = provider._orders["12345"]
        assert isinstance(stored, PlacedOrder)
        assert stored.id == "12345"


class TestPlaceOrderWithBrackets:
    """Test TWSBrokerProvider.place_order() with bracket orders."""

    @pytest.fixture
    def mock_client(self) -> Mock:
        """Create mock TWSClient with bracket order support."""
        mock = Mock()
        mock_qualified = Mock()
        mock_qualified.contract = _create_mock_contract()
        mock.qualify_contract = AsyncMock(return_value=[mock_qualified])

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
            symbol="AAPL:NASDAQ:STK",
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
    async def test_place_order_with_brackets_stores_all_orders(
        self, provider: TWSBrokerProvider, mock_client: Mock
    ) -> None:
        """Test place_order with brackets stores parent and children."""
        pre_order = PreOrder(
            symbol="AAPL:NASDAQ:STK",
            side=Side.BUY,
            type=OrderType.LIMIT,
            qty=100.0,
            limitPrice=150.00,
            stopLoss=145.00,
            takeProfit=160.00,
        )

        result = await provider.place_order(pre_order)

        # Parent stored with bracket context
        assert result.orderId == "100"
        assert "100" in provider._orders
        parent = provider._orders["100"]
        assert parent.stopLoss == 145.00
        assert parent.takeProfit == 160.00

        # Children stored
        assert "101" in provider._orders
        assert "102" in provider._orders

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
            symbol="AAPL:NASDAQ:STK",
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
            symbol="AAPL:NASDAQ:STK",
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
        mock_qualified = Mock()
        mock_qualified.contract = _create_mock_contract()
        mock.qualify_contract = AsyncMock(return_value=[mock_qualified])
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
            symbol="AAPL:NASDAQ:STK",
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
    async def test_modify_order_updates_stored_order(
        self, provider: TWSBrokerProvider, mock_client: Mock
    ) -> None:
        """Test modify_order updates the stored order."""
        # First place an order
        place_order = PreOrder(
            symbol="AAPL:NASDAQ:STK",
            side=Side.BUY,
            type=OrderType.LIMIT,
            qty=100.0,
            limitPrice=150.00,
        )
        await provider.place_order(place_order)

        # Reconfigure mock for modify
        modified_order = _create_mock_order(
            order_type="LMT", lmt_price=155.00, total_quantity=Decimal("100")
        )
        mock_client.placeOrderGroup = AsyncMock(
            return_value=(
                _create_tracked_order(12345, order=modified_order),
                [],
            )
        )

        # Modify with new price
        modify_order = PreOrder(
            symbol="AAPL:NASDAQ:STK",
            side=Side.BUY,
            type=OrderType.LIMIT,
            qty=100.0,
            limitPrice=155.00,
        )
        await provider.modify_order("12345", modify_order)

        # Check stored order was updated
        assert "12345" in provider._orders
        stored = provider._orders["12345"]
        assert stored.limitPrice == 155.00


class TestModifyOrderWithBrackets:
    """Test TWSBrokerProvider.modify_order() with bracket modifications."""

    @pytest.fixture
    def mock_client(self) -> Mock:
        """Create mock TWSClient for bracket modification."""
        mock = Mock()
        mock_qualified = Mock()
        mock_qualified.contract = _create_mock_contract()
        mock.qualify_contract = AsyncMock(return_value=[mock_qualified])

        parent_tracked = _create_tracked_order(100)
        sl_tracked = _create_tracked_order(103)  # New child IDs
        tp_tracked = _create_tracked_order(104)
        mock.placeOrderGroup = AsyncMock(
            return_value=(parent_tracked, [sl_tracked, tp_tracked])
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
            symbol="AAPL:NASDAQ:STK",
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

        # New children should be stored
        assert "103" in provider._orders
        assert "104" in provider._orders


class TestCancelOrder:
    """Test TWSBrokerProvider.cancel_order()."""

    @pytest.fixture
    def mock_client(self) -> Mock:
        """Create mock TWSClient with cancelOrder."""
        mock = Mock()
        mock.cancelOrder = AsyncMock(
            return_value=_create_tracked_order(
                12345,
                order_state=_create_mock_order_state("Cancelled"),
            )
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
    async def test_cancel_order_calls_tws_client(
        self, provider: TWSBrokerProvider, mock_client: Mock
    ) -> None:
        """Test cancel_order calls TWSClient.cancelOrder."""
        await provider.cancel_order("12345")

        mock_client.cancelOrder.assert_called_once_with(12345)

    @pytest.mark.asyncio
    async def test_cancel_order_updates_stored_order(
        self, provider: TWSBrokerProvider, mock_client: Mock
    ) -> None:
        """Test cancel_order updates the stored order status."""
        await provider.cancel_order("12345")

        assert "12345" in provider._orders
        stored = provider._orders["12345"]
        assert stored.status == OrderStatus.CANCELED


class TestSelectPreferredExchange:
    """Test TWSBrokerProvider._select_preferred_exchange() helper."""

    @pytest.fixture
    def provider(self) -> TWSBrokerProvider:
        """Create provider with mocked TWSClient."""
        with patch("trading_api.providers.tws.broker_provider.TWSClient"):
            return TWSBrokerProvider()

    def test_returns_smart_during_market_hours(
        self, provider: TWSBrokerProvider
    ) -> None:
        """Test returns SMART during regular market hours."""
        from datetime import datetime
        from unittest.mock import patch as mock_patch

        # Mock to 10:00 AM US/Eastern on a weekday
        mock_now = datetime(2026, 1, 5, 10, 0, 0)  # Monday
        with mock_patch(
            "trading_api.providers.tws.broker_provider.datetime"
        ) as mock_dt:
            mock_dt.now.return_value = mock_now
            mock_dt.strptime = datetime.strptime

            result = provider._select_preferred_exchange()

        assert result == "SMART"

    def test_returns_overnight_after_8pm(self, provider: TWSBrokerProvider) -> None:
        """Test returns OVERNIGHT after 8 PM on weekdays."""
        from datetime import datetime
        from unittest.mock import patch as mock_patch

        # Mock to 9:00 PM US/Eastern on a weekday
        mock_now = datetime(2026, 1, 5, 21, 0, 0)  # Monday 9 PM
        with mock_patch(
            "trading_api.providers.tws.broker_provider.datetime"
        ) as mock_dt:
            mock_dt.now.return_value = mock_now
            mock_dt.strptime = datetime.strptime

            result = provider._select_preferred_exchange()

        assert result == "OVERNIGHT"

    def test_returns_overnight_before_4am(self, provider: TWSBrokerProvider) -> None:
        """Test returns OVERNIGHT before 4 AM on weekdays."""
        from datetime import datetime
        from unittest.mock import patch as mock_patch

        # Mock to 3:00 AM US/Eastern on a weekday
        mock_now = datetime(2026, 1, 6, 3, 0, 0)  # Tuesday 3 AM
        with mock_patch(
            "trading_api.providers.tws.broker_provider.datetime"
        ) as mock_dt:
            mock_dt.now.return_value = mock_now
            mock_dt.strptime = datetime.strptime

            result = provider._select_preferred_exchange()

        assert result == "OVERNIGHT"
