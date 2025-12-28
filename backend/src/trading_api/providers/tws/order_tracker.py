"""Order tracking for TWS broker integration.

Data structures and helper class for tracking TWS order callbacks without
data transformation. Raw TWS objects (Contract, Order, OrderState) are stored
directly. Domain conversion happens at broker_provider level via tws_mappers.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ibapi.contract import Contract
    from ibapi.order import Order
    from ibapi.order_state import OrderState

    from trading_api.models.exceptions import ProviderException


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
    contract: "Contract"
    order: "Order"
    orderState: "OrderState"
    fills: list[OrderFill] = field(default_factory=list)


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
        self._orders: dict[int, TrackedOrder] = {}
        self._snapshot_complete: bool = False
        self._snapshot_hooks: list[
            tuple[asyncio.AbstractEventLoop, asyncio.Future[list[TrackedOrder]]]
        ] = []
        self._order_hooks: dict[
            int, tuple[asyncio.AbstractEventLoop, asyncio.Future[list[TrackedOrder]]]
        ] = {}
        self._stream_hooks: (
            tuple[
                asyncio.AbstractEventLoop,
                Callable[[TrackedOrder], Awaitable[None]],
                Callable[["ProviderException"], Awaitable[None]] | None,
            ]
            | None
        ) = None

    def reset(self) -> None:
        """Full reset - like fresh creation.

        Clears all orders, snapshot state, and hooks.
        Called from main thread before new snapshot request.
        """
        self._orders.clear()
        self._snapshot_complete = False
        self._snapshot_hooks.clear()
        self._stream_hooks = None

    def upsert_order(
        self,
        orderId: int,
        contract: "Contract",
        order: "Order",
        orderState: "OrderState",
    ) -> TrackedOrder:
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
        tracked = TrackedOrder(
            orderId=orderId,
            contract=contract,
            order=order,
            orderState=orderState,
            fills=[],
        )
        self._orders[orderId] = tracked
        return tracked

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
    ) -> TrackedOrder | None:
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
        if tracked is None:
            # Orphan status - openOrder not yet received
            return None

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
        return tracked

    def mark_snapshot_complete(self) -> None:
        """Mark snapshot as complete. Called from openOrderEnd."""
        self._snapshot_complete = True

    def get_orders(self) -> list[TrackedOrder]:
        """Get all tracked orders as a list."""
        return list(self._orders.values())

    def get_order(self, orderId: int) -> TrackedOrder | None:
        """Get a specific tracked order by ID."""
        return self._orders.get(orderId)

    # --- Hook management (main thread) ---

    def register_snapshot_hook(
        self,
        loop: asyncio.AbstractEventLoop,
        future: asyncio.Future[list[TrackedOrder]],
    ) -> None:
        """Register a future to be resolved when snapshot completes.

        Called from main thread. If snapshot is already complete,
        resolves immediately.

        Args:
            loop: Event loop for the future
            future: Future to resolve with order list
        """
        if self._snapshot_complete:
            loop.call_soon_threadsafe(future.set_result, self.get_orders())
        else:
            self._snapshot_hooks.append((loop, future))

    def register_order_hook(
        self,
        loop: asyncio.AbstractEventLoop,
        callback: Callable[[TrackedOrder], Awaitable[None]],
        on_error: Callable[["ProviderException"], Awaitable[None]] | None = None,
    ) -> None:
        """Register callback for order updates.

        Called from main thread.

        Args:
            loop: Event loop for callbacks
            callback: Called for each order update
            on_error: Optional error callback
        """
        self._stream_hooks = (loop, callback, on_error)

    def unregister_order_hook(self) -> None:
        """Unregister order update callback."""
        self._stream_hooks = None

    # --- Dispatch (reader thread) ---

    def resolve_snapshots(self) -> None:
        """Resolve all pending snapshot futures.

        Called from reader thread after openOrderEnd.
        Uses call_soon_threadsafe to dispatch to main thread.
        """
        if not self._snapshot_complete:
            return
        orders = self.get_orders()
        for loop, future in self._snapshot_hooks:
            if not future.done():
                loop.call_soon_threadsafe(future.set_result, orders)
        self._snapshot_hooks.clear()

    def dispatch_update(self, tracked: TrackedOrder) -> None:
        """Dispatch order update to streaming callback.

        Called from reader thread. Uses call_soon_threadsafe to
        schedule callback execution on main thread.

        Args:
            tracked: The TrackedOrder that was updated
        """
        if self._stream_hooks is None:
            return
        loop, callback, _ = self._stream_hooks

        async def _notify() -> None:
            await callback(tracked)

        loop.call_soon_threadsafe(loop.create_task, _notify())
