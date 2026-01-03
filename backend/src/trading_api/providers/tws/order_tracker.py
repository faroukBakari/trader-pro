"""Order tracking for TWS broker integration.

Data structures and helper class for tracking TWS order callbacks without
data transformation. Raw TWS objects (Contract, Order, OrderState) are stored
directly. Domain conversion happens at broker_provider level via tws_mappers.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from decimal import Decimal
from itertools import count
from typing import Any

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
    contract: Contract
    order: Order
    orderState: OrderState
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
        self._snapshot_requested: bool = False
        self._snapshot_complete: bool = False
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

    def ensure_snapshot_requested(self, request_cb: Callable[[], None]) -> None:
        if not self._snapshot_requested:
            self._snapshot_requested = True
            request_cb()

    def set_next_order_id(self, orderId: int) -> None:
        self._order_id_count = count(orderId)

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
        tracked = TrackedOrder(
            orderId=orderId,
            contract=contract,
            order=order,
            orderState=orderState,
            fills=[],
        )
        self._orders[orderId] = tracked

        for loop, future in self._order_hooks.get(orderId, {}).values():

            def resolve_hook(future: asyncio.Future, tracked: TrackedOrder) -> None:
                if not future.done():
                    future.set_result(tracked)

            loop.call_soon_threadsafe(resolve_hook, future, tracked)

        for stream_loop, stream_callback, _ in self._stream_hooks.values():
            stream_loop.call_soon_threadsafe(
                stream_loop.create_task,
                stream_callback(tracked),
            )

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

        for loop, future in self._order_hooks.get(orderId, {}).values():

            def resolve_hook(future: asyncio.Future, tracked: TrackedOrder) -> None:
                if not future.done():
                    future.set_result(tracked)

            loop.call_soon_threadsafe(resolve_hook, future, tracked)

        for stream_loop, stream_callback, _ in self._stream_hooks.values():
            stream_loop.call_soon_threadsafe(
                stream_loop.create_task,
                stream_callback(tracked),
            )

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
        self._snapshot_complete = True
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
        self._snapshot_complete = False
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

        if self._snapshot_complete:
            loop.call_soon_threadsafe(future.set_result, list(self._orders.values()))
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
