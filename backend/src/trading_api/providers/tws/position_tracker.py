"""Position tracking for TWS broker integration.

Data structures and helper class for tracking TWS position callbacks without
data transformation. Raw TWS objects (Contract) are stored directly.
Domain conversion happens via TrackedPosition.to_domain() method.
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import uuid
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from ibapi.contract import Contract
from ibapi.message import OUT

from trading_api.models.exceptions import ProviderException
from trading_api.providers.tws.wiring_interfaces import (
    IbSocketWiringInterface,
    PositionTrackerCBWiringInterface,
)

if TYPE_CHECKING:
    from trading_api.models.broker import Position

logger = logging.getLogger(__name__)

DEBUG_TWS_REQUEST = os.environ.get("DEBUG_TWS_REQUEST") == "true"


@dataclass
class TrackedPosition:
    """Wraps raw TWS position data.

    Stores the Contract object from position callback without any data
    transformation. Domain conversion happens via to_domain() method.

    Thread Safety:
        - Created/updated by reader thread
        - Passed by reference to main thread callbacks (no copies)
        - Main thread consumers should not mutate these objects
    """

    account: str
    contract: Contract
    position: Decimal  # Positive = long, negative = short
    avgCost: float

    @property
    def position_key(self) -> str:
        """Unique key for this position (account:conId)."""
        return f"{self.account}:{self.contract.conId}"

    def to_domain(self) -> "Position":
        """Convert to domain Position model.

        Uses runtime imports to avoid circular dependencies.

        Returns:
            Domain Position model for frontend consumption
        """
        from trading_api.models.broker import Position, Side
        from trading_api.providers.tws.tws_mappers import ticker_name

        symbol = ticker_name(self.contract)
        qty_float = float(self.position)

        return Position(
            id=symbol,
            symbol=symbol,
            qty=abs(qty_float),
            side=Side.BUY if qty_float >= 0 else Side.SELL,
            avgPrice=float(self.avgCost),
        )


class PositionTracker(PositionTrackerCBWiringInterface):
    """Manages position state for IBSocket. Thread-safe via asyncio dispatch.

    Simpler than OrderTracker:
    - No orderId generation needed
    - No per-position waiting hooks
    - No fills history (positions are net aggregates)

    Thread Ownership:
        - Envelope (hooks registration, reset): main thread
        - Content (positions dict): reader thread writes, main thread reads
        - Dispatch (callbacks): reader thread schedules, main thread executes

    Usage:
        - Snapshot: reqPositions() → all_positions() → resolve_snapshots()
        - Subscription: reqPositionsStream() → create_stream_hook() → dispatch_update()
    """

    def __init__(self, ibsocket: IbSocketWiringInterface) -> None:
        ibsocket.wire_position_tracker(self)
        self.ibsocket = ibsocket
        self._snapshot_requested = threading.Event()
        self._snapshot_complete = threading.Event()
        self._positions: dict[str, TrackedPosition] = {}
        self._snapshot_hooks: dict[
            str, tuple[asyncio.AbstractEventLoop, asyncio.Future[list[TrackedPosition]]]
        ] = {}
        self._stream_hooks: dict[
            str,
            tuple[
                asyncio.AbstractEventLoop,
                Callable[[TrackedPosition], Coroutine[Any, Any, None]],
                Callable[[ProviderException], Coroutine[Any, Any, None]],
            ],
        ] = {}

    # --- Position management (reader thread) ---

    def ensure_snapshot_requested(self) -> None:
        """Send reqPositions() if not already requested.

        Called from reader thread before position callbacks.
        """
        if not self._snapshot_requested.is_set():
            VERSION = 1
            self.ibsocket.send_message(OUT.REQ_POSITIONS, [VERSION])
            self._snapshot_requested.set()
            if DEBUG_TWS_REQUEST:
                logger.info("requested positions")

    def upsert_position(
        self,
        account: str,
        contract: Contract,
        position: Decimal,
        avgCost: float,
    ) -> None:
        """Create or replace TrackedPosition from position callback.

        Called from reader thread. Stores fresh TWS objects directly.

        Args:
            account: Account ID holding the position
            contract: Fresh Contract object from decoder
            position: Position quantity (positive=long, negative=short)
            avgCost: Average cost per unit
        """
        tracked = TrackedPosition(
            account=account,
            contract=contract,
            position=position,
            avgCost=avgCost,
        )
        self._positions[tracked.position_key] = tracked

        for stream_loop, stream_callback, _ in self._stream_hooks.values():
            stream_loop.call_soon_threadsafe(
                stream_loop.create_task,
                stream_callback(tracked),
            )

    def raise_error(self, exception: ProviderException) -> None:
        """Dispatch error to all hooks.

        Called from reader thread.
        """
        # Dispatch to snapshot hooks
        for snapshot_loop, snapshot_future in self._snapshot_hooks.values():

            def resolve_snapshot_error(
                future: asyncio.Future, exc: ProviderException
            ) -> None:
                if not future.done():
                    future.set_exception(exc)

            snapshot_loop.call_soon_threadsafe(
                resolve_snapshot_error, snapshot_future, exception
            )

        # Dispatch to stream hooks
        for stream_loop, _, on_error in self._stream_hooks.values():
            stream_loop.call_soon_threadsafe(
                stream_loop.create_task,
                on_error(exception),
            )

    def mark_snapshot_complete(self) -> None:
        """Mark snapshot as complete. Called from positionEnd."""
        self._snapshot_complete.set()

        for loop, future in self._snapshot_hooks.values():

            def resolve_hook(
                future: asyncio.Future, positions: list[TrackedPosition]
            ) -> None:
                if not future.done():
                    future.set_result(positions)

            loop.call_soon_threadsafe(
                resolve_hook, future, list(self._positions.values())
            )

    # --- Position registrations (main thread) ---

    def reset(self) -> None:
        """Full reset - like fresh creation.

        Clears all positions, snapshot state, and hooks.
        Called from main thread before new snapshot request.
        """
        self._positions.clear()
        self._snapshot_requested.clear()
        self._snapshot_complete.clear()
        self._snapshot_hooks.clear()
        self._stream_hooks.clear()

    async def all_positions(
        self, timeout: float | None = None
    ) -> list[TrackedPosition]:
        """Get all positions, waiting for snapshot if needed.

        Called from main thread. If snapshot is already complete,
        resolves immediately.

        Args:
            timeout: Optional timeout in seconds

        Returns:
            List of TrackedPosition objects
        """

        self.ensure_snapshot_requested()

        loop = asyncio.get_running_loop()
        future: asyncio.Future[list[TrackedPosition]] = loop.create_future()

        if self._snapshot_complete.is_set():
            future.set_result(list(self._positions.values()))
            return await asyncio.wait_for(future, timeout)

        key = str(uuid.uuid4())
        self._snapshot_hooks[key] = (loop, future)

        try:
            return await asyncio.wait_for(future, timeout)
        finally:
            self._snapshot_hooks.pop(key, None)

    def create_stream_hook(
        self,
        callback: Callable[[TrackedPosition], Coroutine[Any, Any, None]],
        on_error: Callable[[ProviderException], Coroutine[Any, Any, None]],
    ) -> str:
        """Register callback for position updates.

        Called from main thread.

        Args:
            loop: Event loop for callbacks
            callback: Called for each position update
            on_error: Error callback

        Returns:
            Unique key for unsubscription
        """
        self.ensure_snapshot_requested()

        loop = asyncio.get_event_loop()

        key = str(uuid.uuid4())
        self._stream_hooks[key] = (loop, callback, on_error)
        return key

    def remove_stream_hook(self, key: str) -> None:
        """Unregister position update callback."""
        self._stream_hooks.pop(key, None)
