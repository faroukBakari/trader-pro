"""Order tracking for TWS broker integration.

Data structures and helper class for tracking TWS order callbacks without
data transformation. Raw TWS objects (Contract, Order, OrderState) are stored
directly. Domain conversion happens at broker_provider level via tws_mappers.
"""

import asyncio
import logging
import os
import threading
import time
import uuid
from collections.abc import Callable, Coroutine
from copy import deepcopy
from dataclasses import dataclass, field
from decimal import Decimal
from itertools import count
from typing import Any

from ibapi.client_utils import (
    createCancelOrderRequestProto,
    createPlaceOrderRequestProto,
)
from ibapi.common import PROTOBUF_MSG_ID
from ibapi.const import UNSET_DECIMAL, UNSET_DOUBLE
from ibapi.contract import Contract
from ibapi.message import OUT
from ibapi.order import Order, OrderComboLeg
from ibapi.order_cancel import OrderCancel
from ibapi.order_state import OrderState
from ibapi.softdollartier import SoftDollarTier

from trading_api.models.broker import (
    OrderStatus,
    OrderType,
    ParentType,
    PlacedOrder,
    Side,
)
from trading_api.models.exceptions import ProviderException
from trading_api.providers.tws.tws_mappers import (
    ORDER_BRACKET_PATTERN,
    TWS_ACTION_TO_SIDE,
    TWS_TO_ORDER_TYPE,
    isUnset,
    ticker_name,
)
from trading_api.providers.tws.wiring_interfaces import (
    IbSocketWiringInterface,
    OrderTrackerCBWiringInterface,
)

logger = logging.getLogger(__name__)

DEBUG_TWS_REQUEST = os.environ.get("DEBUG_TWS_REQUEST") == "true"

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

    @property
    def domain_status(self) -> OrderStatus:
        """Convert TWS order status to domain OrderStatus.
        Handles cancel transitions (PendingCancel, ApiCancelled) by preserving
        the last confirmed status from order history. This prevents misleading
        users during market halts where orders might still fill after cancel request.

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

    def to_domain(
        self,
        *,
        contract: Contract | None = None,
    ) -> PlacedOrder:
        """Convert TrackedOrder to domain PlacedOrder.

        Extracts data directly from raw TWS objects (Contract, Order, OrderState)
        stored in TrackedOrder without relying on flattened dict fields.

        Bracket enrichment (takeProfit, stopLoss, trailingStopPips) is handled
        downstream by OrderManager — this method only sets parent identification.

        Args:
            contract: Override contract (e.g. with full details from reqContractDetails).

        Returns:
            Domain PlacedOrder model
        """

        contract = contract or self.contract
        order = self.order

        # Build symbol from contract
        symbol = ticker_name(contract)

        # Order type
        order_type_str = order.orderType
        order_type = OrderType(TWS_TO_ORDER_TYPE.get(order_type_str, 2))

        # Side from action
        side = Side(TWS_ACTION_TO_SIDE.get(order.action, 1))

        # Quantity
        qty = float(order.totalQuantity)

        # Status with history-aware resolution
        status = self.domain_status

        # Prices — order-type-aware extraction
        # TWS may set lmtPrice/auxPrice internally even for order types that
        # don't use them (e.g. market orders). Only expose prices relevant
        # to the order type to avoid misleading the UI.
        limit_price: float | None = None
        stop_price: float | None = None
        if order_type == OrderType.LIMIT:
            if order.lmtPrice and order.lmtPrice > 0:
                limit_price = order.lmtPrice
        elif order_type in (OrderType.STOP, OrderType.TRAIL):
            if order.auxPrice and order.auxPrice > 0:
                stop_price = order.auxPrice
        # MARKET orders: no prices exposed

        # Filled quantity from order object (mutated by orderStatus callback)
        filled_qty = (
            0.0 if isUnset(order.filledQuantity) else float(order.filledQuantity)
        )

        # Average fill price from fills history (last fill's avgFillPrice)
        avg_price: float | None = None
        if self.fills and filled_qty > 0:
            avg_price = self.fills[-1].avgFillPrice

        # Parent order linking (for bracket child orders)
        # TWS sets order.parentId > 0 for child orders (TP/SL)
        parent_id: str | None = None
        parent_type: ParentType | None = None
        if order.parentId and order.parentId > 0:
            parent_id = str(order.parentId)
            parent_type = ParentType.ORDER
        else:
            # Try to parse parentId from OCA group for position brackets
            parsed_parent_id, parsed_parent_type = self.brackets_info
            if parsed_parent_id and parsed_parent_type == ParentType.POSITION:
                parent_id = parsed_parent_id
                parent_type = ParentType.POSITION

        return PlacedOrder(
            id=str(self.orderId),
            symbol=symbol,
            type=order_type,
            side=side,
            qty=qty if qty > 0 else 1,  # Ensure positive qty
            status=status,
            limitPrice=limit_price,
            stopPrice=stop_price,
            takeProfit=None,
            stopLoss=None,
            trailingStopPips=None,
            stopType=None,
            filledQty=filled_qty if filled_qty > 0 else None,
            avgPrice=avg_price,
            parentId=parent_id,
            parentType=parent_type,
        )


# TODO: finer refactoring and cleanup
# TODO: group smart/overnight orders
# TODO: switch orders when switching smart/overnight exchange
class OrderTracker(OrderTrackerCBWiringInterface):
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

    def __init__(self, ibsocket: IbSocketWiringInterface) -> None:
        nxt_valid_order_id = ibsocket.wire_order_tracker(self)
        self.__order_id_count = (
            count(nxt_valid_order_id) if nxt_valid_order_id else None
        )
        self.ibsocket = ibsocket
        self._snapshot_requested = threading.Event()
        self._snapshot_complete = threading.Event()
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

    # --- Order helper methods (internal) ---

    @property
    def next_order_id(self) -> int:
        assert self.__order_id_count is not None, "Order ID counter not initialized."
        return next(self.__order_id_count)

    def __assert_order_exists(self, orderId: int) -> TrackedOrder:
        """Raise if orderId not tracked."""
        if orderId not in self._orders:
            raise ProviderException(
                code="SERVICE_TWS_ORDER_NOT_FOUND",
                message=f"Order ID {orderId} not found in TWS order tracker.",
                provider="tws",
                capability="shared",
            )
        return self._orders[orderId]

    def __find_tracked_order(
        self,
        order: Order,
    ) -> TrackedOrder | None:
        """Find tracked order by orderId or OCA group+type+action.

        Resolution priority:
        1. If order.orderId > 0 and exists in tracker → return directly
        2. If order.ocaGroup set → find by OCA group + orderType + action

        Used for bracket reconciliation: when updating position brackets,
        find existing orders by their OCA membership and order type.

        Args:
            order: Order object containing orderId, ocaGroup, orderType, and action

        Returns:
            Matching TrackedOrder or None if not found

        Note:
            Skips filled/cancelled orders (status not "Submitted"/"PreSubmitted")
        """

        if order.orderId > 0 and order.orderId in self._orders:
            return self._orders.get(order.orderId)

        oca_group_ori = next(iter(order.ocaGroup.split("@")), order.ocaGroup)

        if not oca_group_ori:
            return None

        orders = [
            tracked
            for tracked in self._orders.values()
            if (
                tracked.oca_group == oca_group_ori
                and tracked.order.orderType == order.orderType
                and tracked.order.action == order.action
                and tracked.is_active
            )
        ]
        assert len(orders) <= 1, (
            f"Multiple active {order.orderType} {order.action}"
            f" orders found for OCA group {order.ocaGroup}"
        )
        return next(iter(orders), None)

    def __find_oca_group(self, oca_group: str) -> str | None:
        """Check if any active order exists in given OCA group."""
        oca_group = next(iter(oca_group.split("@")), oca_group)

        if not oca_group:
            return None

        return next(
            iter(
                [
                    tracked.order.ocaGroup
                    for tracked in self._orders.values()
                    if (tracked.oca_group == oca_group and tracked.is_active)
                ]
            ),
            None,
        )

    def __notify_hooks(self, orderId: int) -> None:
        """Notify all registered hooks with current orders.

        Called from reader thread after reconnect snapshot.
        """
        tracked: TrackedOrder = self._orders[orderId]

        notify_list: list[TrackedOrder] = [tracked]

        # When a parent fills, re-notify its children so downstream
        # consumers (OrderManager) can reclassify them as position brackets.
        if tracked.domain_status == OrderStatus.FILLED:
            for child in self._orders.values():
                if child.order.parentId == orderId:
                    notify_list.append(child)

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

    async def __order_update(
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

    # --- Reset Helper for testing ---
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
        self.__order_id_count = count()

    # --- Order request hooks (main thread) ---

    def __ensure_snapshot_requested(self) -> None:
        if not self._snapshot_requested.is_set():
            VERSION = 1
            self.ibsocket.send_message(OUT.REQ_OPEN_ORDERS, [VERSION])
            if DEBUG_TWS_REQUEST:
                logger.info("requested open orders")
            self._snapshot_requested.set()

    def __placeOrder(self, order_id: int, contract: Contract, order: Order) -> None:
        # Use protobuf encoding for server version >= 203
        assert (
            isinstance(order_id, int) and order_id >= 0
        ), "order_id must be a non-negative integer."
        assert (
            isinstance(contract, Contract) and contract.conId != 0
        ), "contract must be an instance of Contract with a non-zero conId."
        proto_msg = createPlaceOrderRequestProto(order_id, contract, order)
        serialized = proto_msg.SerializeToString()
        # Protobuf message ID = OUT.PLACE_ORDER + 200
        proto_msg_id = OUT.PLACE_ORDER + PROTOBUF_MSG_ID
        self.ibsocket.send_protobuf(proto_msg_id, serialized)
        if DEBUG_TWS_REQUEST:
            ticker = ticker_name(contract)
            logger.info(
                f"placed order (protobuf): id={order_id}, ticker={ticker}, Exchange={contract.exchange} "
                f"action={order.action}, type={order.orderType} "
                f"qty={order.totalQuantity}, price={order.lmtPrice or order.auxPrice} "
            )

    def __submit_order(
        self,
        contract: Contract,
        order: Order,
        parent_id: int = 0,
        transmit: bool = False,
    ) -> tuple[int, bool]:
        order_id = order.orderId
        place_flag = True
        tracked: TrackedOrder | None = self.__find_tracked_order(
            order,
        )
        if tracked:
            order_ori = tracked.clone_order()
            order_id = tracked.orderId
            # we only modify allowed fields. for more infos
            # check 02-API-REFERENCE-CONTRACTS-ORDERS.md
            assert (
                tracked.contract.conId == contract.conId
            ), f"Cannot change contract of an existing order {tracked.contract.conId} -> {contract.conId}"
            assert (
                not contract.exchange or tracked.contract.exchange == contract.exchange
            ), f"Cannot change exchange of an existing order {tracked.contract.exchange} -> {contract.exchange}"
            assert (
                not parent_id or order_ori.parentId == parent_id
            ), f"Cannot change parentId of an existing order {order_ori.parentId} -> {parent_id}"
            place_flag = False
            if order.lmtPrice != UNSET_DOUBLE and order_ori.lmtPrice != order.lmtPrice:
                order_ori.lmtPrice = order.lmtPrice
                place_flag = True
            if order.auxPrice != UNSET_DOUBLE and order_ori.auxPrice != order.auxPrice:
                order_ori.auxPrice = order.auxPrice
                place_flag = True
            if (
                order.totalQuantity != UNSET_DECIMAL
                and order_ori.totalQuantity != order.totalQuantity
            ):
                order_ori.totalQuantity = order.totalQuantity
                place_flag = True
            order = order_ori
            order.tif = ""  # do not modify time-in-force for existing orders
            order.transmit = True  # always transmit existing orders
        else:
            order_id = self.next_order_id
            order.parentId = parent_id
            order.transmit = transmit

        if place_flag:
            self.__placeOrder(order_id, contract, order)

        return order_id, place_flag

    def __cancelOrder(self, order_id: int) -> None:
        orderCancel = OrderCancel()
        cancelOrderRequestProto = createCancelOrderRequestProto(order_id, orderCancel)
        serializedString = cancelOrderRequestProto.SerializeToString()

        self.ibsocket.send_protobuf(
            OUT.CANCEL_ORDER + PROTOBUF_MSG_ID, serializedString
        )

        if DEBUG_TWS_REQUEST:
            logger.info(f"cancelled order: id={order_id}")

    # --- Order management (reader thread) ---

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

        self.__notify_hooks(orderId)

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

        self.__notify_hooks(orderId)

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

    # --- Exposed Order methods (main thread) ---

    async def reqOpenOrders(self, timeout: float | None = None) -> list[TrackedOrder]:
        """Register a future to be resolved when snapshot completes.

        Called from main thread. If snapshot is already complete,
        resolves immediately.

        Args:
            loop: Event loop for the future
            future: Future to resolve with order list
        """

        self.__ensure_snapshot_requested()

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

    async def placeWhatifOrder(
        self, contract: Contract, order: Order, timeout: float
    ) -> TrackedOrder:
        """Place an order via TWS.

        Allocates a unique order ID and submits the order. Order status updates
        are delivered via openOrder() and orderStatus() callbacks.

        Args:
            contract: Contract to trade
            order: Order parameters (type, side, quantity, price, etc.)

        Returns:
            The allocated order ID

        Note:
            For server version >= 203, uses protobuf encoding (required by TWS).
            For older server versions, uses legacy message format.
        """

        if order.orderId != -1:
            logger.warning(
                "placeWhatifOrder called with pre-set order.orderId; "
                "this may cause unexpected behavior"
            )
            order.orderId = -1
        if not order.whatIf:
            logger.warning(
                "placeWhatifOrder called with order.whatIf=False; "
                "proceeding to place a regular order"
            )
            order.whatIf = True
        order_id = self.next_order_id
        self.__placeOrder(order_id, contract, order)
        return await self.__order_update(order_id, timeout=timeout)

    async def placeOcaGroup(
        self,
        contract: Contract,
        order_list: list[Order],
        oca_group: str,
        oca_type: int = 1,
        parent_id: int = 0,
        timeout: float | None = None,
    ) -> list[TrackedOrder]:
        """Place multiple orders linked by OCA (One-Cancels-All) group.

        Used for position brackets where no parent order exists.
        When one order in the group fills, TWS automatically cancels the rest.

        Args:
            contract: The contract for all orders
            orders: List of Order objects (e.g., stop loss + take profit)
            oca_group: Unique OCA group identifier string
            oca_type: OCA behavior type:
                1 = Cancel all remaining with block (overfill protection) - RECOMMENDED
                2 = Proportional reduce with block
                3 = Proportional reduce no block

        Returns:
            List of TrackedOrder for each submitted order
        """
        if not order_list:
            return []

        if not oca_group.startswith("brackets_"):
            raise ValueError("oca_group must start with 'brackets_'")

        # get or create unique OCA group name
        transmit_all = False
        signed_oca_group = self.__find_oca_group(oca_group)
        if signed_oca_group:
            transmit_all = True
        else:
            signed_oca_group = f"{oca_group}@{int(time.time() * 1000)}"

        # Assign OCA attributes to each order
        for order in order_list:
            order.ocaGroup = signed_oca_group
            order.ocaType = oca_type

        submit_results = [
            self.__submit_order(
                contract, order, parent_id=parent_id, transmit=transmit_all
            )
            for order in order_list[:-1]
        ]
        submit_results.append(
            self.__submit_order(
                contract, order_list[-1], parent_id=parent_id, transmit=True
            )
        )

        tracked_list = await asyncio.gather(
            *[
                self.__order_update(oid, timeout=timeout)
                for oid, placed in submit_results
                if placed
            ]
        ) + [
            self.__assert_order_exists(oid)
            for oid, placed in submit_results
            if not placed
        ]

        return list(tracked_list)

    async def placeOrderGroup(
        self,
        contract: Contract,
        parent: Order,
        children: list[Order],
        timeout: float | None = None,
    ) -> tuple[TrackedOrder, list[TrackedOrder]]:
        """Place a parent order with optional child orders (bracket).

        Allocates unique order IDs and submits orders atomically.
        Parent is submitted first, children use transmit chain pattern.

        Args:
            contract: Contract to trade
            parent: Parent order (entry order)
            children: Child orders (stop loss, take profit, etc.)

        Returns:
            Tuple of (parent TrackedOrder, list of child TrackedOrders)
        """
        parent_id, placed = self.__submit_order(
            contract, parent, transmit=(not children)
        )

        children_tracked: list[TrackedOrder] = []
        if children:
            children_tracked = await self.placeOcaGroup(
                contract,
                children,
                oca_group=f"brackets_{parent_id}",
                oca_type=1,
                parent_id=parent_id,
            )

        parent_tracked = (
            (await self.__order_update(parent_id, timeout=timeout))
            if placed
            else self.__assert_order_exists(parent_id)
        )

        return parent_tracked, children_tracked

    async def cancelOrder(self, order_id: int, timeout: float) -> TrackedOrder:
        """Cancel an order via TWS.

        Args:
            order_id: Order ID to cancel
        """

        self.__assert_order_exists(order_id)
        self.__cancelOrder(order_id)
        return await self.__order_update(order_id, timeout=timeout)

    # --- Reset and hooks (main thread) ---

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
        self.__ensure_snapshot_requested()
        key = str(uuid.uuid4())
        self._stream_hooks[key] = (loop, callback, on_error)
        return key

    def remove_stream_hook(self, key: str) -> None:
        """Unregister order update callback."""
        self._stream_hooks.pop(key, None)
