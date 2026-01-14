"""Order tracking for TWS broker integration.

Data structures and helper class for tracking TWS order callbacks without
data transformation. Raw TWS objects (Contract, Order, OrderState) are stored
directly. Domain conversion happens at broker_provider level via tws_mappers.
"""

import asyncio
import re
import threading
import time
import uuid
from collections.abc import Callable, Coroutine
from copy import deepcopy
from dataclasses import dataclass, field
from decimal import Decimal
from itertools import count
from typing import Any

from ibapi.contract import Contract
from ibapi.order import Order, OrderComboLeg
from ibapi.order_state import OrderState
from ibapi.softdollartier import SoftDollarTier

from trading_api.models.broker import OrderStatus, ParentType
from trading_api.models.exceptions import ProviderException

_DIRECT_MAPPED_STATUS: dict[str, int] = {
    "PreSubmitted": 3,  # INACTIVE - simulated order held by IB (stop waiting for trigger)
    "Submitted": 6,  # WORKING - active at exchange
    "Cancelled": 1,  # CANCELED - confirmed cancelled
    "Filled": 2,  # FILLED - confirmed filled
    "Inactive": 3,  # INACTIVE - error or held
}

# Statuses requiring history-based resolution (preserve previous confirmed status)
_HISTORY_RESOLVED_STATUS: set[str] = {
    "PendingCancel",  # Cancel requested but not confirmed - could still fill
    "ApiCancelled",  # Cancelled via API before ack - could still fill
    "PendingSubmit",  # Sent, awaiting exchange ack - use last confirmed
    "ApiPending",  # Not yet sent to IB server - use last confirmed
}

ORDER_BRACKET_PATTERN = re.compile(r"^brackets_(\d+)$")


@dataclass
class OrderFill:
    """Captures each orderStatus callback as immutable fill record.

    TWS sends orderStatus callbacks whenever an order's status changes.
    This class preserves the full callback data for fill history tracking.
    """

    orderId: int
    status: str
    filled: Decimal
    remaining: Decimal
    avgFillPrice: float
    permId: int
    parentId: int
    lastFillPrice: float
    clientId: int
    whyHeld: str
    mktCapPrice: float
    timestamp: int  # Unix timestamp in milliseconds at callback time


@dataclass
class TrackedOrder:
    """Wraps raw TWS objects for an order.

    Stores the fresh Contract, Order, OrderState objects from openOrder callback
    without any data transformation. The Order and OrderState objects are mutated
    directly by orderStatus callbacks.

    Thread Safety:
        - Created/updated by reader thread
        - Passed by reference to main thread callbacks (no copies)
        - Main thread consumers should not mutate these objects
    """

    orderId: int
    contract: Contract
    order: Order
    orderState: OrderState
    fills: list[OrderFill] = field(default_factory=list)
    parent_filled: bool = False

    @property
    def domain_status(self) -> OrderStatus:
        """Convert TWS order status to domain OrderStatus.
        Handles cancel transitions (PendingCancel, ApiCancelled) by preserving
        the last confirmed status from order history. This prevents misleading
        users during market halts where orders might still fill after cancel request.

        Args:
            tracked: TrackedOrder with current status and fills history

        Returns:
            Domain OrderStatus enum value

        Resolution order:
            1. Direct mapping for confirmed statuses (Submitted, Filled, Cancelled, etc.)
            2. History lookup for transitional statuses (PendingCancel, ApiCancelled, etc.)
            3. Fallback to PLACING (4) if no history available
        """
        current_status = self.orderState.status

        # 1. Check direct mapping first (confirmed statuses)
        if current_status in _DIRECT_MAPPED_STATUS:
            return OrderStatus(_DIRECT_MAPPED_STATUS[current_status])

        # 2. History-based resolution for transitional/cancel statuses
        if current_status in _HISTORY_RESOLVED_STATUS and self.fills:
            # Walk history backwards to find last confirmed status
            for fill in reversed(self.fills):
                if fill.status in _DIRECT_MAPPED_STATUS:
                    return OrderStatus(_DIRECT_MAPPED_STATUS[fill.status])

        # 3. Fallback to PLACING for new orders with no history
        return OrderStatus.PLACING

    @property
    def is_active(self) -> bool:
        """Check if order is currently active (working/submitted)."""
        return (
            self.domain_status
            not in {
                OrderStatus.FILLED,  # Completed
                OrderStatus.CANCELED,  # Cancelled
            }
            and self.order.whatIf is False
            and self.order.transmit is True
        )

    @property
    def oca_group(self) -> str | None:
        """Get OCA group string if set, else None."""
        return next(iter(self.order.ocaGroup.split("@")), self.order.ocaGroup)

    @property
    def brackets_info(self) -> tuple[str | None, ParentType | None]:
        """Parse OCA group to extract parent ID and determine parent type.

        The codebase uses deterministic OCA naming:
        - Order brackets: "brackets_{order_id}" (numeric) → parentType=ORDER
        - Position brackets: "brackets_{position_id}" (symbol string) → parentType=POSITION

        Args:
            oca_group: OCA group string (e.g., "brackets_100" or "brackets_AAPL:NASDAQ:STK")

        Returns:
            (parent_id, parent_type):
            - ("100", ParentType.ORDER) for order brackets (numeric)
            - ("AAPL:NASDAQ:STK", ParentType.POSITION) for position brackets (non-numeric)
            - (None, None) if not a bracket OCA group
        """
        if not self.oca_group:
            return None, None

        # Check for order bracket (numeric parent_id)
        match = ORDER_BRACKET_PATTERN.match(self.oca_group)
        if match:
            return match.group(1), ParentType.ORDER

        # Check for position bracket (non-numeric, starts with "brackets_")
        if self.oca_group.startswith("brackets_"):
            position_id = self.oca_group[9:]  # Strip "brackets_" prefix
            return position_id, ParentType.POSITION

        return None, None

    def clone_order(self) -> Order:
        """Deep copy Order to avoid shared references."""
        order_copy = Order()
        order_copy.__dict__.update(self.order.__dict__)

        # Nested objects
        order_copy.softDollarTier = SoftDollarTier(
            self.order.softDollarTier.name,
            self.order.softDollarTier.val,
            self.order.softDollarTier.displayName,
        )

        # Lists (shallow copy sufficient for TagValue)
        order_copy.algoParams = self.order.algoParams[:]
        order_copy.smartComboRoutingParams = self.order.smartComboRoutingParams[:]
        order_copy.orderMiscOptions = self.order.orderMiscOptions[:]

        # Copy each OrderComboLeg
        order_copy.orderComboLegs = []
        for leg in self.order.orderComboLegs:
            leg_copy = OrderComboLeg()
            leg_copy.price = leg.price
            order_copy.orderComboLegs.append(leg_copy)

        # Complex hierarchy - deepcopy
        order_copy.conditions = deepcopy(self.order.conditions)

        return order_copy


class OrderTracker:
    """Manages order state for IBSocket. Thread-safe via asyncio dispatch.

    Encapsulates all order tracking state that was previously scattered across
    IBSocket attributes (_order_data, _order_hooks, _open_orders_future).

    Thread Ownership:
        - Envelope (hooks registration, reset): main thread
        - Content (orders dict, fills): reader thread writes, main thread reads
        - Dispatch (callbacks): reader thread schedules, main thread executes

    Usage:
        - Snapshot: reqOpenOrdersSnapshot() → register_snapshot_hook() → resolve_snapshots()
        - Subscription: subscribeOpenOrders() → register_order_hook() → dispatch_update()
    """

    def __init__(self) -> None:
        self._snapshot_requested = threading.Event()
        self._snapshot_complete = threading.Event()
        self._order_id_count: count[int] = count()
        self._orders: dict[int, TrackedOrder] = {}
        self._snapshot_hooks: dict[
            str, tuple[asyncio.AbstractEventLoop, asyncio.Future[list[TrackedOrder]]]
        ] = {}
        self._stream_hooks: dict[
            str,
            tuple[
                asyncio.AbstractEventLoop,
                Callable[[TrackedOrder], Coroutine[Any, Any, None]],
                Callable[[ProviderException], Coroutine[Any, Any, None]],
            ],
        ] = {}

        # Per-order hooks for waiting on specific order updates
        self._order_hooks: dict[
            int,
            dict[str, tuple[asyncio.AbstractEventLoop, asyncio.Future[TrackedOrder]]],
        ] = {}

    # --- Order management (reader thread) ---

    def signed_oca_groups(self) -> set[str]:
        """Get set of all OCA groups in tracked orders."""
        return {
            tracked.order.ocaGroup
            for tracked in self._orders.values()
            if tracked.order.ocaGroup and tracked.is_active
        }

    def find_by_oca_group(
        self,
        oca_group: str,
        order_type: str,
        action: str,
    ) -> TrackedOrder | None:
        """Find tracked order by OCA group, type, and side.

        Used for bracket reconciliation: when updating position brackets,
        find existing orders by their OCA membership and order type.

        Args:
            oca_group: OCA group string (e.g., "brackets_AAPL:NASDAQ:STK")
            order_type: TWS order type ("STP", "LMT", "TRAIL")
            action: Order side ("BUY" or "SELL")

        Returns:
            Matching TrackedOrder or None if not found

        Note:
            Skips filled/cancelled orders (status not "Submitted"/"PreSubmitted")
        """
        oca_group_ori = next(iter(oca_group.split("@")), oca_group)
        orders = [
            tracked
            for tracked in self._orders.values()
            if (
                tracked.oca_group == oca_group_ori
                and tracked.order.orderType == order_type
                and tracked.order.action == action
                and tracked.is_active
            )
        ]
        assert (
            len(orders) <= 1
        ), f"Multiple active {order_type} {action} orders found for OCA group {oca_group}"
        return next(iter(orders), None)

    def ensure_snapshot_requested(self, request_cb: Callable[[], None]) -> None:
        if not self._snapshot_requested.is_set():
            request_cb()
            self._snapshot_requested.set()

    def set_next_order_id(self, orderId: int) -> None:
        self._order_id_count = count(orderId)

    def notify_hooks(self, orderId: int) -> None:
        """Notify all registered hooks with current orders.

        Called from reader thread after reconnect snapshot.
        """
        tracked: TrackedOrder = self._orders[orderId]

        notify_list: list[TrackedOrder] = [tracked]

        if tracked.domain_status == OrderStatus.FILLED:
            for child in self._orders.values():
                if child.order.parentId == orderId:
                    child.parent_filled = True
                    notify_list.append(child)

        if tracked.order.parentId and not tracked.parent_filled:
            parent_tracked = self._orders.get(tracked.order.parentId)
            if not parent_tracked or tracked.domain_status == OrderStatus.FILLED:
                tracked.parent_filled = True

        def resolve_hook(future: asyncio.Future, tracked: TrackedOrder) -> None:
            if not future.done():
                future.set_result(tracked)

        for tracked in notify_list:
            for loop, future in self._order_hooks.get(tracked.orderId, {}).values():
                loop.call_soon_threadsafe(resolve_hook, future, tracked)
            for stream_loop, stream_callback, _ in self._stream_hooks.values():
                stream_loop.call_soon_threadsafe(
                    stream_loop.create_task,
                    stream_callback(tracked),
                )

        # parent_tracked = tracked.order.parentId and self._orders.get(
        #     tracked.order.parentId
        # )
        # if parent_tracked:
        #     for loop, future in self._order_hooks.get(
        #         tracked.order.parentId, {}
        #     ).values():
        #         loop.call_soon_threadsafe(resolve_hook, future, parent_tracked)
        #     for stream_loop, stream_callback, _ in self._stream_hooks.values():
        #         stream_loop.call_soon_threadsafe(
        #             stream_loop.create_task,
        #             stream_callback(parent_tracked),
        #         )

    def upsert_order(
        self,
        orderId: int,
        contract: Contract,
        order: Order,
        orderState: OrderState,
    ) -> None:
        """Create or replace TrackedOrder from openOrder callback.

        Called from reader thread. Stores fresh TWS objects directly.

        Args:
            orderId: TWS order ID
            contract: Fresh Contract object from decoder
            order: Fresh Order object from decoder
            orderState: Fresh OrderState object from decoder

        Returns:
            The created/updated TrackedOrder
        """
        if orderId in self._orders:
            tracked = self._orders[orderId]
            tracked.order = order
            tracked.orderState = orderState
        else:
            self._orders[orderId] = TrackedOrder(
                orderId=orderId,
                contract=contract,
                order=order,
                orderState=orderState,
            )

        self.notify_hooks(orderId)

    def update_status(
        self,
        orderId: int,
        status: str,
        filled: Decimal,
        remaining: Decimal,
        avgFillPrice: float,
        permId: int,
        parentId: int,
        lastFillPrice: float,
        clientId: int,
        whyHeld: str,
        mktCapPrice: float,
    ) -> None:
        """Update TrackedOrder from orderStatus callback.

        Mutates the stored Order and OrderState objects directly.
        Appends a new OrderFill record for fill history.

        Called from reader thread.

        Args:
            orderId: TWS order ID
            status: Order status (Submitted, Filled, Cancelled, etc.)
            filled: Quantity that has been filled
            remaining: Quantity still remaining
            avgFillPrice: Average fill price
            permId: Permanent order ID
            parentId: Parent order ID (for bracket orders)
            lastFillPrice: Price of last fill
            clientId: Client ID that placed the order
            whyHeld: Reason order is held
            mktCapPrice: Market cap price (for auction orders)

        Returns:
            The updated TrackedOrder, or None if order not found
        """
        tracked = self._orders.get(orderId)
        assert tracked is not None, f"Order ID {orderId} not found for status update"

        # Mutate TWS objects directly
        tracked.orderState.status = status
        tracked.order.filledQuantity = filled
        tracked.order.permId = permId
        tracked.order.parentId = parentId
        tracked.order.clientId = clientId

        # Append fill record
        tracked.fills.append(
            OrderFill(
                orderId=orderId,
                status=status,
                filled=filled,
                remaining=remaining,
                avgFillPrice=avgFillPrice,
                permId=permId,
                parentId=parentId,
                lastFillPrice=lastFillPrice,
                clientId=clientId,
                whyHeld=whyHeld,
                mktCapPrice=mktCapPrice,
                timestamp=int(time.time() * 1000),
            )
        )

        self.notify_hooks(orderId)

    def raise_error(self, exception: ProviderException) -> None:
        """Dispatch error to all stream hooks.

        Called from reader thread.
        """

        for snapshot_loop, snapshot_future in self._snapshot_hooks.values():

            def resolve_snapshot_error(
                future: asyncio.Future, exception: ProviderException
            ) -> None:
                if not future.done():
                    future.set_exception(exception)

            snapshot_loop.call_soon_threadsafe(
                resolve_snapshot_error, snapshot_future, exception
            )

        for stream_loop, _, on_error in self._stream_hooks.values():
            stream_loop.call_soon_threadsafe(
                stream_loop.create_task,
                on_error(exception),
            )

        for order_hooks in self._order_hooks.values():
            for loop, future in order_hooks.values():

                def resolve_order_error(
                    future: asyncio.Future, exception: ProviderException
                ) -> None:
                    if not future.done():
                        future.set_exception(exception)

                loop.call_soon_threadsafe(resolve_order_error, future, exception)

    def mark_snapshot_complete(self) -> None:
        """Mark snapshot as complete. Called from openOrderEnd."""
        self._snapshot_complete.set()
        for loop, future in self._snapshot_hooks.values():

            def resolve_hook(
                future: asyncio.Future, orders: list[TrackedOrder]
            ) -> None:
                if not future.done():
                    future.set_result(orders)

            loop.call_soon_threadsafe(resolve_hook, future, list(self._orders.values()))

    # --- Order registrations (main thread) ---

    def reset(self) -> None:
        """Full reset - like fresh creation.

        Clears all orders, snapshot state, and hooks.
        Called from main thread before new snapshot request.
        """
        self._orders.clear()
        self._snapshot_complete.clear()
        self._snapshot_requested.clear()
        self._snapshot_hooks.clear()
        self._stream_hooks.clear()
        self._order_hooks.clear()
        self._order_id_count = count()

    async def all_orders(self, timeout: float | None = None) -> list[TrackedOrder]:
        """Register a future to be resolved when snapshot completes.

        Called from main thread. If snapshot is already complete,
        resolves immediately.

        Args:
            loop: Event loop for the future
            future: Future to resolve with order list
        """

        loop = asyncio.get_running_loop()
        future: asyncio.Future[list[TrackedOrder]] = loop.create_future()

        if self._snapshot_complete.is_set():
            future.set_result(list(self._orders.values()))
            return await asyncio.wait_for(future, timeout)

        key = str(uuid.uuid4())
        self._snapshot_hooks[key] = (loop, future)

        try:
            return await asyncio.wait_for(future, timeout)
        finally:
            self._snapshot_hooks.pop(key, None)

    @property
    def next_order_id(self) -> int:
        return next(self._order_id_count)

    def ensure_existing_order(self, orderId: int) -> TrackedOrder:
        """Raise if orderId not tracked."""
        if orderId not in self._orders:
            raise ProviderException(
                code="SERVICE_TWS_ORDER_NOT_FOUND",
                message=f"Order ID {orderId} not found in TWS order tracker.",
                provider="tws",
                capability="shared",
            )
        return self._orders[orderId]

    async def order_update(
        self, orderId: int, timeout: float | None = None
    ) -> TrackedOrder:
        """Register a future to be resolved on next update for orderId.

        Called from main thread.

        Args:
            orderId: TWS order ID to wait for
            timeout: Optional timeout in seconds for the update
        """

        key = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        future: asyncio.Future[TrackedOrder] = loop.create_future()

        self._order_hooks.setdefault(orderId, {})[key] = (loop, future)

        try:
            return await asyncio.wait_for(future, timeout)
        finally:
            self._order_hooks.get(orderId, {}).pop(key, None)

    def create_stream_hook(
        self,
        loop: asyncio.AbstractEventLoop,
        callback: Callable[[TrackedOrder], Coroutine[Any, Any, None]],
        on_error: Callable[[ProviderException], Coroutine[Any, Any, None]],
    ) -> str:
        """Register callback for order updates.

        Called from main thread.

        Args:
            loop: Event loop for callbacks
            callback: Called for each order update
            on_error: Optional error callback
        """
        key = str(uuid.uuid4())
        self._stream_hooks[key] = (loop, callback, on_error)
        return key

    def remove_stream_hook(self, key: str) -> None:
        """Unregister order update callback."""
        self._stream_hooks.pop(key, None)
