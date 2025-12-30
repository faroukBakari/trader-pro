"""Tests for TWSBrokerProvider - BrokerCapability implementation.

Tests cover:
- Provider initialization and configuration
- Provider capabilities declaration
- Order operations: place_order, cancel_order, modify_order, get_orders

Note: All tests mock TWSClient to avoid real TWS connections.
Note: PreOrder.symbol uses composite ticker format (e.g., "AAPL:SMART:STK-265598").
"""




# class TestBrokerProviderInitialization:
#     """Test TWSBrokerProvider initialization and configuration."""

#     def test_provider_default_config(self) -> None:
#         """Test TWSBrokerProvider uses default config when none provided."""
#         with patch("trading_api.providers.tws.broker_provider.TWSClient"):
#             provider = TWSBrokerProvider()

#         assert provider.config.host == "127.0.0.1"
#         assert provider.config.port == 7497
#         assert provider.config.client_id == 2  # Default broker client_id

#     def test_provider_with_custom_config(self) -> None:
#         """Test TWSBrokerProvider config is stored correctly."""
#         config = TWSBrokerProviderConfig(
#             host="192.168.1.1", port=4002, client_id=5, account_id="DU123456"
#         )

#         with patch("trading_api.providers.tws.broker_provider.TWSClient"):
#             provider = TWSBrokerProvider(config=config)

#         assert provider.config.host == "192.168.1.1"
#         assert provider.config.port == 4002
#         assert provider.config.client_id == 5
#         assert provider.config.account_id == "DU123456"

#     def test_provider_capabilities(self) -> None:
#         """Test provider capabilities declaration."""
#         caps = TWSBrokerProvider.capabilities()

#         assert len(caps) == 1
#         assert caps[0].name == "broker"

#     def test_provider_name(self) -> None:
#         """Test provider name."""
#         with patch("trading_api.providers.tws.broker_provider.TWSClient"):
#             provider = TWSBrokerProvider()

#         assert provider.name == "tws"

#     def test_provider_creates_tws_client(self) -> None:
#         """Test provider creates TWSClient with config."""
#         with patch("trading_api.providers.tws.broker_provider.TWSClient") as MockClient:
#             config = TWSBrokerProviderConfig(host="10.0.0.1", port=4001, client_id=10)
#             TWSBrokerProvider(config=config)

#         MockClient.assert_called_once_with("10.0.0.1", 4001, 10)


# class TestPlaceOrder:
#     """Test TWSBrokerProvider.place_order()."""

#     @pytest.fixture
#     def mock_client(self) -> Mock:
#         """Create mock TWSClient."""
#         mock = Mock()
#         # placeOrder now allocates and returns order ID
#         mock.placeOrder = Mock(return_value=12345)
#         return mock

#     @pytest.fixture
#     def provider(self, mock_client: Mock) -> TWSBrokerProvider:
#         """Create provider with mocked TWSClient."""
#         with patch(
#             "trading_api.providers.tws.broker_provider.TWSClient",
#             return_value=mock_client,
#         ):
#             return TWSBrokerProvider(
#                 config=TWSBrokerProviderConfig(account_id="DU123456")
#             )

#     @pytest.mark.asyncio
#     async def test_place_order_returns_order_id(
#         self, provider: TWSBrokerProvider, mock_client: Mock
#     ) -> None:
#         """Test place_order returns PlaceOrderResult with order ID."""
#         # Use composite ticker format (symbol:exchange:secType-conId)
#         pre_order = PreOrder(
#             symbol="AAPL:SMART:STK-265598",
#             side=Side.BUY,
#             type=OrderType.MARKET,
#             qty=100.0,
#         )

#         result = await provider.place_order(pre_order)

#         assert isinstance(result, PlaceOrderResult)
#         assert result.orderId == "12345"

#     @pytest.mark.asyncio
#     async def test_place_order_calls_tws_client(
#         self, provider: TWSBrokerProvider, mock_client: Mock
#     ) -> None:
#         """Test place_order calls TWSClient.placeOrder with correct args."""
#         pre_order = PreOrder(
#             symbol="AAPL:SMART:STK-265598",
#             side=Side.BUY,
#             type=OrderType.LIMIT,
#             qty=100.0,
#             limitPrice=150.00,
#         )

#         await provider.place_order(pre_order)

#         # Verify placeOrder was called (now takes contract, order only)
#         mock_client.placeOrder.assert_called_once()

#         # Check call args - placeOrder(contract, order) -> returns order_id
#         call_args = mock_client.placeOrder.call_args
#         assert isinstance(call_args[0][0], Contract)  # contract
#         assert isinstance(call_args[0][1], Order)  # order

#         # Verify contract fields
#         contract = call_args[0][0]
#         assert contract.symbol == "AAPL"
#         assert contract.secType == "STK"
#         assert contract.conId == 265598

#         # Verify order fields
#         order = call_args[0][1]
#         assert order.action == "BUY"
#         assert order.orderType == "LMT"
#         assert order.totalQuantity == Decimal("100")
#         assert order.lmtPrice == 150.00

#     @pytest.mark.asyncio
#     async def test_place_order_with_stop_order(
#         self, provider: TWSBrokerProvider, mock_client: Mock
#     ) -> None:
#         """Test place_order correctly converts stop order."""
#         pre_order = PreOrder(
#             symbol="AAPL:SMART:STK-265598",
#             side=Side.SELL,
#             type=OrderType.STOP,
#             qty=50.0,
#             stopPrice=140.00,
#         )

#         await provider.place_order(pre_order)

#         # Check order type conversion - placeOrder(contract, order) now
#         call_args = mock_client.placeOrder.call_args
#         order = call_args[0][1]
#         assert order.orderType == "STP"
#         assert order.action == "SELL"
#         assert order.auxPrice == 140.00


# class TestModifyOrder:
#     """Test TWSBrokerProvider.modify_order()."""

#     @pytest.fixture
#     def mock_client(self) -> Mock:
#         """Create mock TWSClient."""
#         mock = Mock()
#         mock.modifyOrder = Mock()
#         return mock

#     @pytest.fixture
#     def provider(self, mock_client: Mock) -> TWSBrokerProvider:
#         """Create provider with mocked TWSClient."""
#         with patch(
#             "trading_api.providers.tws.broker_provider.TWSClient",
#             return_value=mock_client,
#         ):
#             return TWSBrokerProvider(
#                 config=TWSBrokerProviderConfig(account_id="DU123456")
#             )

#     @pytest.mark.asyncio
#     async def test_modify_order_uses_same_order_id(
#         self, provider: TWSBrokerProvider, mock_client: Mock
#     ) -> None:
#         """Test modify_order re-submits with same order ID."""
#         pre_order = PreOrder(
#             symbol="AAPL:SMART:STK-265598",
#             side=Side.BUY,
#             type=OrderType.LIMIT,
#             qty=100.0,
#             limitPrice=155.00,
#         )

#         await provider.modify_order("12345", pre_order)

#         # Verify modifyOrder was called with original order ID
#         mock_client.modifyOrder.assert_called_once()
#         call_args = mock_client.modifyOrder.call_args
#         assert call_args[0][0] == 12345  # Same order_id


# class TestCancelOrder:
#     """Test TWSBrokerProvider.cancel_order()."""

#     @pytest.fixture
#     def mock_client(self) -> Mock:
#         """Create mock TWSClient."""
#         mock = Mock()
#         mock.cancelOrder = Mock()
#         return mock

#     @pytest.fixture
#     def provider(self, mock_client: Mock) -> TWSBrokerProvider:
#         """Create provider with mocked TWSClient."""
#         with patch(
#             "trading_api.providers.tws.broker_provider.TWSClient",
#             return_value=mock_client,
#         ):
#             return TWSBrokerProvider()

#     @pytest.mark.asyncio
#     async def test_cancel_order_calls_tws_client(
#         self, provider: TWSBrokerProvider, mock_client: Mock
#     ) -> None:
#         """Test cancel_order calls TWSClient.cancelOrder."""
#         await provider.cancel_order("12345")

#         mock_client.cancelOrder.assert_called_once_with(12345)


# class TestGetOrders:
#     """Test TWSBrokerProvider.get_orders()."""

#     @pytest.fixture
#     def mock_client(self) -> Mock:
#         """Create mock TWSClient with AsyncMock for reqOpenOrders."""
#         from unittest.mock import AsyncMock

#         mock = Mock()
#         mock.reqOpenOrders = AsyncMock()
#         return mock

#     @pytest.fixture
#     def provider(self, mock_client: Mock) -> TWSBrokerProvider:
#         """Create provider with mocked TWSClient."""
#         with patch(
#             "trading_api.providers.tws.broker_provider.TWSClient",
#             return_value=mock_client,
#         ):
#             return TWSBrokerProvider()

#     @pytest.mark.asyncio
#     async def test_get_orders_returns_placed_orders(
#         self, provider: TWSBrokerProvider, mock_client: Mock
#     ) -> None:
#         """Test get_orders converts TWS orders to PlacedOrder list."""
#         # Create mock TWS order data (matches openOrder callback format)
#         mock_contract = Contract()
#         mock_contract.symbol = "AAPL"
#         mock_contract.exchange = "SMART"
#         mock_contract.primaryExchange = "NASDAQ"
#         mock_contract.secType = "STK"
#         mock_contract.conId = 265598

#         mock_order = Order()
#         mock_order.action = "BUY"
#         mock_order.orderType = "LMT"
#         mock_order.totalQuantity = Decimal("100")
#         mock_order.lmtPrice = 150.00
#         mock_order.auxPrice = 0.0
#         mock_order.filledQuantity = Decimal("0")

#         mock_order_state = OrderState()
#         mock_order_state.status = "Submitted"

#         mock_client.reqOpenOrders.return_value = [
#             TrackedOrder(
#                 orderId=12345,
#                 contract=mock_contract,
#                 order=mock_order,
#                 orderState=mock_order_state,
#                 fills=[],
#             )
#         ]

#         result = await provider.get_orders()

#         assert len(result) == 1
#         assert isinstance(result[0], PlacedOrder)
#         assert result[0].id == "12345"
#         assert result[0].symbol == "AAPL:NASDAQ:STK-265598"  # Composite ticker format
#         assert result[0].side == Side.BUY
#         assert result[0].type == OrderType.LIMIT
#         assert result[0].qty == 100.0
#         assert result[0].status == OrderStatus.WORKING

#     @pytest.mark.asyncio
#     async def test_get_orders_empty_list(
#         self, provider: TWSBrokerProvider, mock_client: Mock
#     ) -> None:
#         """Test get_orders returns empty list when no orders."""
#         mock_client.reqOpenOrders.return_value = []

#         result = await provider.get_orders()

#         assert result == []

#     @pytest.mark.asyncio
#     async def test_get_orders_multiple_orders(
#         self, provider: TWSBrokerProvider, mock_client: Mock
#     ) -> None:
#         """Test get_orders handles multiple orders."""
#         # Create two mock orders
#         contract1 = Contract()
#         contract1.symbol = "AAPL"
#         contract1.exchange = "SMART"
#         contract1.primaryExchange = "NASDAQ"
#         contract1.secType = "STK"
#         contract1.conId = 265598

#         order1 = Order()
#         order1.action = "BUY"
#         order1.orderType = "MKT"
#         order1.totalQuantity = Decimal("100")
#         order1.lmtPrice = 0.0
#         order1.auxPrice = 0.0
#         order1.filledQuantity = Decimal("0")

#         order_state1 = OrderState()
#         order_state1.status = "Submitted"

#         contract2 = Contract()
#         contract2.symbol = "MSFT"
#         contract2.exchange = "SMART"
#         contract2.primaryExchange = "NASDAQ"
#         contract2.secType = "STK"
#         contract2.conId = 272093

#         order2 = Order()
#         order2.action = "SELL"
#         order2.orderType = "LMT"
#         order2.totalQuantity = Decimal("50")
#         order2.lmtPrice = 380.00
#         order2.auxPrice = 0.0
#         order2.filledQuantity = Decimal("50")

#         order_state2 = OrderState()
#         order_state2.status = "Filled"

#         mock_client.reqOpenOrders.return_value = [
#             TrackedOrder(
#                 orderId=12345,
#                 contract=contract1,
#                 order=order1,
#                 orderState=order_state1,
#                 fills=[],
#             ),
#             TrackedOrder(
#                 orderId=12346,
#                 contract=contract2,
#                 order=order2,
#                 orderState=order_state2,
#                 fills=[],
#             ),
#         ]

#         result = await provider.get_orders()

#         assert len(result) == 2
#         assert result[0].symbol == "AAPL:NASDAQ:STK-265598"
#         assert result[0].side == Side.BUY
#         assert result[1].symbol == "MSFT:NASDAQ:STK-272093"
#         assert result[1].side == Side.SELL
#         assert result[1].status == OrderStatus.FILLED
