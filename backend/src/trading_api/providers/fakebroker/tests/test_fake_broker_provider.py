"""Tests for FakeBrokerProvider."""

import pytest

from trading_api.models.broker import (
    Brackets,
    Execution,
    LeverageInfoParams,
    LeverageSetParams,
    OrderStatus,
    OrderType,
    PlacedOrder,
    Position,
    PreOrder,
    Side,
)
from trading_api.models.common import CapabilitySpec
from trading_api.models.exceptions import ProviderException
from trading_api.models.providers.fake_broker_configs import FakeBrokerProviderConfig
from trading_api.providers.fakebroker import FakeBrokerProvider


@pytest.fixture
def config() -> FakeBrokerProviderConfig:
    """Test configuration with fast execution."""
    return FakeBrokerProviderConfig(
        initial_balance=100000.0,
        execution_delay_min=0.01,
        execution_delay_max=0.02,
    )


@pytest.fixture
def provider(config: FakeBrokerProviderConfig) -> FakeBrokerProvider:
    """Provider instance with test config."""
    return FakeBrokerProvider(config=config)


class TestProviderProtocol:
    """Test Provider protocol implementation."""

    def test_provider_name(self, provider: FakeBrokerProvider) -> None:
        """Provider name matches directory."""
        assert provider.name == "fakebroker"

    def test_capabilities(self) -> None:
        """Provider declares broker capability."""
        assert FakeBrokerProvider.capabilities() == [CapabilitySpec(name="broker")]

    def test_config_access(self, provider: FakeBrokerProvider) -> None:
        """Config is accessible."""
        assert provider.config.initial_balance == 100000.0


class TestPlaceOrder:
    """Test order placement."""

    @pytest.mark.asyncio
    async def test_place_market_order(self, provider: FakeBrokerProvider) -> None:
        """Place a market order successfully."""
        order = PreOrder(
            symbol="AAPL",
            type=OrderType.MARKET,
            side=Side.BUY,
            qty=10.0,
            limitPrice=150.0,
        )

        result = await provider.place_order(order)

        assert result.orderId.startswith("ORDER-")
        orders = await provider.get_orders()
        assert len(orders) == 1
        assert orders[0].symbol == "AAPL"
        assert orders[0].status == OrderStatus.WORKING

    @pytest.mark.asyncio
    async def test_place_limit_order(self, provider: FakeBrokerProvider) -> None:
        """Place a limit order successfully."""
        order = PreOrder(
            symbol="GOOGL",
            type=OrderType.LIMIT,
            side=Side.SELL,
            qty=5.0,
            limitPrice=2800.0,
        )

        result = await provider.place_order(order)

        assert result.orderId is not None
        orders = await provider.get_orders()
        assert orders[0].type == OrderType.LIMIT
        assert orders[0].limitPrice == 2800.0


class TestModifyOrder:
    """Test order modification."""

    @pytest.mark.asyncio
    async def test_modify_order_success(self, provider: FakeBrokerProvider) -> None:
        """Modify an existing order."""
        # Place order first
        order = PreOrder(
            symbol="AAPL",
            type=OrderType.LIMIT,
            side=Side.BUY,
            qty=10.0,
            limitPrice=150.0,
        )
        result = await provider.place_order(order)

        # Modify it
        modified = PreOrder(
            symbol="AAPL",
            type=OrderType.LIMIT,
            side=Side.BUY,
            qty=20.0,
            limitPrice=145.0,
        )
        await provider.modify_order(result.orderId, modified)

        orders = await provider.get_orders()
        assert orders[0].qty == 20.0
        assert orders[0].limitPrice == 145.0

    @pytest.mark.asyncio
    async def test_modify_nonexistent_order(self, provider: FakeBrokerProvider) -> None:
        """Modifying nonexistent order raises error."""
        modified = PreOrder(
            symbol="AAPL",
            type=OrderType.LIMIT,
            side=Side.BUY,
            qty=10.0,
            limitPrice=150.0,
        )

        with pytest.raises(ProviderException) as exc_info:
            await provider.modify_order("INVALID-ID", modified)

        assert exc_info.value.code == "PROVIDER_BROKER_ORDER_NOT_FOUND"


class TestCancelOrder:
    """Test order cancellation."""

    @pytest.mark.asyncio
    async def test_cancel_order_success(self, provider: FakeBrokerProvider) -> None:
        """Cancel a working order."""
        order = PreOrder(
            symbol="AAPL",
            type=OrderType.LIMIT,
            side=Side.BUY,
            qty=10.0,
            limitPrice=150.0,
        )
        result = await provider.place_order(order)

        await provider.cancel_order(result.orderId)

        orders = await provider.get_orders()
        assert orders[0].status == OrderStatus.CANCELED

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_order(self, provider: FakeBrokerProvider) -> None:
        """Cancelling nonexistent order raises error."""
        with pytest.raises(ProviderException) as exc_info:
            await provider.cancel_order("INVALID-ID")

        assert exc_info.value.code == "PROVIDER_BROKER_ORDER_NOT_FOUND"


class TestExecutionSimulation:
    """Test execution simulation."""

    @pytest.mark.asyncio
    async def test_execute_all_working_orders(
        self, provider: FakeBrokerProvider
    ) -> None:
        """Execute all working orders creates positions."""
        # Place order
        order = PreOrder(
            symbol="AAPL",
            type=OrderType.MARKET,
            side=Side.BUY,
            qty=10.0,
            limitPrice=150.0,
        )
        await provider.place_order(order)

        # Execute
        await provider.execute_all_working_orders()

        # Verify
        orders = await provider.get_orders()
        assert orders[0].status == OrderStatus.FILLED

        positions = await provider.get_positions()
        assert len(positions) == 1
        assert positions[0].symbol == "AAPL"
        assert positions[0].qty == 10.0

    @pytest.mark.asyncio
    async def test_execution_creates_execution_record(
        self, provider: FakeBrokerProvider
    ) -> None:
        """Execution creates execution record."""
        order = PreOrder(
            symbol="AAPL",
            type=OrderType.MARKET,
            side=Side.BUY,
            qty=10.0,
            limitPrice=150.0,
        )
        await provider.place_order(order)
        await provider.execute_all_working_orders()

        executions = await provider.get_executions("AAPL")
        assert len(executions) == 1
        assert executions[0].symbol == "AAPL"
        assert executions[0].qty == 10.0


class TestPositionManagement:
    """Test position operations."""

    @pytest.mark.asyncio
    async def test_close_position_full(self, provider: FakeBrokerProvider) -> None:
        """Close a full position."""
        # Create position via order + execution
        order = PreOrder(
            symbol="AAPL",
            type=OrderType.MARKET,
            side=Side.BUY,
            qty=10.0,
            limitPrice=150.0,
        )
        await provider.place_order(order)
        await provider.execute_all_working_orders()

        # Close position
        await provider.close_position("AAPL")

        # Should have created a closing order
        orders = await provider.get_orders()
        closing_order = [o for o in orders if o.side == Side.SELL][0]
        assert closing_order.qty == 10.0

    @pytest.mark.asyncio
    async def test_close_position_partial(self, provider: FakeBrokerProvider) -> None:
        """Close partial position."""
        order = PreOrder(
            symbol="AAPL",
            type=OrderType.MARKET,
            side=Side.BUY,
            qty=10.0,
            limitPrice=150.0,
        )
        await provider.place_order(order)
        await provider.execute_all_working_orders()

        await provider.close_position("AAPL", amount=5.0)

        orders = await provider.get_orders()
        closing_order = [o for o in orders if o.side == Side.SELL][0]
        assert closing_order.qty == 5.0

    @pytest.mark.asyncio
    async def test_close_nonexistent_position(
        self, provider: FakeBrokerProvider
    ) -> None:
        """Closing nonexistent position raises error."""
        with pytest.raises(ProviderException) as exc_info:
            await provider.close_position("INVALID")

        assert exc_info.value.code == "PROVIDER_BROKER_POSITION_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_edit_position_brackets(self, provider: FakeBrokerProvider) -> None:
        """Edit position brackets creates bracket orders."""
        # Create position
        order = PreOrder(
            symbol="AAPL",
            type=OrderType.MARKET,
            side=Side.BUY,
            qty=10.0,
            limitPrice=150.0,
        )
        await provider.place_order(order)
        await provider.execute_all_working_orders()

        # Edit brackets
        brackets = Brackets(stopLoss=140.0, takeProfit=160.0)
        await provider.edit_position_brackets("AAPL", brackets)

        # Should have bracket orders
        orders = await provider.get_orders()
        bracket_orders = [
            o for o in orders if o.side == Side.SELL and o.status == OrderStatus.WORKING
        ]
        assert len(bracket_orders) == 2


class TestEquityAndPnL:
    """Test equity and P&L calculations."""

    @pytest.mark.asyncio
    async def test_initial_equity(self, provider: FakeBrokerProvider) -> None:
        """Initial equity matches config."""
        equity = await provider.get_equity()
        assert equity.balance == 100000.0
        assert equity.equity == 100000.0
        assert equity.unrealizedPL == 0.0
        assert equity.realizedPL == 0.0

    @pytest.mark.asyncio
    async def test_equity_after_execution(self, provider: FakeBrokerProvider) -> None:
        """Equity updates after execution."""
        order = PreOrder(
            symbol="AAPL",
            type=OrderType.MARKET,
            side=Side.BUY,
            qty=10.0,
            limitPrice=150.0,
        )
        await provider.place_order(order)
        await provider.execute_all_working_orders()

        equity = await provider.get_equity()
        # Balance unchanged (no P&L realized yet)
        assert equity.balance == 100000.0


class TestLeverage:
    """Test leverage operations."""

    @pytest.mark.asyncio
    async def test_get_leverage_info(self, provider: FakeBrokerProvider) -> None:
        """Get leverage info for symbol."""
        params = LeverageInfoParams(
            symbol="AAPL",
            orderType=OrderType.MARKET,
            side=Side.BUY,
        )
        info = await provider.get_leverage_info(params)

        assert info.leverage == 10.0  # Default
        assert info.min == 1.0
        assert info.max == 100.0

    @pytest.mark.asyncio
    async def test_set_leverage(self, provider: FakeBrokerProvider) -> None:
        """Set leverage for symbol."""
        params = LeverageSetParams(
            symbol="AAPL",
            orderType=OrderType.MARKET,
            side=Side.BUY,
            leverage=20.0,
        )
        result = await provider.set_leverage(params)

        assert result.leverage == 20.0

        # Verify persisted
        info = await provider.get_leverage_info(
            LeverageInfoParams(symbol="AAPL", orderType=OrderType.MARKET, side=Side.BUY)
        )
        assert info.leverage == 20.0

    @pytest.mark.asyncio
    async def test_set_invalid_leverage(self, provider: FakeBrokerProvider) -> None:
        """Setting invalid leverage raises error."""
        params = LeverageSetParams(
            symbol="AAPL",
            orderType=OrderType.MARKET,
            side=Side.BUY,
            leverage=150.0,
        )

        with pytest.raises(ProviderException) as exc_info:
            await provider.set_leverage(params)

        assert exc_info.value.code == "PROVIDER_BROKER_INVALID_LEVERAGE"


class TestSubscriptions:
    """Test streaming subscriptions."""

    @pytest.mark.asyncio
    async def test_subscribe_orders(self, provider: FakeBrokerProvider) -> None:
        """Subscribe to order updates."""
        received_orders: list[PlacedOrder] = []

        async def callback(order: PlacedOrder) -> None:
            received_orders.append(order)

        sub_id = await provider.subscribe_orders(callback)
        assert sub_id.startswith("sub-")

        # Place and execute order
        order = PreOrder(
            symbol="AAPL",
            type=OrderType.MARKET,
            side=Side.BUY,
            qty=10.0,
            limitPrice=150.0,
        )
        await provider.place_order(order)
        await provider.execute_all_working_orders()

        # Should have received order update
        assert len(received_orders) == 1
        assert received_orders[0].status == OrderStatus.FILLED

        # Cleanup
        provider.unsubscribe(sub_id)

    @pytest.mark.asyncio
    async def test_subscribe_positions(self, provider: FakeBrokerProvider) -> None:
        """Subscribe to position updates."""
        received_positions: list[Position] = []

        async def callback(position: Position) -> None:
            received_positions.append(position)

        sub_id = await provider.subscribe_positions(callback)

        order = PreOrder(
            symbol="AAPL",
            type=OrderType.MARKET,
            side=Side.BUY,
            qty=10.0,
            limitPrice=150.0,
        )
        await provider.place_order(order)
        await provider.execute_all_working_orders()

        assert len(received_positions) == 1
        assert received_positions[0].symbol == "AAPL"

        provider.unsubscribe(sub_id)

    @pytest.mark.asyncio
    async def test_unsubscribe(self, provider: FakeBrokerProvider) -> None:
        """Unsubscribe stops callbacks."""
        received_orders: list[PlacedOrder] = []

        async def callback(order: PlacedOrder) -> None:
            received_orders.append(order)

        sub_id = await provider.subscribe_orders(callback)
        provider.unsubscribe(sub_id)

        # Place and execute order
        order = PreOrder(
            symbol="AAPL",
            type=OrderType.MARKET,
            side=Side.BUY,
            qty=10.0,
            limitPrice=150.0,
        )
        await provider.place_order(order)
        await provider.execute_all_working_orders()

        # Should NOT have received update
        assert len(received_orders) == 0

    @pytest.mark.asyncio
    async def test_subscribe_executions_all_symbols(
        self, provider: FakeBrokerProvider
    ) -> None:
        """Subscribe to all executions with empty symbol."""
        received_executions: list[Execution] = []

        async def callback(execution: Execution) -> None:
            received_executions.append(execution)

        # Empty string = all symbols
        sub_id = await provider.subscribe_executions("", callback)

        # Place orders for different symbols
        order1 = PreOrder(
            symbol="AAPL",
            type=OrderType.MARKET,
            side=Side.BUY,
            qty=10.0,
            limitPrice=150.0,
        )
        order2 = PreOrder(
            symbol="GOOGL",
            type=OrderType.MARKET,
            side=Side.BUY,
            qty=5.0,
            limitPrice=2800.0,
        )
        await provider.place_order(order1)
        await provider.place_order(order2)
        await provider.execute_all_working_orders()

        # Should receive executions for BOTH symbols
        assert len(received_executions) == 2
        symbols = {e.symbol for e in received_executions}
        assert symbols == {"AAPL", "GOOGL"}

        provider.unsubscribe(sub_id)

    @pytest.mark.asyncio
    async def test_subscribe_executions_specific_symbol(
        self, provider: FakeBrokerProvider
    ) -> None:
        """Subscribe to executions for specific symbol only."""
        received_executions: list[Execution] = []

        async def callback(execution: Execution) -> None:
            received_executions.append(execution)

        # Subscribe only to AAPL
        sub_id = await provider.subscribe_executions("AAPL", callback)

        # Place orders for different symbols
        order1 = PreOrder(
            symbol="AAPL",
            type=OrderType.MARKET,
            side=Side.BUY,
            qty=10.0,
            limitPrice=150.0,
        )
        order2 = PreOrder(
            symbol="GOOGL",
            type=OrderType.MARKET,
            side=Side.BUY,
            qty=5.0,
            limitPrice=2800.0,
        )
        await provider.place_order(order1)
        await provider.place_order(order2)
        await provider.execute_all_working_orders()

        # Should receive only AAPL execution
        assert len(received_executions) == 1
        assert received_executions[0].symbol == "AAPL"

        provider.unsubscribe(sub_id)


class TestReset:
    """Test reset functionality."""

    @pytest.mark.asyncio
    async def test_reset_clears_state(self, provider: FakeBrokerProvider) -> None:
        """Reset clears all state."""
        # Create some state
        order = PreOrder(
            symbol="AAPL",
            type=OrderType.MARKET,
            side=Side.BUY,
            qty=10.0,
            limitPrice=150.0,
        )
        await provider.place_order(order)
        await provider.execute_all_working_orders()

        # Reset
        provider.reset()

        # Verify cleared
        orders = await provider.get_orders()
        positions = await provider.get_positions()
        equity = await provider.get_equity()

        assert len(orders) == 0
        assert len(positions) == 0
        assert equity.balance == 100000.0
