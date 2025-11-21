"""Pure TWS protocol - synchronous callbacks with zero-copy dispatch.

Layer 1 of TWS integration:
- Extends EWrapper (callbacks) and EClient (requests)
- Zero-copy callback dispatch (< 2µs latency target)
- Thread-safe request ID generation
- No AsyncIO - pure sync callbacks in TWS reader thread
- Signals end-of-stream with None parameter
- Passes Exception objects directly (no re-wrapping)

Performance Design:
- Callback dispatch: Direct dict lookup + function call
- No data copying: Pass TWS objects by reference
- No string operations: Use None for end signals
- Minimal locking: Only for request ID generation
"""

import logging
import threading
from collections.abc import Sequence
from decimal import Decimal
from typing import Any, Callable

from ibapi.client import EClient
from ibapi.reader import EReader
from ibapi.wrapper import EWrapper

logger = logging.getLogger(__name__)


class TWSConnection(EWrapper, EClient):
    """Pure TWS protocol - synchronous callbacks with zero-copy dispatch.

    Performance targets:
    - Callback dispatch: < 2 µs (dict lookup + call)
    - Data copying: Zero-copy (pass by reference)
    - String operations: None (use None for end signals)

    Thread Safety:
    - Callbacks execute in TWS reader thread
    - Request ID generation uses lock
    - Callback registry accessed from both threads (dict is thread-safe for reads)
    """

    def __init__(self) -> None:
        """Initialize TWSConnection."""
        EClient.__init__(self, self)
        self.callbacks: dict[int, Callable] = {}  # Direct callback registry
        self.next_req_id = 1
        self._req_id_lock = threading.Lock()  # Only for ID generation
        self.is_ready = threading.Event()  # Connection state

    def get_req_id(self) -> int:
        """Thread-safe request ID generation.

        Returns:
            Unique request ID for TWS API calls
        """
        with self._req_id_lock:
            req_id = self.next_req_id
            self.next_req_id += 1
            return req_id

    def connect_and_run(
        self, host: str = "127.0.0.1", port: int = 7497, client_id: int = 1
    ) -> None:
        """Connect and start message loop (blocking - must run in thread).

        Args:
            host: TWS/Gateway hostname
            port: TWS/Gateway port
            client_id: Client ID (1-32)

        Note:
            This method blocks until disconnect - must be run in a separate thread.
        """
        self.connect(host, port, client_id)
        reader = EReader(self.conn, self.msg_queue)
        reader.start()
        self.run()  # Blocks until disconnect

    def nextValidId(self, orderId: int) -> None:
        """Connection ready callback - called by TWS after successful connection.

        Args:
            orderId: Next valid order ID from TWS
        """
        self.next_req_id = orderId
        self.is_ready.set()
        logger.info(f"TWS connected - next valid ID: {orderId}")

    # === Market Data Callbacks (Zero-Copy Dispatch) ===

    def symbolSamples(self, reqId: int, contractDescriptions: Sequence[Any]) -> None:
        """Single-response pattern - complete list of matching symbols.

        Args:
            reqId: Request ID
            contractDescriptions: List of ContractDescription objects
        """
        if cb := self.callbacks.get(reqId):
            cb(contractDescriptions)  # Pass by reference - no copy

    def contractDetails(self, reqId: int, contractDetails: Any) -> None:
        """Multi-response pattern - called once per contract.

        Args:
            reqId: Request ID
            contractDetails: ContractDetails object
        """
        if cb := self.callbacks.get(reqId):
            cb(contractDetails)  # Called multiple times

    def contractDetailsEnd(self, reqId: int) -> None:
        """End-of-stream signal for contractDetails.

        Args:
            reqId: Request ID
        """
        if cb := self.callbacks.get(reqId):
            cb(None)  # Signal completion with None

    def historicalData(self, reqId: int, bar: Any) -> None:
        """Multi-response pattern - called once per historical bar.

        Args:
            reqId: Request ID
            bar: BarData object
        """
        if cb := self.callbacks.get(reqId):
            cb(bar)  # Pass TWS BarData by reference

    def historicalDataEnd(self, reqId: int, start: str, end: str) -> None:
        """End-of-stream signal for historicalData.

        Args:
            reqId: Request ID
            start: Start date string
            end: End date string
        """
        if cb := self.callbacks.get(reqId):
            cb(None)  # Signal completion with None

    def realtimeBar(
        self,
        reqId: int,
        time: int,
        open_: float,
        high: float,
        low: float,
        close: float,
        volume: Decimal,
        wap: Decimal,
        count: int,
    ) -> None:
        """Continuous subscription - real-time 5-second bars.

        Args:
            reqId: Request ID
            time: Bar timestamp
            open_: Open price
            high: High price
            low: Low price
            close: Close price
            volume: Volume (Decimal from TWS)
            wap: Weighted average price (Decimal from TWS)
            count: Trade count
        """
        if cb := self.callbacks.get(reqId):
            cb(time, open_, high, low, close, volume, wap, count)

    def tickPrice(self, reqId: int, tickType: int, price: float, attrib: Any) -> None:
        """Continuous subscription - price tick updates.

        Args:
            reqId: Request ID
            tickType: Type of tick (bid/ask/last/etc)
            price: Price value
            attrib: Tick attributes
        """
        if cb := self.callbacks.get(reqId):
            cb(tickType, price, attrib)

    def tickSize(self, reqId: int, tickType: int, size: Decimal) -> None:
        """Continuous subscription - size tick updates.

        Args:
            reqId: Request ID
            tickType: Type of tick (bid/ask/volume/etc)
            size: Size value (Decimal from TWS)
        """
        if cb := self.callbacks.get(reqId):
            cb(tickType, size)

    def tickSnapshotEnd(self, reqId: int) -> None:
        """Snapshot end signal for market data snapshot.

        Args:
            reqId: Request ID
        """
        if cb := self.callbacks.get(reqId):
            cb(None)  # Signal completion with None

    def error(
        self,
        reqId: int,
        errorTime: int,
        errorCode: int,
        errorString: str,
        advancedOrderRejectJson: str = "",
    ) -> None:
        """Error callback - pass Exception object to registered callback.

        Args:
            reqId: Request ID (-1 for general errors)
            errorTime: Unix timestamp of error
            errorCode: TWS error code
            errorString: Error message
            advancedOrderRejectJson: Advanced order reject details (optional)
        """
        logger.error(
            f"TWS error [reqId={reqId}, time={errorTime}, code={errorCode}]: {errorString}"
        )
        if reqId != -1 and (cb := self.callbacks.get(reqId)):
            exc = Exception(f"TWS error {errorCode}: {errorString}")
            cb(exc)  # Pass Exception object - not string
