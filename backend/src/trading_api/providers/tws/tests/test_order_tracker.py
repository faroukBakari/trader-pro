"""Tests for OrderTracker — parentId passthrough and fill notification.

The tracker is "dumb TWS state": it always emits the raw TWS parentId as
parentType=ORDER. Bracket reclassification (ORDER → POSITION) is handled
downstream by OrderManager.

Tests verify:
1. Children always get parentId=str(tws_parentId), parentType=ORDER
2. Fill cascade re-notifies children via stream hooks (without reclassification)
3. OCA-based position brackets still resolve correctly
"""

import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from ibapi.contract import Contract
from ibapi.order import Order
from ibapi.order_state import OrderState

from trading_api.models.broker.orders import ParentType
from trading_api.providers.tws.order_tracker import OrderTracker, TrackedOrder

# ── Helpers ─────────────────────────────────────────────────────────────


def _make_contract(symbol: str = "AAPL") -> Contract:
    c = Contract()
    c.symbol = symbol
    c.exchange = "SMART"
    c.primaryExchange = "NASDAQ"
    c.secType = "STK"
    return c


def _make_order(
    action: str = "BUY",
    order_type: str = "MKT",
    qty: int = 100,
    parent_id: int = 0,
    oca_group: str = "",
) -> Order:
    o = Order()
    o.action = action
    o.orderType = order_type
    o.totalQuantity = Decimal(qty)
    o.parentId = parent_id
    o.ocaGroup = oca_group
    o.filledQuantity = Decimal(0)
    return o


def _make_order_state(status: str = "Submitted") -> OrderState:
    s = OrderState()
    s.status = status
    return s


def _make_tracker() -> OrderTracker:
    """Create an OrderTracker with a mocked IBSocket (no real connection)."""
    mock_ibsocket = MagicMock()
    mock_ibsocket.wire_order_tracker.return_value = 1000
    return OrderTracker(mock_ibsocket)


# ═══════════════════════════════════════════════════════════════════════
# Raw parentId passthrough (no reclassification)
# ═══════════════════════════════════════════════════════════════════════


class TestRawParentIdPassthrough:
    """Tracker always emits raw TWS parentId as parentType=ORDER."""

    def test_child_always_emits_order_parent_type(self) -> None:
        """Child with TWS parentId > 0 → parentType=ORDER, parentId=str(id)."""
        tracker = _make_tracker()

        child_order = _make_order(action="SELL", order_type="STP", parent_id=100)
        tracker.upsert_order(
            orderId=101,
            contract=_make_contract(),
            order=child_order,
            orderState=_make_order_state("Submitted"),
        )

        domain = tracker._orders[101].to_domain()
        assert domain.parentType == ParentType.ORDER
        assert domain.parentId == "100"

    def test_child_before_parent_stays_order_bracket(self) -> None:
        """Child arrives before parent → still ORDER bracket."""
        tracker = _make_tracker()

        # Child first
        child_order = _make_order(action="SELL", order_type="STP", parent_id=100)
        tracker.upsert_order(
            orderId=101,
            contract=_make_contract(),
            order=child_order,
            orderState=_make_order_state("Submitted"),
        )

        # Parent arrives later
        parent_order = _make_order(action="BUY", order_type="MKT")
        tracker.upsert_order(
            orderId=100,
            contract=_make_contract(),
            order=parent_order,
            orderState=_make_order_state("Submitted"),
        )

        domain = tracker._orders[101].to_domain()
        assert domain.parentType == ParentType.ORDER
        assert domain.parentId == "100"

    def test_child_after_snapshot_stays_order_bracket(self) -> None:
        """Even after snapshot completes, child still emits ORDER bracket.

        Cold-start reclassification is OrderManager's job.
        """
        tracker = _make_tracker()
        tracker.mark_snapshot_complete()

        child_order = _make_order(action="SELL", order_type="STP", parent_id=100)
        tracker.upsert_order(
            orderId=101,
            contract=_make_contract(),
            order=child_order,
            orderState=_make_order_state("Submitted"),
        )

        domain = tracker._orders[101].to_domain()
        assert domain.parentType == ParentType.ORDER
        assert domain.parentId == "100"

    def test_parent_fills_children_still_order_bracket(self) -> None:
        """Parent fills → children still emitted as ORDER bracket.

        Reclassification to POSITION is OrderManager's responsibility.
        """
        tracker = _make_tracker()

        parent_order = _make_order(action="BUY", order_type="MKT")
        tracker.upsert_order(
            orderId=100,
            contract=_make_contract(),
            order=parent_order,
            orderState=_make_order_state("Submitted"),
        )

        child_order = _make_order(action="SELL", order_type="STP", parent_id=100)
        tracker.upsert_order(
            orderId=101,
            contract=_make_contract(),
            order=child_order,
            orderState=_make_order_state("Submitted"),
        )

        # Parent fills
        tracker.update_status(
            orderId=100,
            status="Filled",
            filled=Decimal("100"),
            remaining=Decimal("0"),
            avgFillPrice=150.0,
            permId=100,
            parentId=0,
            lastFillPrice=150.0,
            clientId=1,
            whyHeld="",
            mktCapPrice=0.0,
        )

        # Child still reports ORDER bracket (raw TWS parentId)
        domain = tracker._orders[101].to_domain()
        assert domain.parentType == ParentType.ORDER
        assert domain.parentId == "100"

    def test_order_without_parent_has_no_parent_type(self) -> None:
        """Order with parentId=0 → no parentId/parentType set."""
        tracker = _make_tracker()

        order = _make_order(action="BUY", order_type="LMT")
        tracker.upsert_order(
            orderId=100,
            contract=_make_contract(),
            order=order,
            orderState=_make_order_state("Submitted"),
        )

        domain = tracker._orders[100].to_domain()
        assert domain.parentId is None
        assert domain.parentType is None


# ═══════════════════════════════════════════════════════════════════════
# Fill cascade notification
# ═══════════════════════════════════════════════════════════════════════


class TestFillCascadeNotification:
    """When a parent fills, its children are re-notified via stream hooks."""

    @pytest.mark.asyncio
    async def test_parent_fill_re_notifies_children(self) -> None:
        """Parent fills → stream hook fires for both parent and children."""
        tracker = _make_tracker()
        notified_ids: list[int] = []

        # Register stream hook
        loop = asyncio.get_running_loop()

        async def on_update(tracked: TrackedOrder) -> None:
            notified_ids.append(tracked.orderId)

        tracker._stream_hooks["test"] = (loop, on_update, AsyncMock())

        # Parent and child
        tracker.upsert_order(
            orderId=100,
            contract=_make_contract(),
            order=_make_order(action="BUY", order_type="MKT"),
            orderState=_make_order_state("Submitted"),
        )
        tracker.upsert_order(
            orderId=101,
            contract=_make_contract(),
            order=_make_order(action="SELL", order_type="STP", parent_id=100),
            orderState=_make_order_state("Submitted"),
        )
        notified_ids.clear()

        # Parent fills
        tracker.update_status(
            orderId=100,
            status="Filled",
            filled=Decimal("100"),
            remaining=Decimal("0"),
            avgFillPrice=150.0,
            permId=100,
            parentId=0,
            lastFillPrice=150.0,
            clientId=1,
            whyHeld="",
            mktCapPrice=0.0,
        )

        # Let scheduled tasks run
        await asyncio.sleep(0.05)

        # Both parent (100) and child (101) should be notified
        assert 100 in notified_ids
        assert 101 in notified_ids


# ═══════════════════════════════════════════════════════════════════════
# OCA-based position brackets
# ═══════════════════════════════════════════════════════════════════════


class TestOcaPositionBrackets:
    """Position brackets placed via OCA (no TWS parentId) still resolve."""

    def test_oca_position_bracket_resolves_to_position(self) -> None:
        """OCA group brackets_AAPL → parentType=POSITION, parentId=AAPL."""
        tracker = _make_tracker()

        # Position bracket: no TWS parentId, but OCA group set
        order = _make_order(
            action="SELL",
            order_type="STP",
            parent_id=0,
            oca_group="brackets_NASDAQ:AAPL",
        )
        tracker.upsert_order(
            orderId=200,
            contract=_make_contract(),
            order=order,
            orderState=_make_order_state("Submitted"),
        )

        domain = tracker._orders[200].to_domain()
        assert domain.parentType == ParentType.POSITION
        assert domain.parentId == "NASDAQ:AAPL"

    def test_oca_numeric_without_tws_parent_id_is_unlinked(self) -> None:
        """OCA brackets_100 (numeric) but no TWS parentId → no parent set.

        Numeric OCA without TWS parentId doesn't happen in practice —
        order brackets always have order.parentId > 0 from TWS.
        The OCA fallback only resolves POSITION brackets (non-numeric).
        """
        tracker = _make_tracker()

        order = _make_order(
            action="SELL",
            order_type="STP",
            parent_id=0,
            oca_group="brackets_100",
        )
        tracker.upsert_order(
            orderId=200,
            contract=_make_contract(),
            order=order,
            orderState=_make_order_state("Submitted"),
        )

        domain = tracker._orders[200].to_domain()
        assert domain.parentType is None
        assert domain.parentId is None

    def test_tws_parent_id_takes_precedence_over_oca(self) -> None:
        """When TWS parentId > 0, it takes precedence over OCA parsing."""
        tracker = _make_tracker()

        order = _make_order(
            action="SELL",
            order_type="STP",
            parent_id=100,
            oca_group="brackets_NASDAQ:AAPL",
        )
        tracker.upsert_order(
            orderId=200,
            contract=_make_contract(),
            order=order,
            orderState=_make_order_state("Submitted"),
        )

        domain = tracker._orders[200].to_domain()
        # TWS parentId wins over OCA
        assert domain.parentType == ParentType.ORDER
        assert domain.parentId == "100"
