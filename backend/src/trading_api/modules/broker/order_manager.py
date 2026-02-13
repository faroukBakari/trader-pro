"""
Order Manager — service-layer bracket clustering.

Maintains an in-memory set of all PlacedOrders and enriches parent orders
with bracket context (takeProfit, stopLoss, trailingStopPips) derived from
their child orders. Both REST and WS paths read from / write to this single
enriched state, making bracket clustering a set operation — always.

Design principle: OrderTracker stays "dumb TWS state" (raw tracking, OCA
parsing, raw parentId via to_domain()). OrderManager adds ALL business
logic: position bracket reclassification, BracketContext derivation, and
cluster emission.

Position bracket reclassification:
  When a parent order FILLS, its bracket children become position brackets
  (protecting the resulting position, not the now-closed order). The tracker
  always emits parentType=ORDER with the raw TWS parentId. The OrderManager
  detects filled/missing parents and reclassifies children:
    parentId = symbol, parentType = POSITION.
"""

from __future__ import annotations

import logging

from trading_api.models.broker.orders import (
    OrderStatus,
    OrderType,
    ParentType,
    PlacedOrder,
    StopType,
)

logger = logging.getLogger(__name__)


class OrderManager:
    """In-memory order state with bracket cluster enrichment.

    Upsert individual orders (WS path) or bulk-sync (REST path).
    Both paths return PlacedOrders with bracket fields enriched from
    child orders in the same cluster.
    """

    def __init__(self) -> None:
        self._orders: dict[str, PlacedOrder] = {}

    # ── Public API ──────────────────────────────────────────────────────

    def upsert(self, order: PlacedOrder) -> list[PlacedOrder]:
        """Upsert order, enrich its bracket cluster, return affected orders.

        Returns the upserted order plus any orders whose enriched
        representation changed. Empty list means no observable change
        (prevents double emissions on the WS path).
        """
        prev = self._orders.get(order.id)

        # Reclassify ORDER bracket → POSITION if parent is FILLED in state.
        # On the WS path we only reclassify when the parent is present and
        # confirmed FILLED (missing parent = hasn't arrived yet, not cold start).
        order = self._maybe_reclassify(order)

        self._orders[order.id] = order

        affected = self._enrich_bracket_cluster(order)

        # If reclassified from ORDER→POSITION, the old parent may have stale
        # bracket enrichment from when this child was still an ORDER bracket.
        # Re-enrich the old parent to clear stale fields.
        if (
            prev is not None
            and prev.parentType == ParentType.ORDER
            and order.parentType == ParentType.POSITION
            and prev.parentId is not None
            and prev.parentId in self._orders
        ):
            old_parent = self._orders[prev.parentId]
            new_parent = self._enrich_parent(prev.parentId)
            if new_parent != old_parent:
                affected.append(new_parent)

        # If nothing changed (same order re-upserted, no cluster change),
        # return empty to avoid double emissions.
        if not affected and prev == order:
            return []

        # Always include the upserted order + any additionally changed orders.
        result_ids: set[str] = {order.id}
        result: list[PlacedOrder] = [self._orders[order.id]]
        for a in affected:
            if a.id not in result_ids:
                result.append(a)
                result_ids.add(a.id)
        return result

    def sync(self, orders: list[PlacedOrder]) -> None:
        """Bulk replace state (for initial load / REST refresh).

        Reclassifies position brackets (parent FILLED or missing) then
        enriches all remaining order brackets.
        """
        self._orders = {o.id: o for o in orders}
        self._reclassify_position_brackets()
        self._enrich_all()

    def get_all(self) -> list[PlacedOrder]:
        """Return all orders (copies — mutations don't affect internal state)."""
        return [o.model_copy() for o in self._orders.values()]

    def clear(self) -> None:
        """Reset state."""
        self._orders.clear()

    # ── Position Bracket Reclassification (private) ─────────────────────

    def _reclassify_position_brackets(self) -> None:
        """Reclassify ORDER children whose parent is FILLED or missing.

        Called in sync() where all orders are available simultaneously.
        Children of FILLED parents or children whose parent doesn't exist
        in state (cold start — TWS only resends active orders) become
        POSITION brackets: parentId=symbol, parentType=POSITION.
        """
        updates: dict[str, PlacedOrder] = {}
        for order in self._orders.values():
            if order.parentType != ParentType.ORDER or order.parentId is None:
                continue
            parent = self._orders.get(order.parentId)
            if parent is None or parent.status == OrderStatus.FILLED:
                updates[order.id] = order.model_copy(
                    update={
                        "parentId": order.symbol,
                        "parentType": ParentType.POSITION,
                    }
                )
        self._orders.update(updates)

    def _maybe_reclassify(self, order: PlacedOrder) -> PlacedOrder:
        """Reclassify a single ORDER bracket if parent is FILLED in state.

        Used on the WS path (upsert). Only checks parents already in state —
        a missing parent means it hasn't arrived yet, NOT cold start.
        """
        if order.parentType != ParentType.ORDER or order.parentId is None:
            return order
        parent = self._orders.get(order.parentId)
        if parent is not None and parent.status == OrderStatus.FILLED:
            return order.model_copy(
                update={
                    "parentId": order.symbol,
                    "parentType": ParentType.POSITION,
                }
            )
        return order

    # ── Bracket Enrichment (private) ────────────────────────────────────

    def _enrich_all(self) -> None:
        """Re-derive bracket fields for every parent in state."""
        parent_ids = self._find_all_parent_ids()
        for parent_id in parent_ids:
            self._enrich_parent(parent_id)

    def _enrich_bracket_cluster(self, order: PlacedOrder) -> list[PlacedOrder]:
        """Enrich the bracket cluster that `order` belongs to.

        Returns list of orders whose enriched state changed (excluding
        the upserted order itself — the caller handles that).
        """
        changed: list[PlacedOrder] = []

        # Determine which parent to enrich
        if order.parentId is not None and order.parentType == ParentType.ORDER:
            # This is an ORDER bracket child — enrich its parent (if in state)
            parent_id = order.parentId
            if parent_id in self._orders:
                old_parent = self._orders[parent_id]
                new_parent = self._enrich_parent(parent_id)
                if new_parent != old_parent:
                    changed.append(new_parent)
        elif order.parentId is None or order.parentType is None:
            # This order might be a parent — enrich it from its children
            old = self._orders[order.id]
            new = self._enrich_parent(order.id)
            if new != old:
                changed.append(new)

        return changed

    def _enrich_parent(self, parent_id: str) -> PlacedOrder:
        """Derive bracket fields on parent from its ORDER bracket children.

        Returns the (potentially updated) parent order.
        """
        parent = self._orders.get(parent_id)
        if parent is None:
            raise KeyError(f"Parent {parent_id} not in state")

        children = self._find_children(parent_id)

        take_profit: float | None = None
        stop_loss: float | None = None
        trailing_stop_pips: float | None = None
        stop_type: StopType | None = None

        for child in children:
            child_type = OrderType(child.type)
            if child_type == OrderType.LIMIT:
                take_profit = child.limitPrice
            elif child_type == OrderType.STOP:
                stop_loss = child.stopPrice
            elif child_type == OrderType.TRAIL:
                trailing_stop_pips = child.stopPrice
                stop_type = StopType.TRAILING_STOP

        # Only update if bracket fields actually differ
        if (
            parent.takeProfit == take_profit
            and parent.stopLoss == stop_loss
            and parent.trailingStopPips == trailing_stop_pips
            and parent.stopType == stop_type
        ):
            return parent

        enriched = parent.model_copy(
            update={
                "takeProfit": take_profit,
                "stopLoss": stop_loss,
                "trailingStopPips": trailing_stop_pips,
                "stopType": stop_type,
            }
        )
        self._orders[parent_id] = enriched
        return enriched

    def _find_children(self, parent_id: str) -> list[PlacedOrder]:
        """Find all ORDER bracket children whose parentId matches."""
        return [
            o
            for o in self._orders.values()
            if o.parentId == parent_id and o.parentType == ParentType.ORDER
        ]

    def _find_all_parent_ids(self) -> set[str]:
        """Collect all unique parent IDs referenced by ORDER bracket children."""
        ids: set[str] = set()
        for o in self._orders.values():
            if (
                o.parentId is not None
                and o.parentType == ParentType.ORDER
                and o.parentId in self._orders
            ):
                ids.add(o.parentId)
        return ids
