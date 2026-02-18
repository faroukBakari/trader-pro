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
from trading_api.models.exceptions import ProviderException
from trading_api.providers.tws.order_tracker import OrderTracker, TrackedOrder

# ── Helpers ─────────────────────────────────────────────────────────────


def _make_contract(symbol: str = "AAPL", con_id: int = 265598) -> Contract:
    c = Contract()
    c.conId = con_id
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


# ═══════════════════════════════════════════════════════════════════════
# Timeout safety (WS1) and targeted error dispatch (WS3)
# ═══════════════════════════════════════════════════════════════════════


class TestDefaultOrderTimeout:
    """OrderTracker applies DEFAULT_ORDER_TIMEOUT when timeout=None."""

    @pytest.mark.asyncio
    async def test_order_update_uses_default_timeout_when_none(self) -> None:
        """__order_update with timeout=None uses DEFAULT_ORDER_TIMEOUT, not infinite."""
        tracker = _make_tracker()
        contract = _make_contract()
        order = _make_order()

        # Stub __placeOrder to avoid protobuf encoding
        tracker._OrderTracker__placeOrder = MagicMock()  # type: ignore[attr-defined]

        # Use a very short default timeout to make the test fast
        tracker.DEFAULT_ORDER_TIMEOUT = 0.05

        with pytest.raises(asyncio.TimeoutError):
            # placeOrderGroup with no timeout → DEFAULT_ORDER_TIMEOUT (0.05s)
            await tracker.placeOrderGroup(contract, order, children=[])

    @pytest.mark.asyncio
    async def test_place_order_group_forwards_timeout_to_oca_group(self) -> None:
        """placeOrderGroup passes its timeout to placeOcaGroup for children."""
        tracker = _make_tracker()
        contract = _make_contract()
        parent = _make_order()
        child = _make_order(action="SELL", order_type="STP")

        # Stub __placeOrder to avoid protobuf encoding
        tracker._OrderTracker__placeOrder = MagicMock()  # type: ignore[attr-defined]

        # Patch placeOcaGroup to capture the timeout kwarg
        captured_kwargs: dict = {}

        async def mock_place_oca(*args: object, **kwargs: object) -> list:
            captured_kwargs.update(kwargs)
            return []

        tracker.placeOcaGroup = mock_place_oca  # type: ignore[method-assign]

        # Set a short default to not hang the test
        tracker.DEFAULT_ORDER_TIMEOUT = 0.05

        with pytest.raises(asyncio.TimeoutError):
            await tracker.placeOrderGroup(
                contract, parent, children=[child], timeout=5.0
            )

        assert captured_kwargs.get("timeout") == 5.0


class TestHookRegistrationBeforePlacement:
    """Hooks must be registered BEFORE orders are sent to TWS.

    This prevents a race condition where TWS responds (reader thread →
    __notify_hooks) before the hook exists, causing the notification to
    be lost and the future to hang until timeout.
    """

    @pytest.mark.asyncio
    async def test_placeOcaGroup_registers_hooks_before_sending(self) -> None:
        """placeOcaGroup registers hooks in _order_hooks before __placeOrder."""
        tracker = _make_tracker()
        contract = _make_contract()
        orders = [
            _make_order(action="SELL", order_type="STP"),
            _make_order(action="SELL", order_type="LMT"),
        ]

        # Track the sequence of operations
        sequence: list[str] = []

        def instant_tws_response(oid: int, _c: object, _o: object) -> None:
            # At the time __placeOrder fires, hooks should already exist
            hooks_registered = oid in tracker._order_hooks
            sequence.append(f"place:{oid}:hooks={'yes' if hooks_registered else 'no'}")
            # Simulate TWS responding instantly inside __placeOrder by calling
            # upsert_order synchronously (mimics reader thread callback)
            tracker.upsert_order(
                orderId=oid,
                contract=contract,
                order=orders[0],
                orderState=_make_order_state("Submitted"),
            )

        tracker._OrderTracker__placeOrder = MagicMock(  # type: ignore[attr-defined]
            side_effect=instant_tws_response
        )

        result = await tracker.placeOcaGroup(
            contract,
            orders,
            oca_group="brackets_NASDAQ:TEST",
            oca_type=1,
            timeout=2.0,
        )

        assert len(result) == 2
        # Every __placeOrder call should see hooks already registered
        for entry in sequence:
            assert entry.endswith(
                ":hooks=yes"
            ), f"Hook not registered before placement: {entry}"

    @pytest.mark.asyncio
    async def test_placeOrderGroup_registers_parent_hook_before_sending(self) -> None:
        """placeOrderGroup registers parent hook before __placeOrder."""
        tracker = _make_tracker()
        contract = _make_contract()
        parent = _make_order(action="BUY", order_type="MKT")

        sequence: list[str] = []

        def instant_parent_response(oid: int, _c: object, _o: object) -> None:
            hooks_registered = oid in tracker._order_hooks
            sequence.append(f"place:{oid}:hooks={'yes' if hooks_registered else 'no'}")
            tracker.upsert_order(
                orderId=oid,
                contract=contract,
                order=parent,
                orderState=_make_order_state("Submitted"),
            )

        tracker._OrderTracker__placeOrder = MagicMock(  # type: ignore[attr-defined]
            side_effect=instant_parent_response
        )

        result = await tracker.placeOrderGroup(
            contract, parent, children=[], timeout=2.0
        )

        assert result[0].orderId >= 0
        for entry in sequence:
            assert entry.endswith(
                ":hooks=yes"
            ), f"Hook not registered before placement: {entry}"


class TestHasOrder:
    """OrderTracker.has_order() detects tracked orders and pending hooks."""

    def test_has_order_for_tracked_order(self) -> None:
        """has_order returns True for orders in _orders dict."""
        tracker = _make_tracker()

        tracker.upsert_order(
            orderId=42,
            contract=_make_contract(),
            order=_make_order(),
            orderState=_make_order_state(),
        )

        assert tracker.has_order(42) is True
        assert tracker.has_order(99) is False

    def test_has_order_for_pending_hooks(self) -> None:
        """has_order returns True when order has pending hooks."""
        tracker = _make_tracker()
        loop = asyncio.new_event_loop()
        future: asyncio.Future[TrackedOrder] = loop.create_future()

        tracker._order_hooks[77] = {"hook1": (loop, future)}

        assert tracker.has_order(77) is True
        assert tracker.has_order(78) is False

        loop.close()


class TestRaiseErrorForOrder:
    """OrderTracker.raise_error_for_order() targets a single order's hooks."""

    def test_targets_only_specified_order(self) -> None:
        """raise_error_for_order dispatches to matching order, not others."""
        tracker = _make_tracker()
        loop = asyncio.new_event_loop()

        future_42: asyncio.Future[TrackedOrder] = loop.create_future()
        future_99: asyncio.Future[TrackedOrder] = loop.create_future()

        tracker._order_hooks[42] = {"h1": (loop, future_42)}
        tracker._order_hooks[99] = {"h2": (loop, future_99)}

        exc = ProviderException(
            provider="tws",
            capability="broker",
            code="PROVIDER_TWS_2109",
            message="test",
        )
        result = tracker.raise_error_for_order(42, exc)

        # Process scheduled callbacks
        loop.run_until_complete(asyncio.sleep(0))

        assert result is True
        assert future_42.done()
        assert not future_99.done()

        loop.close()

    def test_returns_false_when_no_hooks(self) -> None:
        """raise_error_for_order returns False if no hooks for order_id."""
        tracker = _make_tracker()

        exc = ProviderException(
            provider="tws",
            capability="broker",
            code="PROVIDER_TWS_9999",
            message="test",
        )
        assert tracker.raise_error_for_order(42, exc) is False
