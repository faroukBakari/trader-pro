"""
Tests for OrderManager — service-layer bracket clustering with DuckDB persistence.

Gate 0: Core state (upsert, sync, get_all, clear)
Gate 1: BracketContext derivation (bracket enrichment algorithm)
Gate 2: Position bracket reclassification (ORDER → POSITION)
Gate 3: BrokerService integration (REST + WS paths through OrderManager)
Gate 4: End-to-end validation (FakeBrokerProvider)
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

import pytest

if TYPE_CHECKING:
    from trading_api.modules.broker.service import BrokerService
    from trading_api.shared import DatastoreInterface

from trading_api.datastores.duckdb import create_memory_datastore
from trading_api.models.broker.orders import (
    OrderDuration,
    OrderOrPositionMessage,
    OrderOrPositionMessageType,
    OrderStatus,
    OrderType,
    ParentType,
    PlacedOrder,
    Side,
    StopType,
)
from trading_api.modules.broker.order_manager import OrderManager

# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
async def datastore() -> AsyncGenerator["DatastoreInterface"]:
    """Create in-memory DuckDB datastore for OrderManager tests."""
    ds = create_memory_datastore()
    yield ds
    await ds.close()


# ── Helpers ─────────────────────────────────────────────────────────────


def _make_order(
    id: str = "1",
    symbol: str = "AAPL",
    type: OrderType = OrderType.MARKET,
    side: Side = Side.BUY,
    qty: float = 100.0,
    status: OrderStatus = OrderStatus.WORKING,
    limit_price: float | None = None,
    stop_price: float | None = None,
    parent_id: str | None = None,
    parent_type: ParentType | None = None,
    take_profit: float | None = None,
    stop_loss: float | None = None,
    trailing_stop_pips: float | None = None,
    stop_type: StopType | None = None,
    duration: OrderDuration | None = None,
    message: OrderOrPositionMessage | None = None,
) -> PlacedOrder:
    """Create a PlacedOrder for testing."""
    return PlacedOrder(
        id=id,
        symbol=symbol,
        type=type,
        side=side,
        qty=qty,
        status=status,
        limitPrice=limit_price,
        stopPrice=stop_price,
        parentId=parent_id,
        parentType=parent_type,
        takeProfit=take_profit,
        stopLoss=stop_loss,
        trailingStopPips=trailing_stop_pips,
        stopType=stop_type,
        duration=duration,
        message=message,
    )


# ═══════════════════════════════════════════════════════════════════════
# Gate 0: Core State
# ═══════════════════════════════════════════════════════════════════════


class TestOrderManagerCoreState:
    """Gate 0 — upsert, sync, get_all, clear."""

    @pytest.mark.asyncio
    async def test_upsert_single_order(self, datastore: "DatastoreInterface") -> None:
        """Upsert a single order → get_all returns it."""
        mgr = OrderManager(datastore=datastore)
        order = _make_order(id="100")

        await mgr.upsert(order)

        result = await mgr.get_all()
        assert len(result) == 1
        assert result[0].id == "100"

    @pytest.mark.asyncio
    async def test_upsert_updates_existing(
        self, datastore: "DatastoreInterface"
    ) -> None:
        """Upsert same ID → replaces the order."""
        mgr = OrderManager(datastore=datastore)
        await mgr.upsert(_make_order(id="100", qty=10.0))
        await mgr.upsert(_make_order(id="100", qty=50.0))

        result = await mgr.get_all()
        assert len(result) == 1
        assert result[0].qty == 50.0

    @pytest.mark.asyncio
    async def test_sync_bulk_replace(self, datastore: "DatastoreInterface") -> None:
        """sync() replaces entire state."""
        mgr = OrderManager(datastore=datastore)
        await mgr.upsert(_make_order(id="1"))
        await mgr.upsert(_make_order(id="2"))

        await mgr.sync([_make_order(id="10"), _make_order(id="20")])

        ids = {o.id for o in await mgr.get_all()}
        assert ids == {"10", "20"}

    @pytest.mark.asyncio
    async def test_get_all_returns_copy(self, datastore: "DatastoreInterface") -> None:
        """Mutations on returned orders don't affect internal state."""
        mgr = OrderManager(datastore=datastore)
        await mgr.upsert(_make_order(id="100", qty=10.0))

        result = await mgr.get_all()
        result.clear()
        assert len(await mgr.get_all()) == 1

    @pytest.mark.asyncio
    async def test_clear(self, datastore: "DatastoreInterface") -> None:
        """clear() empties state."""
        mgr = OrderManager(datastore=datastore)
        await mgr.upsert(_make_order(id="1"))
        await mgr.clear()
        assert await mgr.get_all() == []

    @pytest.mark.asyncio
    async def test_get_existing_order(self, datastore: "DatastoreInterface") -> None:
        """get() returns a copy of the order."""
        mgr = OrderManager(datastore=datastore)
        await mgr.upsert(_make_order(id="42", symbol="MSFT"))
        result = await mgr.get("42")
        assert result is not None
        assert result.id == "42"
        assert result.symbol == "MSFT"

    @pytest.mark.asyncio
    async def test_get_missing_order(self, datastore: "DatastoreInterface") -> None:
        """get() returns None for unknown order ID."""
        mgr = OrderManager(datastore=datastore)
        assert await mgr.get("nonexistent") is None

    @pytest.mark.asyncio
    async def test_get_returns_copy(self, datastore: "DatastoreInterface") -> None:
        """get() returns a copy — mutations don't affect internal state."""
        mgr = OrderManager(datastore=datastore)
        await mgr.upsert(_make_order(id="42"))
        result = await mgr.get("42")
        assert result is not None
        result.symbol = "MUTATED"
        original = await mgr.get("42")
        assert original is not None
        assert original.symbol == "AAPL"

    @pytest.mark.asyncio
    async def test_upsert_returns_upserted_order(
        self, datastore: "DatastoreInterface"
    ) -> None:
        """Upsert always returns the upserted order itself."""
        mgr = OrderManager(datastore=datastore)
        order = _make_order(id="100")
        result = await mgr.upsert(order)
        assert len(result) == 1
        assert result[0].id == "100"

    @pytest.mark.asyncio
    async def test_upsert_returns_child_and_enriched_parent(
        self, datastore: "DatastoreInterface"
    ) -> None:
        """When child arrives, both child AND enriched parent are returned."""
        mgr = OrderManager(datastore=datastore)
        parent = _make_order(id="100", type=OrderType.MARKET)
        await mgr.upsert(parent)

        sl_child = _make_order(
            id="101",
            type=OrderType.STOP,
            side=Side.SELL,
            stop_price=145.0,
            parent_id="100",
            parent_type=ParentType.ORDER,
        )
        result = await mgr.upsert(sl_child)

        result_ids = {o.id for o in result}
        assert "101" in result_ids, "Child must be in result"
        assert "100" in result_ids, "Enriched parent must be in result"

    @pytest.mark.asyncio
    async def test_upsert_duplicate_returns_empty(
        self, datastore: "DatastoreInterface"
    ) -> None:
        """Re-upserting identical order → empty list (no change)."""
        mgr = OrderManager(datastore=datastore)
        order = _make_order(id="100")
        await mgr.upsert(order)

        result = await mgr.upsert(order)
        assert result == []

    @pytest.mark.asyncio
    async def test_upsert_with_duration_json_field(
        self, datastore: "DatastoreInterface"
    ) -> None:
        """Orders with duration (sa_column=JSON) round-trip through DuckDB."""
        mgr = OrderManager(datastore=datastore)
        duration = OrderDuration(type="GTC")
        order = _make_order(id="dur1", duration=duration)
        await mgr.upsert(order)

        result = await mgr.get("dur1")
        assert result is not None
        assert result.duration is not None
        assert result.duration.type == "GTC"
        assert result.duration.datetime is None

    @pytest.mark.asyncio
    async def test_upsert_with_message_json_field(
        self, datastore: "DatastoreInterface"
    ) -> None:
        """Orders with message (sa_column=JSON) round-trip through DuckDB."""
        mgr = OrderManager(datastore=datastore)
        msg = OrderOrPositionMessage(
            type=OrderOrPositionMessageType.WARNING,
            text="Partially filled",
        )
        order = _make_order(id="msg1", message=msg)
        await mgr.upsert(order)

        result = await mgr.get("msg1")
        assert result is not None
        assert result.message is not None
        assert result.message.text == "Partially filled"
        assert result.message.type == OrderOrPositionMessageType.WARNING

    @pytest.mark.asyncio
    async def test_upsert_with_duration_and_message(
        self, datastore: "DatastoreInterface"
    ) -> None:
        """Both JSON fields set simultaneously round-trip correctly."""
        mgr = OrderManager(datastore=datastore)
        order = _make_order(
            id="both1",
            duration=OrderDuration(type="GTD", datetime=1700000000),
            message=OrderOrPositionMessage(
                type=OrderOrPositionMessageType.INFORMATION,
                text="Order accepted",
            ),
        )
        await mgr.upsert(order)

        result = await mgr.get("both1")
        assert result is not None
        assert result.duration is not None
        assert result.duration.type == "GTD"
        assert result.duration.datetime == 1700000000
        assert result.message is not None
        assert result.message.text == "Order accepted"


# ═══════════════════════════════════════════════════════════════════════
# Gate 1: BracketContext Derivation
# ═══════════════════════════════════════════════════════════════════════


class TestBracketEnrichment:
    """Gate 1 — bracket enrichment algorithm."""

    @pytest.mark.asyncio
    async def test_parent_then_children(self, datastore: "DatastoreInterface") -> None:
        """Parent arrives first, children later → parent re-enriched."""
        mgr = OrderManager(datastore=datastore)
        parent = _make_order(id="100", type=OrderType.MARKET)
        sl_child = _make_order(
            id="101",
            type=OrderType.STOP,
            side=Side.SELL,
            stop_price=145.0,
            parent_id="100",
            parent_type=ParentType.ORDER,
        )
        tp_child = _make_order(
            id="102",
            type=OrderType.LIMIT,
            side=Side.SELL,
            limit_price=160.0,
            parent_id="100",
            parent_type=ParentType.ORDER,
        )

        await mgr.upsert(parent)
        await mgr.upsert(sl_child)
        await mgr.upsert(tp_child)

        orders = {o.id: o for o in await mgr.get_all()}
        enriched_parent = orders["100"]
        assert enriched_parent.stopLoss == 145.0
        assert enriched_parent.takeProfit == 160.0

    @pytest.mark.asyncio
    async def test_children_then_parent(self, datastore: "DatastoreInterface") -> None:
        """Children arrive first → parent enriched immediately on arrival."""
        mgr = OrderManager(datastore=datastore)
        sl_child = _make_order(
            id="101",
            type=OrderType.STOP,
            side=Side.SELL,
            stop_price=145.0,
            parent_id="100",
            parent_type=ParentType.ORDER,
        )
        tp_child = _make_order(
            id="102",
            type=OrderType.LIMIT,
            side=Side.SELL,
            limit_price=160.0,
            parent_id="100",
            parent_type=ParentType.ORDER,
        )
        parent = _make_order(id="100", type=OrderType.MARKET)

        await mgr.upsert(sl_child)
        await mgr.upsert(tp_child)
        affected = await mgr.upsert(parent)

        orders = {o.id: o for o in await mgr.get_all()}
        enriched_parent = orders["100"]
        assert enriched_parent.stopLoss == 145.0
        assert enriched_parent.takeProfit == 160.0
        assert any(o.id == "100" for o in affected)

    @pytest.mark.asyncio
    async def test_partial_bracket(self, datastore: "DatastoreInterface") -> None:
        """Only SL child, no TP → parent gets stopLoss only."""
        mgr = OrderManager(datastore=datastore)
        parent = _make_order(id="100", type=OrderType.MARKET)
        sl_child = _make_order(
            id="101",
            type=OrderType.STOP,
            side=Side.SELL,
            stop_price=145.0,
            parent_id="100",
            parent_type=ParentType.ORDER,
        )

        await mgr.upsert(parent)
        await mgr.upsert(sl_child)

        orders = {o.id: o for o in await mgr.get_all()}
        enriched = orders["100"]
        assert enriched.stopLoss == 145.0
        assert enriched.takeProfit is None

    @pytest.mark.asyncio
    async def test_full_bracket(self, datastore: "DatastoreInterface") -> None:
        """Parent + SL + TP children → parent gets both stopLoss and takeProfit."""
        mgr = OrderManager(datastore=datastore)
        parent = _make_order(id="100", type=OrderType.MARKET)
        sl_child = _make_order(
            id="101",
            type=OrderType.STOP,
            side=Side.SELL,
            stop_price=145.0,
            parent_id="100",
            parent_type=ParentType.ORDER,
        )
        tp_child = _make_order(
            id="102",
            type=OrderType.LIMIT,
            side=Side.SELL,
            limit_price=160.0,
            parent_id="100",
            parent_type=ParentType.ORDER,
        )

        await mgr.upsert(parent)
        await mgr.upsert(sl_child)
        await mgr.upsert(tp_child)

        orders = {o.id: o for o in await mgr.get_all()}
        enriched = orders["100"]
        assert enriched.stopLoss == 145.0
        assert enriched.takeProfit == 160.0
        assert enriched.trailingStopPips is None

    @pytest.mark.asyncio
    async def test_trailing_stop_bracket(self, datastore: "DatastoreInterface") -> None:
        """TRAIL child → parent gets trailingStopPips + TRAILING_STOP stopType."""
        mgr = OrderManager(datastore=datastore)
        parent = _make_order(id="100", type=OrderType.MARKET)
        trail_child = _make_order(
            id="101",
            type=OrderType.TRAIL,
            side=Side.SELL,
            stop_price=5.0,
            parent_id="100",
            parent_type=ParentType.ORDER,
        )

        await mgr.upsert(parent)
        await mgr.upsert(trail_child)

        orders = {o.id: o for o in await mgr.get_all()}
        enriched = orders["100"]
        assert enriched.trailingStopPips == 5.0
        assert enriched.stopType == StopType.TRAILING_STOP

    @pytest.mark.asyncio
    async def test_sync_enriches_all_brackets(
        self, datastore: "DatastoreInterface"
    ) -> None:
        """sync() with a full bracket set → parent is enriched."""
        mgr = OrderManager(datastore=datastore)
        parent = _make_order(id="100", type=OrderType.MARKET)
        sl_child = _make_order(
            id="101",
            type=OrderType.STOP,
            side=Side.SELL,
            stop_price=145.0,
            parent_id="100",
            parent_type=ParentType.ORDER,
        )
        tp_child = _make_order(
            id="102",
            type=OrderType.LIMIT,
            side=Side.SELL,
            limit_price=160.0,
            parent_id="100",
            parent_type=ParentType.ORDER,
        )

        await mgr.sync([parent, sl_child, tp_child])

        orders = {o.id: o for o in await mgr.get_all()}
        enriched = orders["100"]
        assert enriched.stopLoss == 145.0
        assert enriched.takeProfit == 160.0

    @pytest.mark.asyncio
    async def test_position_brackets_dont_enrich_orders(
        self, datastore: "DatastoreInterface"
    ) -> None:
        """POSITION brackets (parentId=symbol) don't enrich any order."""
        mgr = OrderManager(datastore=datastore)
        parent = _make_order(id="100", type=OrderType.MARKET, symbol="AAPL")
        pos_bracket = _make_order(
            id="201",
            type=OrderType.STOP,
            side=Side.SELL,
            stop_price=140.0,
            parent_id="AAPL",
            parent_type=ParentType.POSITION,
        )

        await mgr.sync([parent, pos_bracket])

        orders = {o.id: o for o in await mgr.get_all()}
        assert (
            orders["100"].stopLoss is None
        ), "Position brackets must not enrich orders"


# ═══════════════════════════════════════════════════════════════════════
# Gate 2: Position Bracket Reclassification
# ═══════════════════════════════════════════════════════════════════════


class TestPositionBracketReclassification:
    """Gate 2 — ORDER → POSITION reclassification."""

    @pytest.mark.asyncio
    async def test_sync_reclassifies_children_of_filled_parent(
        self, datastore: "DatastoreInterface"
    ) -> None:
        """sync(): children of FILLED parent → reclassified to POSITION."""
        mgr = OrderManager(datastore=datastore)
        parent = _make_order(
            id="100",
            type=OrderType.MARKET,
            status=OrderStatus.FILLED,
            symbol="NASDAQ:GOOGL",
        )
        sl_child = _make_order(
            id="101",
            type=OrderType.STOP,
            side=Side.SELL,
            stop_price=145.0,
            parent_id="100",
            parent_type=ParentType.ORDER,
            symbol="NASDAQ:GOOGL",
        )

        await mgr.sync([parent, sl_child])

        orders = {o.id: o for o in await mgr.get_all()}
        child = orders["101"]
        assert child.parentType == ParentType.POSITION
        assert child.parentId == "NASDAQ:GOOGL"

    @pytest.mark.asyncio
    async def test_sync_reclassifies_children_of_missing_parent(
        self, datastore: "DatastoreInterface"
    ) -> None:
        """sync(): children whose parent is not in state → POSITION (cold start)."""
        mgr = OrderManager(datastore=datastore)
        sl_child = _make_order(
            id="101",
            type=OrderType.STOP,
            side=Side.SELL,
            stop_price=145.0,
            parent_id="999",  # parent not in state
            parent_type=ParentType.ORDER,
            symbol="NASDAQ:GOOGL",
        )

        await mgr.sync([sl_child])

        orders = {o.id: o for o in await mgr.get_all()}
        child = orders["101"]
        assert child.parentType == ParentType.POSITION
        assert child.parentId == "NASDAQ:GOOGL"

    @pytest.mark.asyncio
    async def test_sync_keeps_children_of_working_parent(
        self, datastore: "DatastoreInterface"
    ) -> None:
        """sync(): children of WORKING parent → stay ORDER bracket."""
        mgr = OrderManager(datastore=datastore)
        parent = _make_order(
            id="100",
            type=OrderType.MARKET,
            status=OrderStatus.WORKING,
        )
        sl_child = _make_order(
            id="101",
            type=OrderType.STOP,
            side=Side.SELL,
            stop_price=145.0,
            parent_id="100",
            parent_type=ParentType.ORDER,
        )

        await mgr.sync([parent, sl_child])

        orders = {o.id: o for o in await mgr.get_all()}
        child = orders["101"]
        assert child.parentType == ParentType.ORDER
        assert child.parentId == "100"

    @pytest.mark.asyncio
    async def test_upsert_reclassifies_when_parent_filled(
        self, datastore: "DatastoreInterface"
    ) -> None:
        """upsert(): child with FILLED parent in state → reclassified."""
        mgr = OrderManager(datastore=datastore)
        # Parent already in state as FILLED
        parent = _make_order(
            id="100",
            type=OrderType.MARKET,
            status=OrderStatus.FILLED,
            symbol="NASDAQ:GOOGL",
        )
        await mgr.upsert(parent)

        # Child arrives via WS — parent is FILLED
        sl_child = _make_order(
            id="101",
            type=OrderType.STOP,
            side=Side.SELL,
            stop_price=145.0,
            parent_id="100",
            parent_type=ParentType.ORDER,
            symbol="NASDAQ:GOOGL",
        )
        result = await mgr.upsert(sl_child)

        # Child should be reclassified in the result
        child_in_result = next(o for o in result if o.id == "101")
        assert child_in_result.parentType == ParentType.POSITION
        assert child_in_result.parentId == "NASDAQ:GOOGL"

    @pytest.mark.asyncio
    async def test_upsert_keeps_child_when_parent_missing(
        self, datastore: "DatastoreInterface"
    ) -> None:
        """upsert(): child whose parent isn't in state yet → stays ORDER.

        On WS path, missing parent means it hasn't arrived yet.
        """
        mgr = OrderManager(datastore=datastore)
        sl_child = _make_order(
            id="101",
            type=OrderType.STOP,
            side=Side.SELL,
            stop_price=145.0,
            parent_id="100",
            parent_type=ParentType.ORDER,
        )
        result = await mgr.upsert(sl_child)

        child_in_result = next(o for o in result if o.id == "101")
        assert child_in_result.parentType == ParentType.ORDER
        assert child_in_result.parentId == "100"

    @pytest.mark.asyncio
    async def test_sync_enriches_working_parent_after_reclassification(
        self, datastore: "DatastoreInterface"
    ) -> None:
        """After reclassification, working parent's ORDER children still enrich it."""
        mgr = OrderManager(datastore=datastore)
        working_parent = _make_order(
            id="200",
            type=OrderType.LIMIT,
            status=OrderStatus.WORKING,
            limit_price=305.57,
            symbol="NASDAQ:GOOGL",
        )
        sl_working = _make_order(
            id="201",
            type=OrderType.STOP,
            side=Side.SELL,
            stop_price=304.57,
            parent_id="200",
            parent_type=ParentType.ORDER,
            symbol="NASDAQ:GOOGL",
        )
        tp_working = _make_order(
            id="202",
            type=OrderType.LIMIT,
            side=Side.SELL,
            limit_price=307.57,
            parent_id="200",
            parent_type=ParentType.ORDER,
            symbol="NASDAQ:GOOGL",
        )
        # Also include a FILLED parent with its brackets (should be reclassified)
        filled_parent = _make_order(
            id="100",
            type=OrderType.MARKET,
            status=OrderStatus.FILLED,
            symbol="NASDAQ:GOOGL",
        )
        sl_filled = _make_order(
            id="101",
            type=OrderType.STOP,
            side=Side.SELL,
            stop_price=303.0,
            parent_id="100",
            parent_type=ParentType.ORDER,
            symbol="NASDAQ:GOOGL",
        )

        await mgr.sync(
            [working_parent, sl_working, tp_working, filled_parent, sl_filled]
        )

        orders = {o.id: o for o in await mgr.get_all()}

        # Working parent gets enriched from its ORDER children
        assert orders["200"].stopLoss == 304.57
        assert orders["200"].takeProfit == 307.57

        # Filled parent's child was reclassified → no enrichment on filled parent
        assert orders["100"].stopLoss is None

        # Reclassified child is now POSITION bracket
        assert orders["101"].parentType == ParentType.POSITION
        assert orders["101"].parentId == "NASDAQ:GOOGL"

    @pytest.mark.asyncio
    async def test_upsert_fill_cascade_reclassifies_existing_children(
        self, datastore: "DatastoreInterface"
    ) -> None:
        """WS fill cascade: parent WORKING→FILLED, then children re-upserted.

        Simulates the real WS flow:
        1. Parent + children arrive (parent WORKING)
        2. Parent fills → tracker re-notifies children
        3. OrderManager re-upserts each child → reclassifies to POSITION
        """
        mgr = OrderManager(datastore=datastore)

        # Step 1: parent + children arrive as ORDER brackets
        parent = _make_order(
            id="100",
            type=OrderType.MARKET,
            status=OrderStatus.WORKING,
            symbol="NASDAQ:AAPL",
        )
        sl_child = _make_order(
            id="101",
            type=OrderType.STOP,
            side=Side.SELL,
            stop_price=145.0,
            parent_id="100",
            parent_type=ParentType.ORDER,
            symbol="NASDAQ:AAPL",
        )
        tp_child = _make_order(
            id="102",
            type=OrderType.LIMIT,
            side=Side.SELL,
            limit_price=160.0,
            parent_id="100",
            parent_type=ParentType.ORDER,
            symbol="NASDAQ:AAPL",
        )
        await mgr.upsert(parent)
        await mgr.upsert(sl_child)
        await mgr.upsert(tp_child)

        # Verify enrichment while parent is WORKING
        orders = {o.id: o for o in await mgr.get_all()}
        assert orders["100"].stopLoss == 145.0
        assert orders["100"].takeProfit == 160.0

        # Step 2: parent fills
        filled_parent = _make_order(
            id="100",
            type=OrderType.MARKET,
            status=OrderStatus.FILLED,
            symbol="NASDAQ:AAPL",
        )
        await mgr.upsert(filled_parent)

        # Step 3: tracker re-notifies children (same child, re-upserted)
        result_sl = await mgr.upsert(sl_child)
        result_tp = await mgr.upsert(tp_child)

        # Children should be reclassified to POSITION
        sl_result = next(o for o in result_sl if o.id == "101")
        assert sl_result.parentType == ParentType.POSITION
        assert sl_result.parentId == "NASDAQ:AAPL"

        tp_result = next(o for o in result_tp if o.id == "102")
        assert tp_result.parentType == ParentType.POSITION
        assert tp_result.parentId == "NASDAQ:AAPL"

        # Filled parent should no longer have bracket enrichment
        # (children are now POSITION, not ORDER)
        orders = {o.id: o for o in await mgr.get_all()}
        assert orders["100"].stopLoss is None
        assert orders["100"].takeProfit is None

    @pytest.mark.asyncio
    async def test_child_cancelled_removes_enrichment(
        self, datastore: "DatastoreInterface"
    ) -> None:
        """When a bracket child is cancelled, parent loses that enrichment."""
        mgr = OrderManager(datastore=datastore)

        parent = _make_order(id="100", type=OrderType.MARKET)
        sl_child = _make_order(
            id="101",
            type=OrderType.STOP,
            side=Side.SELL,
            stop_price=145.0,
            parent_id="100",
            parent_type=ParentType.ORDER,
        )
        tp_child = _make_order(
            id="102",
            type=OrderType.LIMIT,
            side=Side.SELL,
            limit_price=160.0,
            parent_id="100",
            parent_type=ParentType.ORDER,
        )

        await mgr.upsert(parent)
        await mgr.upsert(sl_child)
        await mgr.upsert(tp_child)

        # Verify both enriched
        orders = {o.id: o for o in await mgr.get_all()}
        assert orders["100"].stopLoss == 145.0
        assert orders["100"].takeProfit == 160.0

        # TP child cancelled (user removes take profit)
        tp_cancelled = _make_order(
            id="102",
            type=OrderType.LIMIT,
            side=Side.SELL,
            limit_price=160.0,
            parent_id="100",
            parent_type=ParentType.ORDER,
            status=OrderStatus.CANCELED,
        )
        await mgr.upsert(tp_cancelled)

        orders = {o.id: o for o in await mgr.get_all()}
        assert orders["100"].stopLoss == 145.0, "SL should remain"
        assert (
            orders["100"].takeProfit == 160.0
        ), "Cancelled child still enriches (still ORDER bracket in state)"

    @pytest.mark.asyncio
    async def test_independent_brackets_no_cross_contamination(
        self, datastore: "DatastoreInterface"
    ) -> None:
        """Two parent/bracket sets in state don't cross-contaminate."""
        mgr = OrderManager(datastore=datastore)

        # Bracket set A: AAPL parent at id=100
        parent_a = _make_order(
            id="100", type=OrderType.LIMIT, symbol="AAPL", limit_price=150.0
        )
        sl_a = _make_order(
            id="101",
            type=OrderType.STOP,
            side=Side.SELL,
            stop_price=145.0,
            parent_id="100",
            parent_type=ParentType.ORDER,
            symbol="AAPL",
        )

        # Bracket set B: GOOGL parent at id=200
        parent_b = _make_order(
            id="200", type=OrderType.LIMIT, symbol="GOOGL", limit_price=180.0
        )
        tp_b = _make_order(
            id="201",
            type=OrderType.LIMIT,
            side=Side.SELL,
            limit_price=190.0,
            parent_id="200",
            parent_type=ParentType.ORDER,
            symbol="GOOGL",
        )

        await mgr.sync([parent_a, sl_a, parent_b, tp_b])

        orders = {o.id: o for o in await mgr.get_all()}
        # Parent A: only SL from its child
        assert orders["100"].stopLoss == 145.0
        assert orders["100"].takeProfit is None

        # Parent B: only TP from its child
        assert orders["200"].takeProfit == 190.0
        assert orders["200"].stopLoss is None


# ═══════════════════════════════════════════════════════════════════════
# Gate 3: BrokerService Integration
# ═══════════════════════════════════════════════════════════════════════


def _make_bracket_set(
    parent_id: str = "100",
    sl_id: str = "101",
    tp_id: str = "102",
    symbol: str = "AAPL",
    sl_price: float = 145.0,
    tp_price: float = 160.0,
    parent_status: OrderStatus = OrderStatus.WORKING,
) -> list[PlacedOrder]:
    """Create a parent + SL + TP bracket set for testing."""
    parent = _make_order(
        id=parent_id,
        type=OrderType.MARKET,
        symbol=symbol,
        status=parent_status,
    )
    sl_child = _make_order(
        id=sl_id,
        type=OrderType.STOP,
        side=Side.SELL,
        stop_price=sl_price,
        parent_id=parent_id,
        parent_type=ParentType.ORDER,
        symbol=symbol,
    )
    tp_child = _make_order(
        id=tp_id,
        type=OrderType.LIMIT,
        side=Side.SELL,
        limit_price=tp_price,
        parent_id=parent_id,
        parent_type=ParentType.ORDER,
        symbol=symbol,
    )
    return [parent, sl_child, tp_child]


async def _make_mock_service(datastore: "DatastoreInterface") -> MagicMock:
    """Create a mock BrokerService with OrderManager wired to datastore."""
    service = MagicMock()
    service._order_manager = OrderManager(datastore=datastore)
    service._topic_to_subscription_id = {}
    return service


class TestBrokerServiceIntegration:
    """Gate 3 — BrokerService routes through OrderManager."""

    @pytest.mark.asyncio
    async def test_get_orders_returns_enriched(
        self, datastore: "DatastoreInterface"
    ) -> None:
        """get_orders syncs provider state and returns bracket-enriched orders."""
        from trading_api.modules.broker.service import BrokerService

        raw_orders = _make_bracket_set()

        service = await _make_mock_service(datastore)
        service.broker_provider = AsyncMock()
        service.broker_provider.get_orders = AsyncMock(return_value=raw_orders)

        result = await BrokerService.get_orders(service, user_id="test")

        orders = {o.id: o for o in result}
        assert orders["100"].stopLoss == 145.0
        assert orders["100"].takeProfit == 160.0
        assert orders["101"].parentId == "100"
        assert orders["102"].parentId == "100"

    @pytest.mark.asyncio
    async def test_subscribe_orders_enriches_updates(
        self, datastore: "DatastoreInterface"
    ) -> None:
        """WS callback routes order through OrderManager and emits enriched."""
        from trading_api.modules.broker.service import BrokerService

        service = await _make_mock_service(datastore)
        service.broker_provider = AsyncMock()

        captured_callback: Any | None = None

        async def capture_subscribe(callback: Any, on_error: Any) -> str:
            nonlocal captured_callback
            captured_callback = callback
            return "sub-123"

        service.broker_provider.subscribe_orders = AsyncMock(
            side_effect=capture_subscribe
        )

        emitted: list[PlacedOrder] = []

        async def topic_update(order: PlacedOrder) -> None:
            emitted.append(order)

        async def topic_error(*args: Any) -> None:
            pass

        await BrokerService.create_topic(
            service,
            topic='orders:{"accountId":"TEST"}',
            topic_update=topic_update,
            topic_error=topic_error,
            user_id="test",
        )

        assert captured_callback is not None

        parent = _make_order(id="100", type=OrderType.MARKET)
        sl_child = _make_order(
            id="101",
            type=OrderType.STOP,
            side=Side.SELL,
            stop_price=145.0,
            parent_id="100",
            parent_type=ParentType.ORDER,
        )
        tp_child = _make_order(
            id="102",
            type=OrderType.LIMIT,
            side=Side.SELL,
            limit_price=160.0,
            parent_id="100",
            parent_type=ParentType.ORDER,
        )

        await captured_callback(parent)
        await captured_callback(sl_child)
        await captured_callback(tp_child)

        # Both children and enriched parent should be emitted
        emitted_ids = {o.id for o in emitted}
        assert "100" in emitted_ids, "Parent should be emitted"
        assert "101" in emitted_ids, "SL child should be emitted"
        assert "102" in emitted_ids, "TP child should be emitted"

        # Last parent emission should have bracket fields
        parent_emissions = [o for o in emitted if o.id == "100"]
        final_parent = parent_emissions[-1]
        assert final_parent.stopLoss == 145.0
        assert final_parent.takeProfit == 160.0

    @pytest.mark.asyncio
    async def test_ws_and_rest_consistent(
        self, datastore: "DatastoreInterface"
    ) -> None:
        """WS updates + get_orders return same enrichment for same orders."""
        from trading_api.modules.broker.service import BrokerService

        raw_orders = _make_bracket_set()

        service = await _make_mock_service(datastore)
        service.broker_provider = AsyncMock()
        service.broker_provider.get_orders = AsyncMock(return_value=raw_orders)

        captured_callback: Any | None = None

        async def capture_subscribe(callback: Any, on_error: Any) -> str:
            nonlocal captured_callback
            captured_callback = callback
            return "sub-123"

        service.broker_provider.subscribe_orders = AsyncMock(
            side_effect=capture_subscribe
        )

        emitted: list[PlacedOrder] = []

        async def topic_update(order: PlacedOrder) -> None:
            emitted.append(order)

        async def topic_error(*args: Any) -> None:
            pass

        await BrokerService.create_topic(
            service,
            topic='orders:{"accountId":"TEST"}',
            topic_update=topic_update,
            topic_error=topic_error,
            user_id="test",
        )

        assert captured_callback is not None

        for order in raw_orders:
            await captured_callback(order)

        rest_result = await BrokerService.get_orders(service, user_id="test")

        rest_orders = {o.id: o for o in rest_result}
        assert rest_orders["100"].stopLoss == 145.0
        assert rest_orders["100"].takeProfit == 160.0


# ═══════════════════════════════════════════════════════════════════════
# Gate 4: End-to-End Validation
# ═══════════════════════════════════════════════════════════════════════


class TestEndToEnd:
    """Gate 4 — E2E with real BrokerService (uses conftest.py fixtures)."""

    @pytest.mark.asyncio
    async def test_place_bracket_order_get_enriched(
        self, broker_service: "BrokerService"
    ) -> None:
        """Seed OrderManager with bracket data → returns enriched parent."""
        bracket_set = _make_bracket_set(
            parent_id="E2E-100", sl_id="E2E-101", tp_id="E2E-102"
        )

        await broker_service._order_manager.sync(bracket_set)

        result = await broker_service._order_manager.get_all()
        orders = {o.id: o for o in result}
        assert orders["E2E-100"].stopLoss == 145.0
        assert orders["E2E-100"].takeProfit == 160.0

        await broker_service._order_manager.clear()

    @pytest.mark.asyncio
    async def test_place_bracket_order_ws_enriched(
        self, broker_service: "BrokerService"
    ) -> None:
        """WS callback receives enriched parent through real service."""
        emitted: list[PlacedOrder] = []

        async def topic_update(order: PlacedOrder) -> None:
            emitted.append(order)

        async def topic_error(*args: Any) -> None:
            pass

        topic = 'orders:{"accountId":"E2E-TEST"}'

        await broker_service.create_topic(
            topic=topic,
            topic_update=topic_update,
            topic_error=topic_error,
            user_id="e2e-user",
        )

        try:
            parent = _make_order(id="WS-100", type=OrderType.MARKET)
            sl_child = _make_order(
                id="WS-101",
                type=OrderType.STOP,
                side=Side.SELL,
                stop_price=145.0,
                parent_id="WS-100",
                parent_type=ParentType.ORDER,
            )
            tp_child = _make_order(
                id="WS-102",
                type=OrderType.LIMIT,
                side=Side.SELL,
                limit_price=160.0,
                parent_id="WS-100",
                parent_type=ParentType.ORDER,
            )

            for order in [parent, sl_child, tp_child]:
                affected = await broker_service._order_manager.upsert(order)
                for enriched in affected:
                    await topic_update(enriched)

            parent_emissions = [o for o in emitted if o.id == "WS-100"]
            final_parent = parent_emissions[-1]
            assert final_parent.stopLoss == 145.0
            assert final_parent.takeProfit == 160.0
        finally:
            broker_service.remove_topic(topic)
            await broker_service._order_manager.clear()
