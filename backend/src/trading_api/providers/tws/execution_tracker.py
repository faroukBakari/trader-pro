"""Execution tracking for TWS broker integration.

Data structures and helper class for tracking TWS execution callbacks.
Raw TWS objects (Contract, Execution) are stored directly.
Domain conversion happens via TrackedExecution.to_domain() method.

Commission Joining Strategy:
    TWS sends execDetails and commissionAndFeesReport as separate callbacks.
    We dispatch immediately on execDetails (commission=None), then re-dispatch
    when commissionAndFeesReport arrives with the enriched execution.
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import uuid
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from ibapi.client_utils import createExecutionRequestProto
from ibapi.common import PROTOBUF_MSG_ID
from ibapi.contract import Contract
from ibapi.execution import Execution as TWSExecution
from ibapi.execution import ExecutionFilter
from ibapi.message import OUT

from trading_api.models.broker import Execution, Side
from trading_api.models.exceptions import ProviderException
from trading_api.providers.tws.wiring_interfaces import (
    ExecutionTrackerCBWiringInterface,
    IbSocketWiringInterface,
)

logger = logging.getLogger(__name__)

DEBUG_TWS_REQUEST = os.environ.get("DEBUG_TWS_REQUEST") == "true"


def _parse_tws_execution_time(time_str: str) -> int:
    """Parse TWS execution time to unix milliseconds.

    TWS format: "YYYYMMDD HH:MM:SS TZ" where TZ is IANA timezone (e.g., "US/Eastern").
    Also handles legacy formats: "YYYYMMDD-HH:MM:SS" or "YYYYMMDD HH:MM:SS" (no timezone).

    Args:
        time_str: TWS execution time string (e.g., "20260120 07:10:09 US/Eastern")

    Returns:
        Unix timestamp in milliseconds (UTC)
    """
    # Normalize separator: "20240115-14:30:45" → "20240115 14:30:45"
    normalized = time_str.replace("-", " ").replace("  ", " ")

    # Split into parts: ['20260120', '07:10:09', 'US/Eastern'] or ['20260120', '07:10:09']
    parts = normalized.split(" ")

    try:
        dt_str = f"{parts[0]} {parts[1]}"
        dt = datetime.strptime(dt_str, "%Y%m%d %H:%M:%S")

        # Apply timezone if provided, otherwise assume UTC
        if len(parts) >= 3:
            tz_name = " ".join(parts[2:])  # Handle "US/Eastern" or multi-word TZ
            tz = ZoneInfo(tz_name)
            dt = dt.replace(tzinfo=tz)
        else:
            dt = dt.replace(tzinfo=timezone.utc)

        # Convert to UTC milliseconds
        return int(dt.timestamp() * 1000)
    except (ValueError, KeyError, IndexError):
        # Fallback: return current time if parsing fails
        return int(datetime.now(timezone.utc).timestamp() * 1000)


@dataclass
class TrackedExecution:
    """Wraps raw TWS execution data with optional commission enrichment.

    Stores the Contract and Execution objects from execDetails callback
    without data transformation. Commission is enriched later via
    commissionAndFeesReport callback.

    Thread Safety:
        - Created by reader thread on execDetails
        - Commission enriched by reader thread on commissionAndFeesReport
        - Passed by reference to main thread callbacks (no copies)
        - Main thread consumers should not mutate these objects
    """

    contract: Contract
    execution: TWSExecution
    commission: float | None = field(default=None)

    @property
    def exec_id(self) -> str:
        """Unique execution ID from TWS."""
        return self.execution.execId

    @property
    def symbol(self) -> str:
        """Ticker format: EXCHANGE:SYMBOL."""
        return f"{self.contract.exchange}:{self.contract.symbol}"

    def to_domain(self) -> Execution:
        """Convert to domain Execution model.

        Uses runtime imports to avoid circular dependencies.

        Returns:
            Domain Execution model for frontend consumption
        """

        return Execution(
            id=self.exec_id,
            symbol=self.symbol,
            price=self.execution.price,
            qty=float(self.execution.shares),
            side=Side.BUY if self.execution.side == "BOT" else Side.SELL,
            time=_parse_tws_execution_time(self.execution.time),
            commission=self.commission,
        )


# TODO: group smart/overnight executions
class ExecutionTracker(ExecutionTrackerCBWiringInterface):
    """Manages execution state for IBSocket. Thread-safe via asyncio dispatch.

    Follows the tracker pattern (OrderTracker, PositionTracker):
    - Reader thread: upsert_execution(), update_commission(), mark_snapshot_complete()
    - Main thread: all_executions(), create_stream_hook()

    Commission Joining:
        execDetails arrives first (commission=None), then commissionAndFeesReport
        arrives ~50-200ms later. We dispatch immediately on execDetails, then
        re-dispatch when commission arrives so subscribers get the enriched data.

    Thread Ownership:
        - Envelope (hooks registration, reset): main thread
        - Content (executions dict): reader thread writes, main thread reads
        - Dispatch (callbacks): reader thread schedules, main thread executes
    """

    def __init__(self, ibsocket: IbSocketWiringInterface) -> None:
        ibsocket.wire_execution_tracker(self)
        self.ibsocket = ibsocket
        self._snapshot_requested = threading.Event()
        self._snapshot_complete = threading.Event()
        self._executions: dict[str, TrackedExecution] = {}  # exec_id → TrackedExecution
        self._snapshot_hooks: dict[
            str,
            tuple[asyncio.AbstractEventLoop, asyncio.Future[list[TrackedExecution]]],
        ] = {}
        self._stream_hooks: dict[
            str,
            tuple[
                asyncio.AbstractEventLoop,
                Callable[[TrackedExecution], Coroutine[Any, Any, None]],
                Callable[[ProviderException], Coroutine[Any, Any, None]],
            ],
        ] = {}

    # =========================================================================
    # Reader Thread Methods (called from IBSocket callbacks)
    # =========================================================================

    def ensure_snapshot_requested(self) -> None:
        """Send reqExecutions() if not already requested.

        Internalizes TWS protocol: sends OUT.REQ_EXECUTIONS via protobuf.
        Called from main thread before snapshot/stream operations.
        """
        if not self._snapshot_requested.is_set():
            reqId = self.ibsocket.next_req_id
            exec_filter = ExecutionFilter()
            exec_request_proto = createExecutionRequestProto(reqId, exec_filter)
            serialized = exec_request_proto.SerializeToString()
            self.ibsocket.send_protobuf(
                OUT.REQ_EXECUTIONS + PROTOBUF_MSG_ID, serialized
            )
            self._snapshot_requested.set()
            if DEBUG_TWS_REQUEST:
                logger.info(f"requested executions reqId={reqId}")

    def upsert_execution(
        self,
        contract: Contract,
        execution: TWSExecution,
    ) -> None:
        """Create or update TrackedExecution from execDetails callback.

        Called from reader thread. Dispatches to stream hooks immediately
        (commission may be None, will re-dispatch on enrichment).

        Args:
            contract: Contract object from execDetails
            execution: Execution object from execDetails
        """
        exec_id = execution.execId
        tracked = self._executions.get(exec_id)

        if tracked is not None:
            # Update existing (rare - usually new executions)
            tracked.execution = execution
            tracked.contract = contract
        else:
            tracked = self._executions[exec_id] = TrackedExecution(
                contract=contract,
                execution=execution,
            )

        self._dispatch_to_stream_hooks(tracked)

    def update_commission(self, exec_id: str, commission: float) -> None:
        """Enrich execution with commission from commissionAndFeesReport.

        Called from reader thread. Re-dispatches to stream hooks so
        subscribers receive the enriched execution.

        Args:
            exec_id: Execution ID to enrich
            commission: Commission amount from commissionAndFeesReport
        """
        tracked = self._executions.get(exec_id)
        if tracked is not None:
            tracked.commission = commission
            # Re-dispatch with commission
            self._dispatch_to_stream_hooks(tracked)

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
        """Mark snapshot as complete. Called from execDetailsEnd."""
        self._snapshot_complete.set()

        for loop, future in self._snapshot_hooks.values():

            def resolve_hook(
                future: asyncio.Future, executions: list[TrackedExecution]
            ) -> None:
                if not future.done():
                    future.set_result(executions)

            loop.call_soon_threadsafe(
                resolve_hook, future, list(self._executions.values())
            )

    # =========================================================================
    # Main Thread Methods (called from TWSClient/BrokerProvider)
    # =========================================================================

    def reset(self) -> None:
        """Full reset - like fresh creation.

        Clears all executions, snapshot state, and hooks.
        Called from main thread before new snapshot request.
        """
        self._executions.clear()
        self._snapshot_requested.clear()
        self._snapshot_complete.clear()
        self._snapshot_hooks.clear()
        self._stream_hooks.clear()

    async def all_executions(
        self, filter_symbol: str = "", timeout: float | None = None
    ) -> list[TrackedExecution]:
        """Get all executions, waiting for snapshot if needed.

        Called from main thread. If snapshot is already complete,
        resolves immediately.

        Args:
            filter_symbol: Optional symbol to filter by (e.g., "NASDAQ:AAPL")
            timeout: Optional timeout in seconds

        Returns:
            List of TrackedExecution objects, optionally filtered
        """
        self.ensure_snapshot_requested()

        loop = asyncio.get_running_loop()
        future: asyncio.Future[list[TrackedExecution]] = loop.create_future()

        if self._snapshot_complete.is_set():
            executions = list(self._executions.values())
        else:
            key = str(uuid.uuid4())
            self._snapshot_hooks[key] = (loop, future)

            try:
                executions = await asyncio.wait_for(future, timeout)
            finally:
                self._snapshot_hooks.pop(key, None)

        if filter_symbol:
            executions = [e for e in executions if e.symbol == filter_symbol]
        return executions

    def create_stream_hook(
        self,
        callback: Callable[[TrackedExecution], Coroutine[Any, Any, None]],
        on_error: Callable[[ProviderException], Coroutine[Any, Any, None]],
    ) -> str:
        """Register callback for execution updates.

        Called from main thread. Callback will be invoked:
        1. When execDetails arrives (commission=None)
        2. When commissionAndFeesReport arrives (commission enriched)

        Args:
            callback: Called for each execution update
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
        """Unregister execution update callback."""
        self._stream_hooks.pop(key, None)

    # =========================================================================
    # Internal
    # =========================================================================

    def _dispatch_to_stream_hooks(self, tracked: TrackedExecution) -> None:
        """Dispatch execution to all stream hooks.

        Called from reader thread.
        """
        for stream_loop, stream_callback, _ in self._stream_hooks.values():
            stream_loop.call_soon_threadsafe(
                stream_loop.create_task,
                stream_callback(tracked),
            )
