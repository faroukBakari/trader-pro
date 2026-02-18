"""
Tests for BrokerService — bracket diffing on modify_order.

Tests that _strip_unchanged_brackets correctly diffs incoming PreOrder
bracket fields against current OrderManager state, stripping unchanged
legs to prevent TWS rejection errors (PROVIDER_TWS_201).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

if TYPE_CHECKING:
    from trading_api.shared import DatastoreInterface

from trading_api.datastores.duckdb import create_memory_datastore
from trading_api.models.broker.orders import (
    OrderStatus,
    OrderType,
    PlacedOrder,
    PreOrder,
    Side,
)
from trading_api.modules.broker.order_manager import OrderManager


@pytest.fixture
async def datastore() -> AsyncGenerator["DatastoreInterface"]:
    """Create in-memory DuckDB datastore for service tests."""
    ds = create_memory_datastore()
    yield ds
    await ds.close()


def _make_placed_order(
    id: str = "100",
    symbol: str = "AAPL",
    take_profit: float | None = 160.0,
    stop_loss: float | None = 145.0,
    trailing_stop_pips: float | None = None,
) -> PlacedOrder:
    """Create a PlacedOrder with bracket fields for diffing tests."""
    return PlacedOrder(
        id=id,
        symbol=symbol,
        type=OrderType.MARKET,
        side=Side.BUY,
        qty=100.0,
        status=OrderStatus.WORKING,
        takeProfit=take_profit,
        stopLoss=stop_loss,
        trailingStopPips=trailing_stop_pips,
    )


def _make_preorder(
    symbol: str = "AAPL",
    take_profit: float | None = 160.0,
    stop_loss: float | None = 145.0,
    trailing_stop_pips: float | None = None,
    limit_price: float | None = 150.0,
) -> PreOrder:
    """Create a PreOrder for modify_order tests."""
    return PreOrder(
        symbol=symbol,
        type=OrderType.LIMIT,
        side=Side.BUY,
        qty=100.0,
        limitPrice=limit_price,
        takeProfit=take_profit,
        stopLoss=stop_loss,
        trailingStopPips=trailing_stop_pips,
    )


async def _seed_order(datastore: "DatastoreInterface", order: PlacedOrder) -> None:
    """Seed an order directly into the table, bypassing enrichment."""
    table = datastore.table(PlacedOrder)
    await table.set(order.id, order)


async def _make_mock_service(
    datastore: "DatastoreInterface",
) -> MagicMock:
    """Create a mock BrokerService with OrderManager wired to datastore."""
    from trading_api.modules.broker.service import BrokerService

    service = MagicMock()
    service._order_manager = OrderManager(datastore=datastore)
    service.broker_provider = AsyncMock()
    # Bind real methods so unbound calls via BrokerService.method(service, ...) work
    service._strip_unchanged_brackets = (
        lambda order_id, order: BrokerService._strip_unchanged_brackets(
            service, order_id, order
        )
    )
    return service


class TestStripUnchangedBrackets:
    """Test _strip_unchanged_brackets bracket diffing logic."""

    @pytest.mark.asyncio
    async def test_all_brackets_unchanged_are_stripped(
        self, datastore: "DatastoreInterface"
    ) -> None:
        """When all bracket values match current state, they are nulled out."""
        from trading_api.modules.broker.service import BrokerService

        service = await _make_mock_service(datastore)
        await _seed_order(
            datastore,
            _make_placed_order(id="100", take_profit=160.0, stop_loss=145.0),
        )

        preorder = _make_preorder(take_profit=160.0, stop_loss=145.0)
        result = await BrokerService._strip_unchanged_brackets(service, "100", preorder)

        assert result.takeProfit is None
        assert result.stopLoss is None
        # Non-bracket fields untouched
        assert result.limitPrice == 150.0

    @pytest.mark.asyncio
    async def test_all_brackets_changed_are_kept(
        self, datastore: "DatastoreInterface"
    ) -> None:
        """When all bracket values differ from current state, they are preserved."""
        from trading_api.modules.broker.service import BrokerService

        service = await _make_mock_service(datastore)
        await _seed_order(
            datastore,
            _make_placed_order(id="100", take_profit=160.0, stop_loss=145.0),
        )

        preorder = _make_preorder(take_profit=165.0, stop_loss=140.0)
        result = await BrokerService._strip_unchanged_brackets(service, "100", preorder)

        assert result.takeProfit == 165.0
        assert result.stopLoss == 140.0

    @pytest.mark.asyncio
    async def test_mixed_changed_and_unchanged(
        self, datastore: "DatastoreInterface"
    ) -> None:
        """Only unchanged bracket fields are stripped; changed ones are kept."""
        from trading_api.modules.broker.service import BrokerService

        service = await _make_mock_service(datastore)
        await _seed_order(
            datastore,
            _make_placed_order(id="100", take_profit=160.0, stop_loss=145.0),
        )

        # TP unchanged (160), SL changed (145 → 140)
        preorder = _make_preorder(take_profit=160.0, stop_loss=140.0)
        result = await BrokerService._strip_unchanged_brackets(service, "100", preorder)

        assert result.takeProfit is None  # stripped (unchanged)
        assert result.stopLoss == 140.0  # kept (changed)

    @pytest.mark.asyncio
    async def test_unknown_order_passes_through(
        self, datastore: "DatastoreInterface"
    ) -> None:
        """When order is not in OrderManager, PreOrder is returned unchanged."""
        from trading_api.modules.broker.service import BrokerService

        service = await _make_mock_service(datastore)
        # Don't seed any orders

        preorder = _make_preorder(take_profit=160.0, stop_loss=145.0)
        result = await BrokerService._strip_unchanged_brackets(
            service, "unknown-id", preorder
        )

        assert result.takeProfit == 160.0
        assert result.stopLoss == 145.0

    @pytest.mark.asyncio
    async def test_trailing_stop_unchanged_stripped(
        self, datastore: "DatastoreInterface"
    ) -> None:
        """trailingStopPips is also diffed and stripped when unchanged."""
        from trading_api.modules.broker.service import BrokerService

        service = await _make_mock_service(datastore)
        await _seed_order(
            datastore,
            _make_placed_order(
                id="100",
                take_profit=None,
                stop_loss=None,
                trailing_stop_pips=50.0,
            ),
        )

        preorder = _make_preorder(
            take_profit=None, stop_loss=None, trailing_stop_pips=50.0
        )
        result = await BrokerService._strip_unchanged_brackets(service, "100", preorder)

        assert result.trailingStopPips is None  # stripped

    @pytest.mark.asyncio
    async def test_none_brackets_not_stripped(
        self, datastore: "DatastoreInterface"
    ) -> None:
        """Brackets that are None in PreOrder are left alone (not false-positive stripped)."""
        from trading_api.modules.broker.service import BrokerService

        service = await _make_mock_service(datastore)
        await _seed_order(
            datastore,
            _make_placed_order(id="100", take_profit=160.0, stop_loss=145.0),
        )

        # PreOrder has no brackets at all
        preorder = _make_preorder(take_profit=None, stop_loss=None)
        result = await BrokerService._strip_unchanged_brackets(service, "100", preorder)

        # None stays None — guard clause `order.takeProfit is not None` prevents stripping
        assert result.takeProfit is None
        assert result.stopLoss is None


class TestModifyOrderIntegration:
    """Test that modify_order calls _strip_unchanged_brackets before provider."""

    @pytest.mark.asyncio
    async def test_modify_order_strips_then_forwards(
        self, datastore: "DatastoreInterface"
    ) -> None:
        """modify_order strips unchanged brackets, then forwards to provider."""
        from trading_api.modules.broker.service import BrokerService

        service = await _make_mock_service(datastore)
        await _seed_order(
            datastore,
            _make_placed_order(id="100", take_profit=160.0, stop_loss=145.0),
        )

        # Modify only limitPrice — brackets unchanged
        preorder = _make_preorder(take_profit=160.0, stop_loss=145.0, limit_price=155.0)

        await BrokerService.modify_order(service, "100", preorder, user_id="test")

        # Provider should have been called with stripped brackets
        service.broker_provider.modify_order.assert_awaited_once()
        call_args = service.broker_provider.modify_order.call_args
        forwarded_order: PreOrder = call_args[0][1]
        assert forwarded_order.takeProfit is None
        assert forwarded_order.stopLoss is None
        assert forwarded_order.limitPrice == 155.0
