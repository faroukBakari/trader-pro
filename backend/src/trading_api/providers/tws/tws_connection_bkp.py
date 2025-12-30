"""Pure TWS protocol - synchronous callbacks with zero-copy dispatch.

Layer 1 of TWS integration:
- Pure EWrapper implementation (callbacks only)
- Zero-copy callback dispatch (< 2µs latency target)
- No connection management (handled by TWSDatafeedProvider)
- No request ID generation (handled by TWSDatafeedProvider)
- No AsyncIO - pure sync callbacks in TWS reader thread
- Signals end-of-stream with None parameter
- Passes Exception objects directly (no re-wrapping)

Performance Design:
- Callback dispatch: Direct dict lookup + function call
- No data copying: Pass TWS objects by reference
- No string operations: Use None for end signals

Architecture:
- Pure EWrapper inheritance (no EClient)
- Callback registry for request-based dispatch
- Used via composition by TWSDatafeedProvider
"""

import asyncio
import logging
import math
import os
import select
import struct
import threading
import time
from collections.abc import Awaitable, Callable
from decimal import Decimal
from functools import wraps
from itertools import count
from socket import MSG_PEEK
from socket import error as socketError
from socket import socket
from socket import timeout as socketTimeout
from typing import Any

# Protobuf imports for server version >= 203
from ibapi.client_utils import createPlaceOrderRequestProto
from ibapi.common import BarData, TickAttrib
from ibapi.const import DOUBLE_INFINITY, INFINITY_STR, UNSET_DOUBLE, UNSET_INTEGER
from ibapi.contract import Contract, ContractDescription, ContractDetails
from ibapi.decoder import Decoder
from ibapi.message import OUT
from ibapi.order import Order
from ibapi.order_state import OrderState
from ibapi.protobuf.ErrorMessage_pb2 import ErrorMessage as ErrorMessageProto
from ibapi.ticktype import TickTypeEnum
from ibapi.wrapper import EWrapper, current_fn_name

from trading_api.models.exceptions import ProviderException
from trading_api.providers.tws.order_tracker import OrderTracker, TrackedOrder
from trading_api.providers.tws.tws_mappers import ticker_name
from trading_api.providers.tws.tws_models import get_bar_duration_seconds

from .tws_models import TICK_TYPE_TO_FIELD, classify_error, get_asset_config

logger = logging.getLogger(__name__)
DEBUG_TWS_REQUEST = os.environ.get("DEBUG_TWS_REQUEST") == "true"
DEBUG_TWS_SEND = os.environ.get("DEBUG_TWS_SEND") == "true"
DEBUG_TWS_RECEIVE = os.environ.get("DEBUG_TWS_RECEIVE") == "true"
DEBUG_TWS_DISPATCH = os.environ.get("DEBUG_TWS_DISPATCH") == "true"
DEBUG_TWS_CALLBACK = os.environ.get("DEBUG_TWS_CALLBACK") == "true"
DEBUG_TWS_DATAFEED = os.environ.get("DEBUG_TWS_DATAFEED") == "true"
DEBUG_TWS_BROKER = os.environ.get("DEBUG_TWS_BROKER") == "true"

NO_VALID_ID = -1
MIN_CLIENT_VER = 100
MAX_CLIENT_VER = 203
PROTOBUF_MSG_ID = 200
VERSION = 2


# TWS Error Code Categories (for consistent ProviderException codes)
class TWSErrorCategory:
    """Error categories for TWS ProviderException codes.

    Convention: PROVIDER_TWS_{CATEGORY}_{DETAIL}
    """

    CONN = "CONN"  # Connection/socket errors
    API = "API"  # TWS API protocol errors (from error() callback)
    CALLBACK = "CALLBACK"  # Callback processing errors


def clean_self(param: dict) -> dict:
    """Helper to remove 'self' from method parameters for logging."""
    if isinstance(param, dict) and "self" in param:
        del param["self"]
    return param


def to_str(val: object) -> str:
    match val:
        # 1. Type Check: Boolean
        # Must act before int checks usually, though here we cast to int explicitly
        case bool():
            return str(int(val))

        # 2. Type Check: List
        case list():
            return ",".join(to_str(item) for item in val)

        # 3. Value Check: Unset constants
        case _:
            if val == UNSET_INTEGER or val == UNSET_DOUBLE:
                return ""
            if val == DOUBLE_INFINITY:
                return str(INFINITY_STR)
            return str(val)


NULL = b"\0"


def make_fields(values: list) -> bytes:
    result = bytearray()
    for v in values:
        result.extend(to_str(v).encode())
        result.extend(NULL)
    return bytes(result)


HEADER_STRUCT = struct.Struct(">I")


def decode_data(buf: bytearray, buf_siz: int) -> tuple[int, bytes, bytearray, int]:
    if buf_siz < 4:
        return -1, b"", buf, buf_siz
    msg_size = HEADER_STRUCT.unpack_from(buf, 0)[0]
    packet_end = 4 + msg_size
    if buf_siz >= packet_end:
        msgId = HEADER_STRUCT.unpack_from(buf, 4)[0]
        payload = bytes(buf[8:packet_end])
        del buf[:packet_end]
        buf_siz -= packet_end
        if DEBUG_TWS_RECEIVE:
            assert len(buf) == buf_siz, "Buffer size mismatch after decoding."
        return (
            msgId,
            payload,
            buf,
            buf_siz,
        )
    else:
        return -1, b"", buf, buf_siz


def get_duration_for_bars(bar_size: str, num_bars: int = 2) -> str:
    """Convert bar size to duration string for N bars."""
    # Map bar size to seconds
    secs = get_bar_duration_seconds(bar_size)
    total_secs = secs * num_bars

    # TWS prefers larger units when possible
    if total_secs >= 86400 and total_secs % 86400 == 0:
        return f"{total_secs // 86400} D"
    elif total_secs >= 3600:
        return f"{total_secs} S"  # TWS accepts seconds for any duration
    else:
        return f"{total_secs} S"


get_tick_type_name = TickTypeEnum.idx2name.get
debug_log = logger.info


def error_handler(capability: str = "shared") -> Callable:
    """Decorator for TWS callbacks with error handling.

    - Catches exceptions, routes through error handler
    - Keeps reader thread alive on callback errors
    - Never re-raises (protects reader thread stability)
    """

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(self: "IBSocket", reqId: int, *args: Any, **kwargs: Any) -> Any:
            try:
                return fn(self, reqId, *args, **kwargs)
            except Exception as e:
                self._handle_request_error(
                    category=TWSErrorCategory.CALLBACK,
                    detail=fn.__name__.upper(),
                    reqId=reqId,
                    message=f"{fn.__name__}: {e!r}",
                    capability_fallback=capability,
                )

        return wrapper

    return decorator


class IBSocketState:
    READY = 0
    CONNECTING = 1
    CONNECTED = 2
    RUNNING = 3
    ERROR = 4
    CLOSED = 5


class IBSocket(EWrapper):
    def __init__(self) -> None:
        # socket related attributes
        self._req_id_counter = count()
        self._socket_lock = threading.Lock()
        self._state = IBSocketState.READY
        self._socket = socket()
        self._reader_loop: asyncio.AbstractEventLoop | None = None

        self._server_version: str = ""
        self._connection_time: str = ""

        # callback related attributes
        self._future_hooks: dict[
            int, tuple[asyncio.AbstractEventLoop, asyncio.Future]
        ] = {}
        self._stream_hooks: dict[
            int,
            tuple[
                asyncio.AbstractEventLoop,
                Callable[
                    [dict[str, Any], list[str]],
                    Awaitable[None],
                ],
                Callable[[ProviderException], Awaitable[None]] | None,  # error callback
            ],
        ] = {}

        # Pending snapshot futures - separate from stream hooks
        # Maps reqId → (event_loop, Future) for quote snapshot resolution
        self._snapshot_hooks: dict[
            int, list[tuple[asyncio.AbstractEventLoop, asyncio.Future]]
        ] = {}

        # ticker name to reqId mapping for active streams
        self._active_streams: dict[str, int] = {}

        # Data tracking attributes
        self._future_data: dict[int, list[Any]] = {}
        self._stream_data: dict[int, dict[str, Any]] = {}
        self._nxt_order_id: int | None = None
        self._reader_accounts: list[str] = []

        # Order tracking - maps orderId → order data for streaming updates
        self._order_tracker = OrderTracker()

        # Position tracking - maps account → list of position data dicts
        self._position_data: dict[str, list[dict[str, Any]]] = {}
        # Position streaming callbacks - for position subscription
        self._position_hooks: (
            tuple[
                asyncio.AbstractEventLoop,
                Callable[[dict[str, Any]], Awaitable[None]],
                Callable[[ProviderException], Awaitable[None]] | None,
            ]
            | None
        ) = None
        # Future for reqPositions() completion
        self._positions_future: (
            tuple[asyncio.AbstractEventLoop, asyncio.Future[list[dict[str, Any]]]]
            | None
        ) = None

        # Account summary tracking - maps (reqId, tag) → value data
        self._account_summary_data: dict[int, dict[str, dict[str, Any]]] = {}
        # Future for reqAccountSummary() completion
        self._account_summary_future: (
            tuple[asyncio.AbstractEventLoop, asyncio.Future[dict[str, dict[str, Any]]]]
            | None
        ) = None

        # for error management on capability basis
        self._reqId_to_capability: dict[int, str] = {}

        # Signals when IBKR connection is fully established
        self._ready_event = threading.Event()

    # == default implementation for unimplemented methods ==

    def _dispatchMessage(self, fnName: str, fnParams: dict) -> None:
        if DEBUG_TWS_DISPATCH:
            if "self" in fnParams:
                fnParams = dict(fnParams)
                del fnParams["self"]
            debug_log(f"!!!WARNING!!!: unimplemented {fnName} --> {fnParams}")

    # == infrastructure methods (internal) ==

    def __del__(self) -> None:
        try:
            self.disconnect()
        except Exception:
            pass

    def _remotely_closed(self) -> bool:
        """Check if the remote side has closed the connection."""
        if self._socket.fileno() == -1:
            return True  # Socket already closed locally
        try:
            self._socket.getpeername()
        except OSError:
            return True
        try:
            ready_to_read, _, _ = select.select([self._socket], [], [], 0)
            if ready_to_read:
                data = self._socket.recv(1, MSG_PEEK)
                if len(data) == 0:
                    return True  # Remote side has closed the connection
            return False  # Connection is still open
        except socketError:
            return True  # Assume closed on error

    def _receive_data(
        self, read_buf: bytearray, buf_siz: int = 0
    ) -> tuple[int, bytes, bytearray, int]:
        """Optimized receive - called in hot path from _reader_method."""
        new_data_received = False
        assert self._state == IBSocketState.RUNNING, "Socket is not connected."
        sock_recv = self._socket.recv  # Cache method lookup
        while True:
            try:
                data = sock_recv(4096)
                assert data, "Socket connection closed."
                read_buf.extend(data)
                receiv_siz = len(data)
                buf_siz += receiv_siz
                new_data_received = True
                if receiv_siz < 4096:
                    break
            except socketTimeout:
                # No more data available right now
                break

        if new_data_received:
            # Direct join - chunks list never contains falsy values
            if DEBUG_TWS_RECEIVE:
                debug_log(
                    "Final received data: <%s>",
                    read_buf.decode("ascii", errors="ignore"),
                )
        return decode_data(read_buf, buf_siz)

    def _reader_task(self, server_version: int) -> None:
        """TWS reader loop - to be run in a separate thread.

        Note:
            This method should be called in a dedicated thread to continuously
            read messages from the IBSocket connection and dispatch them to
            the appropriate EWrapper callback methods.
        """

        if self._state != IBSocketState.CONNECTED:
            self._state = IBSocketState.ERROR
            raise RuntimeError("_reader_method Startup error : Socket not connected.")

        decoder = Decoder(self, server_version)
        debug_log("IBSocket reader loop started.")

        # Cache method references for hot path (avoid attribute lookup per iteration)
        recv = self._receive_data
        process_proto = decoder.processProtoBuf
        interpret = decoder.interpret

        buf = bytearray()
        buf_siz = 0

        # self._reader_loop = asyncio.get_running_loop()
        self._state = IBSocketState.RUNNING
        running = True
        while running:
            try:
                msgId = -1
                msgId, data, buf, buf_siz = recv(buf, buf_siz)

                if msgId == -1:
                    # Incomplete message - only log if debugging enabled
                    if buf_siz > 0:
                        if DEBUG_TWS_RECEIVE:
                            debug_log(
                                "Incomplete message in buffer, waiting for more data. "
                                "Buffer size: %d",
                                buf_siz,
                            )
                    continue

                if msgId > PROTOBUF_MSG_ID:
                    msgId -= PROTOBUF_MSG_ID
                    if DEBUG_TWS_DISPATCH:
                        debug_log("msgId: %d, protobuf: %s", msgId, data)
                    process_proto(data, msgId)
                else:
                    # Direct split - no list comprehension wrapper needed
                    fields = data.split(NULL)[:-1]  # Remove trailing empty field
                    if DEBUG_TWS_DISPATCH:
                        debug_log("msgId: %d, interpret: %s", msgId, fields)
                    # Remove trailing empty field (split always produces one)
                    interpret(fields, msgId)

            except Exception as e:
                running = self._state == IBSocketState.RUNNING
                if not running or self._remotely_closed():
                    self._state = IBSocketState.ERROR
                    # Socket closed remotely
                    raise ProviderException(
                        provider="tws",
                        capability="shared",
                        code=f"PROVIDER_TWS_{TWSErrorCategory.CONN}_CLOSED",
                        message=f"IBSocket connection closed: {e!r}",
                    )
                logger.exception(
                    "Unexpected exception in IBSocket reader loop (running: %d): %s",
                    running,
                    e,
                )
                time.sleep(0.5)

        debug_log("IBSocket reader loop finished.")

    def _reset(self) -> None:
        """Reset internal state - clear futures, accumulators, callbacks."""
        with self._socket_lock:
            self._future_hooks.clear()
            self._future_data.clear()
            self._stream_data.clear()
            self._reader_accounts.clear()
            self._ready_event.clear()
            self._nxt_order_id = None

    def _handle_request_error(
        self,
        category: str,
        detail: str,
        reqId: int,
        message: str,
        capability_fallback: str = "shared",
        timestamp: int | None = None,
    ) -> None:
        """Create a standardized ProviderException for TWS errors.
            Route error to appropriate handler based on request state.

            Handles three scenarios:
            1. stream exists → notify stream error callback
            2. Future exists → reject future with error
            3. Neither → log warning (orphan error)

            For non-recoverable errors (detail ends with _NON_RECOVERABLE):
            - Cleans up all associated data structures for the reqId
            - Removes hooks, data, and capability tracking

            This method never raises - errors are stored/routed, not propagated.

        Args:
            category: Error category (TWSErrorCategory.CONN, API, CALLBACK)
            detail: Error detail (e.g., function name or TWS error code)
            reqId: Request ID (-1 for system errors)
            message: Human-readable error description
            capability_fallback: Capability to use if reqId not tracked
            timestamp: Optional Unix timestamp (defaults to None)

        Returns:
            ProviderException with consistent code format:
            PROVIDER_TWS_{CATEGORY}_{DETAIL}
        """

        error = ProviderException(
            code=f"PROVIDER_TWS_{category}_{detail.upper()}",
            message=f"[reqId={reqId}] {message}",
            provider="tws",
            capability=self._reqId_to_capability.setdefault(reqId, capability_fallback),
            timestamp=timestamp,
        )

        # 1. Check for pending future
        future_loop, _ = self._future_hooks.get(reqId, (None, None))
        if future_loop is not None:

            def _reject_in_loop(reqId: int, error: ProviderException) -> None:
                self._future_data.pop(reqId, None)
                _, future = self._future_hooks.pop(reqId, (None, None))
                if future is not None and not future.done():
                    future.set_exception(error)

            future_loop.call_soon_threadsafe(_reject_in_loop, reqId, error)

        # 2. Check for active stream
        stream_loop, _, on_error = self._stream_hooks.get(reqId, (None, None, None))
        if stream_loop is not None and on_error is not None:

            async def _notify_in_loop(
                on_error: Callable[[ProviderException], Awaitable[None]],
                error: ProviderException,
            ) -> None:
                await on_error(error)

            stream_loop.call_soon_threadsafe(
                stream_loop.create_task,
                _notify_in_loop(on_error, error),
            )

        # Determine if error is non-recoverable from detail suffix
        is_non_recoverable = error.code.endswith("_NON_RECOVERABLE")

        # 3. Orphan error - log warning
        if future_loop is None and stream_loop is None:
            logger.error(
                "Orphan TWS error (no future or stream) for reqId %d",
                reqId,
            )
            logger.exception(error)

        elif is_non_recoverable:
            loop = stream_loop or future_loop
            if loop:
                loop.call_soon_threadsafe(self._cleanup_request, reqId)

    # == exposed socket methods ===

    def stream_req_id(self, stream_key: str) -> int | None:
        """Get the reqId for an active stream by ticker name."""
        return self._active_streams.get(stream_key)

    def _pop_stream_req_id(self, stream_key: str) -> int | None:
        """Pop the reqId for an active stream by ticker name."""
        reqId = self._active_streams.pop(stream_key, None)
        if DEBUG_TWS_CALLBACK:
            debug_log(
                f"_pop_stream_req_id for stream_key: {stream_key} => reqId {reqId}"
            )
        return reqId

    def _cleanup_request(self, reqId: int) -> None:
        """Remove all tracking state for a request.

        Cleans up all internal data structures associated with a reqId:
        - Stream data and hooks
        - Future hooks and data
        - Pending snapshots
        - Capability tracking
        - Active stream mapping

        Args:
            reqId: The request ID to clean up
        """
        self._stream_data.pop(reqId, None)
        self._stream_hooks.pop(reqId, None)
        self._future_hooks.pop(reqId, None)
        self._future_data.pop(reqId, None)
        self._snapshot_hooks.pop(reqId, None)
        self._reqId_to_capability.pop(reqId, None)
        # Remove from active streams
        for ticker, rid in list(self._active_streams.items()):
            if rid == reqId:
                self._pop_stream_req_id(ticker)
                break

    def _update_stream_field(
        self,
        reqId: int,
        field_name: str,
        value: float | int | str | Decimal,
        *,
        tolerance: float = 1e-3,
    ) -> dict[str, Any] | None:
        """Update stream field if changed.

        Args:
            reqId: The request ID for the stream
            field_name: The field name to update
            value: The new value
            tolerance: Absolute tolerance for float comparisons (default 1e-3)

        Returns:
            True if the field was updated, False if stream not found or value unchanged.
        """
        stream = self._stream_data.get(reqId)
        if stream is None:
            return None
        current = stream.get(field_name)
        if current is not None:
            # For numeric types, use tolerance-based comparison
            if isinstance(value, (float, int, Decimal)) and isinstance(
                current, (float, int, Decimal)
            ):
                if math.isclose(float(current), float(value), abs_tol=tolerance):
                    return None
            # For strings and exact matches
            elif current == value:
                return None
        stream[field_name] = value
        return stream

    @property
    def server_version(self) -> str:
        return self._server_version

    @property
    def connection_time(self) -> str:
        return self._connection_time

    @property
    def account_id(self) -> str:
        return next(iter(self._reader_accounts), "Not set")

    @property
    def next_req_id(self) -> int:
        return next(self._req_id_counter)

    @property
    def next_order_id(self) -> int:
        """Get next valid order ID (auto-increments).

        Returns the current _nxt_order_id and increments it for the next call.
        Raises AssertionError if connection not yet ready (nextValidId not received).
        """
        assert self._nxt_order_id is not None, "nextValidId not yet received from TWS"
        order_id = self._nxt_order_id
        self._nxt_order_id += 1
        return order_id

    @property
    def running(self) -> bool:
        return self._state == IBSocketState.RUNNING

    def connect(
        self,
        host: str,
        port: int,
        client_id: int,
        block_interval: float = 0.01,
    ) -> None:
        assert self._state == IBSocketState.READY, "Socket already used!"

        self._state = IBSocketState.CONNECTING
        nb_retries = 3
        while nb_retries > 0:
            try:
                with self._socket_lock:
                    self._socket.connect((host, port))
                    self._socket.settimeout(block_interval)
                break
            except Exception:
                nb_retries -= 1
                time.sleep(0.1)

        if nb_retries == 0:
            self._state = IBSocketState.ERROR
            raise ConnectionError(f"Failed to connect to TWS at {host}:{port}")

        debug_log(f"Socket connected: {self._socket.getpeername()}")

        # Send initial handshake message
        v100version = "v%d..%d" % (MIN_CLIENT_VER, MAX_CLIENT_VER)
        msg_content = len(v100version).to_bytes(4, "big") + v100version.encode()
        message = str.encode("API\0", "ascii") + msg_content
        with self._socket_lock:
            self._socket.sendall(message)
        if DEBUG_TWS_SEND:
            debug_log(f"Sent initial message: {str(message)}")
        nb_retries = 10
        data: bytes = b""
        while nb_retries > 0:
            try:
                data = self._socket.recv(4096)
                break
            except socketTimeout:
                nb_retries -= 1
                time.sleep(0.1)

        if nb_retries == 0:
            self._state = IBSocketState.ERROR
            raise ConnectionError("Error while waiting for handshake response")

        buf_size = len(data)
        msg_size = HEADER_STRUCT.unpack_from(data, 0)[0]
        if DEBUG_TWS_RECEIVE:
            debug_log(f"Received handshake data: {str(data)}")

        if buf_size < msg_size + 4:
            self._state = IBSocketState.ERROR
            raise ConnectionError(
                f"Handshake response incomplete: expected {msg_size + 4} bytes, got {buf_size} bytes"
            )

        fields = [chunk for chunk in data[4 : 4 + msg_size].split(NULL) if chunk]
        if len(fields) != 2:
            self._state = IBSocketState.ERROR
            raise ConnectionError(
                f"Invalid handshake response: expected 2 fields, got {len(fields)}"
            )

        self._server_version, self._connection_time = [
            msg.decode("ascii") for msg in fields
        ]
        debug_log(
            f"Server version: {self._server_version}, Connection time: {self._connection_time}"
        )
        text = make_fields([VERSION, client_id, ""])
        msg2 = (
            (len(text) + 4).to_bytes(4, "big") + OUT.START_API.to_bytes(4, "big") + text
        )
        with self._socket_lock:
            self._socket.sendall(msg2)
        debug_log("IBSocket connection successfully.")

        self._state = IBSocketState.CONNECTED
        threading.Thread(
            target=self._reader_task,
            args=(int(self._server_version),),
            daemon=False,
        ).start()

    def disconnect(self) -> None:
        try:
            with self._socket_lock:
                self._socket.close()
        finally:
            with self._socket_lock:
                self._state = IBSocketState.CLOSED

    def send_message(self, msgId: int, values: list[object]) -> None:
        text = make_fields(values)
        msg2 = (len(text) + 4).to_bytes(4, "big") + msgId.to_bytes(4, "big") + text
        if DEBUG_TWS_SEND:
            debug_log(f"Sending message: {str(msg2)}")
        assert self._state == IBSocketState.RUNNING, "Socket is not connected."
        with self._socket_lock:
            self._socket.sendall(msg2)

    def send_message_proto(self, msgId: int, protobuf_data: bytes) -> None:
        """Send a protobuf-encoded message.

        For server version >= 203, certain messages (PLACE_ORDER, CANCEL_ORDER)
        require protobuf encoding.

        Message format: [4-byte length][4-byte msgId][protobuf bytes]
        """
        byte_array = msgId.to_bytes(4, "big") + protobuf_data
        msg = len(byte_array).to_bytes(4, "big") + byte_array
        if DEBUG_TWS_SEND:
            debug_log(
                f"Sending protobuf message: msgId={msgId}, size={len(protobuf_data)}"
            )
        assert self._state == IBSocketState.RUNNING, "Socket is not connected."
        with self._socket_lock:
            self._socket.sendall(msg)

    # === Future / Coroutine management ===

    # called in reader thread
    def _resolve_future(self, reqId: int) -> None:
        """Helper to resolve a future in the asyncio loop."""

        loop, _ = self._future_hooks.get(reqId, (None, None))
        if loop is None:
            logger.warning(f"loop not found or already done for reqId {reqId}.")
            return

        def resolve_in_loop(reqId: int) -> None:
            result = self._future_data.pop(reqId, None)
            assert result is not None, "No results found in future resolver."
            _, future = self._future_hooks.pop(reqId, (None, None))
            assert (
                future is not None and not future.done()
            ), "Future missing or already done in resolver."
            future.set_result(result)
            self._reqId_to_capability.pop(reqId, None)

        loop.call_soon_threadsafe(resolve_in_loop, reqId)

    # =======================

    def create_future(
        self, reqId: int, *, capability: str, timeout: float | None = 5
    ) -> Awaitable[Any]:
        """Create a new Future attached to the current event loop."""
        loop = asyncio.get_event_loop()
        future: asyncio.Future[Any] = loop.create_future()
        self._future_hooks[reqId] = (loop, future)
        self._future_data[reqId] = []
        self._reqId_to_capability[reqId] = capability
        return asyncio.wait_for(future, timeout)

    def create_snapshot(
        self,
        reqId: int,
        ticker_name: str,
        *,
        capability: str,
        timeout: float | None = 5,
    ) -> Awaitable[Any]:
        """Create a new Future for quote snapshot resolution.

        Uses _pending_snapshots to track snapshot futures separately from
        _future_hooks (which are used for request-response patterns like
        contractDetails).

        Args:
            reqId: Request ID for the market data request
            ticker_name: Ticker name for the stream
            capability: Provider capability for error routing
            timeout: Timeout in seconds (default 5)

        Returns:
            Awaitable that resolves with the stream data when bid/ask/last complete.
        """
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        self._snapshot_hooks.setdefault(reqId, []).append((loop, future))
        self._reqId_to_capability.setdefault(reqId, capability)
        stream = self._stream_data.setdefault(
            reqId,
            {
                "reqId": reqId,
                "ticker_name": ticker_name,
            },
        )
        # If stream already has all required fields, resolve immediately
        if stream.get("snapshot_complete", False):
            future.set_result(stream)
        return asyncio.wait_for(future, timeout)

    # === Stream management ===

    def _resolve_snapshots(
        self, reqId: int, stream: dict[str, Any]
    ) -> list[tuple[asyncio.AbstractEventLoop, asyncio.Future[Any]]]:
        """Try to resolve pending snapshot futures if bid/ask/last complete.

        Called from tick callbacks when data is updated. Checks if the stream
        has all required quote fields and resolves the pending snapshot future
        if so.

        Args:
            reqId: Request ID for the stream
            stream: Stream data dictionary

        Returns:
            The event loop used for resolution, or None if no snapshot was resolved.
        """

        if not stream.get("snapshot_complete"):
            return []

        snapshot_hooks = self._snapshot_hooks.pop(reqId, None)
        if not snapshot_hooks:
            return []

        if DEBUG_TWS_CALLBACK:
            debug_log(
                "_try_resolve_snapshots resolving "
                + f"[{stream.get('ticker_name', 'UNKNOWN')}]"
                + f" [reqId {reqId}]"
            )

        for loop, future in snapshot_hooks:
            if not future.done():
                loop.call_soon_threadsafe(future.set_result, stream)

        # No stream hook - clean up if snapshot was resolved
        if reqId not in self._stream_hooks:
            loop, _ = next(iter(snapshot_hooks))

            if DEBUG_TWS_CALLBACK:
                debug_log(
                    "_notify_stream cleaning up after snapshot resolution "
                    + f"[{stream.get('ticker_name', 'UNKNOWN')}]"
                    + f" [reqId {reqId}]"
                )
            loop.call_soon_threadsafe(self._cleanup_request, reqId)
        return snapshot_hooks

    def _dispatch_update(
        self, reqId: int, stream: dict[str, Any], updated_fields: list[str]
    ) -> (
        tuple[
            asyncio.AbstractEventLoop,
            Callable[
                [dict[str, Any], list[str]],
                Awaitable[None],
            ],
            Callable[[ProviderException], Awaitable[None]] | None,
        ]
        | None
    ):
        """Dispatch stream update to registered callback.

        Args:
            reqId: Request ID for the stream
            stream: Stream data dictionary
            updated_fields: List of field names that were updated

        Returns:
            True if update was dispatched, False if no stream hook exists.
        """
        stream_hook = self._stream_hooks.get(reqId)
        if stream_hook is None:
            return None

        stream_loop, stream_callback, _ = stream_hook

        if DEBUG_TWS_CALLBACK:
            debug_log(
                f"_dispatch_stream_update [{stream.get('ticker_name', 'UNKNOWN')}]"
                + f" with fields: {updated_fields}"
            )

        stream_loop.call_soon_threadsafe(
            stream_loop.create_task,  # type: ignore
            stream_callback(stream, updated_fields),  # type: ignore
        )
        return stream_hook

    def _notify_stream(
        self,
        reqId: int,
        stream: dict[str, Any],
        updated_fields: list[str],
    ) -> None:
        """Trigger stream callbacks if registered.

        Handles both snapshot resolution and continuous stream updates:
        1. Try to resolve pending snapshots (if bid/ask/last complete)
        2. Dispatch to stream callback if registered
        3. Clean up if snapshot-only (no stream hook)
        """
        # TODO: add rate limiting

        # Dispatch to stream callback
        self._dispatch_update(reqId, stream, updated_fields)

        # Try to resolve pending snapshots
        self._resolve_snapshots(reqId, stream)

    # =======================

    def register_stream(
        self,
        reqId: int,
        ticker_name: str,
        callback: Callable[
            [dict[str, Any], list[str]],
            Awaitable[None],
        ],
        capability: str,
        on_error: Callable[[ProviderException], Awaitable[None]] | None = None,
    ) -> None:
        """Create and register a new stream slot for a reqId.

        Args:
            reqId: Request ID for the stream
            ticker_name: Human-readable ticker_name
            callback: Callback for data updates (receives stream dict and updated fields)
            capability: Capability name for error routing
            on_error: Optional callback for streaming errors (receives ProviderException)
        """
        # main thread ownership
        self._stream_hooks[reqId] = (
            asyncio.get_event_loop(),
            callback,
            on_error,
        )
        # assert self._reader_loop is not None, "Reader loop not initialized."
        # self._reader_loop.call_soon_threadsafe(
        #     self._register_stream, reqId, ticker_name
        # )
        self._stream_data[reqId] = {
            "reqId": reqId,
            "ticker_name": ticker_name,
        }
        self._reqId_to_capability[reqId] = capability
        self._active_streams[ticker_name] = reqId

    def update_stream(
        self,
        reqId: int,
        callback: Callable[
            [dict[str, Any], list[str]],
            Awaitable[None],
        ],
        on_error: Callable[[ProviderException], Awaitable[None]] | None = None,
    ) -> None:
        """Update stream callbacks for an existing reqId.

        Args:
            reqId: Request ID for the stream
            callback: New callback for data updates
            on_error: Optional new callback for streaming errors
        """
        # main thread ownership
        self._stream_hooks[reqId] = (
            asyncio.get_event_loop(),
            callback,
            on_error,
        )

    def unregister_stream(self, reqId: int) -> None:
        """Remove stream slot slot and associated reqIds."""
        self._cleanup_request(reqId)

    # ================================================
    # == Dispatch handlers for subscription events ===
    # ================================================

    # === Trading / account management ===

    def managedAccounts(self, accountsList: str) -> None:
        if DEBUG_TWS_BROKER:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")
        # should be sent upon connection
        self._reader_accounts = accountsList.split(",")

    def nextValidId(self, orderId: int) -> None:
        if DEBUG_TWS_BROKER:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")
        # Signals connection fully established - safe to make requests
        self._nxt_order_id = orderId
        self._ready_event.set()

    # === Order callbacks (broker capability) ===

    def openOrder(
        self, orderId: int, contract: Contract, order: Order, orderState: OrderState
    ) -> None:
        """Callback for open order information.

        TWS sends this callback for:
        1. Each open order after reqOpenOrders() is called
        2. Real-time updates when orders are placed/modified

        The callback provides complete order info including contract, order params,
        and current state. Raw TWS objects are stored in OrderTracker without
        transformation. Domain conversion happens at broker_provider level.

        Args:
            orderId: TWS order ID
            contract: Contract the order is for
            order: Order parameters (type, qty, price, etc.)
            orderState: Current order state (status, margin, commission)
        """
        if DEBUG_TWS_BROKER:
            debug_log(
                f"{current_fn_name()}, orderId={orderId}, "
                f"symbol={contract.symbol}, status={orderState.status}"
            )

        # Store raw TWS objects in OrderTracker
        tracked = self._order_tracker.upsert_order(orderId, contract, order, orderState)

        # Dispatch to streaming callback if registered
        self._order_tracker.dispatch_update(tracked)

    def orderStatus(
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
        """Callback for order status updates.

        This callback fires whenever an order's status changes. Updates the
        TrackedOrder's Order and OrderState objects directly and appends an
        OrderFill record for fill history. May be called multiple times for
        the same order as it progresses through its lifecycle.

        Args:
            orderId: TWS order ID
            status: Order status (Submitted, Filled, Cancelled, etc.)
            filled: Quantity that has been filled
            remaining: Quantity still remaining
            avgFillPrice: Average fill price
            permId: Permanent order ID (persists across sessions)
            parentId: Parent order ID (for bracket orders)
            lastFillPrice: Price of last fill
            clientId: Client ID that placed the order
            whyHeld: Reason order is held (if applicable)
            mktCapPrice: Market cap price (for auction orders)
        """
        if DEBUG_TWS_BROKER:
            debug_log(
                f"{current_fn_name()}, orderId={orderId}, status={status}, "
                f"filled={filled}, remaining={remaining}, avgFillPrice={avgFillPrice}"
            )

        # Update TrackedOrder (mutates Order/OrderState, appends OrderFill)
        tracked = self._order_tracker.update_status(
            orderId,
            status,
            filled,
            remaining,
            avgFillPrice,
            permId,
            parentId,
            lastFillPrice,
            clientId,
            whyHeld,
            mktCapPrice,
        )

        # Dispatch to streaming callback if registered
        if tracked is not None:
            self._order_tracker.dispatch_update(tracked)

    def openOrderEnd(self) -> None:
        """End signal for open orders request.

        Called after all openOrder callbacks for reqOpenOrders().
        Marks snapshot as complete and resolves pending futures.
        """
        if DEBUG_TWS_BROKER:
            debug_log(f"{current_fn_name()}")

        # Mark snapshot complete and resolve pending futures
        self._order_tracker.mark_snapshot_complete()
        self._order_tracker.resolve_snapshots()

    # === Position callbacks (broker capability) ===

    def position(
        self, account: str, contract: Contract, position: Decimal, avgCost: float
    ) -> None:
        """Callback for position information.

        TWS sends this callback for:
        1. Each position after reqPositions() is called
        2. Real-time updates when positions change (if subscribed)

        Args:
            account: Account ID holding the position
            contract: Contract the position is for
            position: Position size (positive=long, negative=short)
            avgCost: Average cost per unit
        """
        if DEBUG_TWS_BROKER:
            debug_log(
                f"{current_fn_name()}, account={account}, "
                f"symbol={contract.symbol}, position={position}, avgCost={avgCost}"
            )

        # Build position data dict for domain conversion
        position_data: dict[str, Any] = {
            "account": account,
            "contract": contract,
            "position": position,
            "avgCost": avgCost,
            # Flatten commonly needed fields
            "symbol": contract.symbol,
            "exchange": contract.primaryExchange or contract.exchange,
            "secType": contract.secType,
            "conId": contract.conId,
            "currency": contract.currency,
        }

        # Accumulate positions by account
        if account not in self._position_data:
            self._position_data[account] = []
        self._position_data[account].append(position_data)

        # Dispatch to streaming callback if registered
        if self._position_hooks is not None:
            loop, callback, _ = self._position_hooks

            async def _notify(
                cb: Callable[[dict[str, Any]], Awaitable[None]], data: dict[str, Any]
            ) -> None:
                await cb(data)

            loop.call_soon_threadsafe(
                loop.create_task, _notify(callback, position_data)
            )

    def positionEnd(self) -> None:
        """End signal for positions request.

        Called after all position callbacks for reqPositions().
        Resolves the pending future with accumulated position data.
        """
        if DEBUG_TWS_BROKER:
            debug_log(f"{current_fn_name()}")

        # Resolve the pending positions future
        if self._positions_future is not None:
            loop, future = self._positions_future

            def resolve(
                fut: asyncio.Future[list[dict[str, Any]]],
                positions: list[dict[str, Any]],
            ) -> None:
                if not fut.done():
                    fut.set_result(positions)

            # Flatten all positions from all accounts
            all_positions: list[dict[str, Any]] = []
            for account_positions in self._position_data.values():
                all_positions.extend(account_positions)
            loop.call_soon_threadsafe(resolve, future, all_positions)
            self._positions_future = None

    # === Account Summary callbacks (broker capability) ===

    def accountSummary(
        self, reqId: int, account: str, tag: str, value: str, currency: str
    ) -> None:
        """Callback for account summary information.

        TWS sends this callback for each requested tag after reqAccountSummary().

        Args:
            reqId: Request ID
            account: Account ID
            tag: Tag name (e.g., "NetLiquidation", "TotalCashValue")
            value: Tag value as string
            currency: Currency of the value
        """
        if DEBUG_TWS_BROKER:
            debug_log(
                f"{current_fn_name()}, reqId={reqId}, account={account}, "
                f"tag={tag}, value={value}, currency={currency}"
            )

        # Initialize data structure for this reqId if needed
        stream = self._stream_data.get(reqId)
        assert stream is not None, "Stream data not initialized for accountSummary."

        account_data = stream.setdefault(account, {})

        # Store tag value (keyed by tag name)
        account_data[tag] = {
            "account": account,
            "tag": tag,
            "value": value,
            "currency": currency,
        }

    def accountSummaryEnd(self, reqId: int) -> None:
        """End signal for account summary request.

        Called after all accountSummary callbacks for reqAccountSummary().
        Resolves the pending future with accumulated summary data.
        """
        if DEBUG_TWS_BROKER:
            debug_log(f"{current_fn_name()}, reqId={reqId}")

        # snapshot future resolution (uses _pending_snapshots)
        stream = self._stream_data.get(reqId)
        assert stream is not None, "Stream data not initialized for accountSummaryEnd."
        stream["snapshot_complete"] = True

        self._resolve_snapshots(reqId, stream)

        # # Dispatch to stream callback
        # if self._dispatch_update(reqId, stream, ["snapshot_complete"]) is not None:
        #     return

        # if snapshot_loop is not None:
        #     if DEBUG_TWS_DATAFEED:
        #         debug_log(f"tickSnapshotEnd cleanup stream for reqId {reqId}")

        #     snapshot_loop.call_soon_threadsafe(self._cleanup_request, reqId)

    # === symbolSamples ===

    @error_handler(capability="shared")
    def symbolSamples(
        self, reqId: int, contractDescriptions: list[ContractDescription]
    ) -> None:
        if DEBUG_TWS_CALLBACK:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")
        accumulator = self._future_data.get(reqId)
        if isinstance(accumulator, list):
            accumulator.extend(contractDescriptions)
            self._resolve_future(reqId)

    # === contractDetails (streaming accumulation pattern) ===

    @error_handler(capability="shared")
    def contractDetails(self, reqId: int, contractDetails: ContractDetails) -> None:
        """Accumulate contract details (may be called multiple times).

        TWS sends one contractDetails callback per matching contract.
        Results are accumulated until contractDetailsEnd is called.
        """
        if DEBUG_TWS_CALLBACK:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")
        accumulator = self._future_data.get(reqId)
        if isinstance(accumulator, list):
            accumulator.append(contractDetails)

    @error_handler(capability="shared")
    def contractDetailsEnd(self, reqId: int) -> None:
        """End signal for contract details - resolve Future with accumulated results."""
        if DEBUG_TWS_CALLBACK:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")
        self._resolve_future(reqId)

    # === historicalData (streaming accumulation pattern) ===

    @error_handler(capability="datafeed")
    def historicalData(self, reqId: int, bar: BarData) -> None:
        """Accumulate historical bars (may be called multiple times).

        TWS sends one historicalData callback per bar.
        Results are accumulated until historicalDataEnd is called.
        """
        # TODO: there is a streaming opportunity here to dispatch bars as they arrive
        if DEBUG_TWS_DATAFEED:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")
        accumulator = self._future_data.get(reqId)
        if accumulator is not None:
            accumulator.append(bar)
        elif reqId not in self._stream_data:
            debug_log(f"No accumulator found for reqId {reqId}")

    @error_handler(capability="datafeed")
    def historicalDataUpdate(self, reqId: int, bar: BarData) -> None:
        """Returns updates in real time when keepUpToDate is set to True."""

        # Field mapping: (stream_attr, bar_attr, transform)
        field_mappings: list[tuple[str, float | int | str | Decimal]] = [
            ("bar_date", bar.date),
            ("bar_open", bar.open),
            ("bar_high", bar.high),
            ("bar_low", bar.low),
            ("bar_close", bar.close),
            ("bar_volume", int(bar.volume)),
            ("bar_wap", float(bar.wap)),
            ("bar_count", bar.barCount),
        ]

        stream: dict[str, float | int | str | Decimal] | None = None
        updated_fields: list[str] = []
        for field_name, new_value in field_mappings:
            _stream = self._update_stream_field(reqId, field_name, new_value)
            if _stream:
                stream = _stream
                updated_fields.append(field_name)

        # Only notify if at least one field changed
        if stream:
            self._notify_stream(reqId, stream, updated_fields)

    @error_handler(capability="datafeed")
    def historicalDataEnd(self, reqId: int, start: str, end: str) -> None:
        """End signal for historical data - resolve Future with accumulated results."""
        if DEBUG_TWS_DATAFEED:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")

        # Snapshot future resolution (uses _pending_snapshots)
        stream = self._update_stream_field(reqId, "snapshot_complete", True)
        if stream:
            self._notify_stream(reqId, stream, ["snapshot_complete"])

        if reqId in self._future_data:
            self._resolve_future(reqId)

    # === Market data (accumulation pattern) ===

    @error_handler(capability="datafeed")
    def tickPrice(
        self, reqId: int, tickType: int, price: float, attrib: TickAttrib
    ) -> None:
        """Accumulate price ticks for market data snapshot."""
        tick_name = get_tick_type_name(tickType)
        field_name = TICK_TYPE_TO_FIELD.get(tick_name)  # type: ignore[arg-type]
        if field_name is None:
            return
        stream = self._update_stream_field(reqId, field_name, price)
        if stream:
            fields = [field_name]
            # Also update bar_close for last/close prices
            if field_name in ["last", "close"]:
                self._update_stream_field(reqId, "bar_close", price)
                fields.append("bar_close")
            if not stream.get("snapshot_complete"):
                stream["snapshot_complete"] = all(
                    att in stream for att in ["bid", "ask", "last"]
                )
            self._notify_stream(reqId, stream, fields)

    @error_handler(capability="datafeed")
    def tickSize(self, reqId: int, tickType: int, size: Decimal) -> None:
        """Accumulate size ticks for market data snapshot."""
        tick_name = get_tick_type_name(tickType)
        field_name = TICK_TYPE_TO_FIELD.get(tick_name)  # type: ignore[arg-type]
        if field_name is None:
            return
        stream = self._update_stream_field(reqId, field_name, size)
        if stream:
            self._notify_stream(reqId, stream, [field_name])

    @error_handler(capability="datafeed")
    def marketDataType(self, reqId: int, marketDataType: int) -> None:
        """Set market data type for the request."""
        stream = self._update_stream_field(reqId, "market_data_type", marketDataType)
        if stream:
            self._notify_stream(reqId, stream, ["market_data_type"])

    @error_handler(capability="datafeed")
    def tickReqParams(
        self, tickerId: int, minTick: float, bboExchange: str, snapshotPermissions: int
    ) -> None:
        """Returns exchange map of a particular contract."""
        # FIXME: suboptimal performance - need to hardcode field updates
        # to avoid multiples collections and dict creations
        update_list: list[str] = []
        stream: dict[str, Any] | None = None
        data: dict[str, float | int | str | Decimal] = {
            "min_tick": minTick,
            "bbo_exchange": bboExchange,
            "snapshot_permissions": snapshotPermissions,
        }
        for field_name, field_value in data.items():
            _stream = self._update_stream_field(tickerId, field_name, field_value)
            if _stream:
                update_list.append(field_name)
                stream = _stream or stream

        if stream:
            self._notify_stream(tickerId, stream, update_list)

    @error_handler(capability="datafeed")
    def tickString(self, reqId: int, tickType: int, value: str) -> None:
        """Generic string tick for market data snapshot."""
        tick_name = get_tick_type_name(tickType)
        field_name = TICK_TYPE_TO_FIELD.get(tick_name)  # type: ignore[arg-type]
        if field_name is None:
            return
        stream = self._update_stream_field(reqId, field_name, value)
        if stream:
            self._notify_stream(reqId, stream, [field_name])

    @error_handler(capability="datafeed")
    def tickGeneric(self, reqId: int, tickType: int, value: float) -> None:
        """Generic float tick for market data snapshot."""
        tick_name = get_tick_type_name(tickType)
        field_name = TICK_TYPE_TO_FIELD.get(tick_name)  # type: ignore[arg-type]
        if field_name is None:
            return
        stream = self._update_stream_field(reqId, field_name, value)
        if stream:
            self._notify_stream(reqId, stream, [field_name])

    @error_handler(capability="datafeed")
    def tickSnapshotEnd(self, reqId: int) -> None:
        """When requesting market data snapshots, this market will indicate the
        snapshot reception is finished."""

        # Snapshot future resolution (uses _pending_snapshots)
        stream = self._update_stream_field(reqId, "snapshot_complete", True)
        if stream:
            self._notify_stream(reqId, stream, ["snapshot_complete"])

    # === error handling ===

    def error(
        self,
        reqId: int,
        errorTime: int,
        errorCode: int,
        errorString: str,
        advancedOrderRejectJson: str = "",
    ) -> None:
        """Error callback from TWS API - routes through centralized error handling.

        Args:
            reqId: Request ID (-1 for system-wide errors)
            errorTime: Unix timestamp of error
            errorCode: TWS error code (e.g., 10187, 200, etc.)
            errorString: Error message from TWS
            advancedOrderRejectJson: Advanced order reject details (optional)
        """
        # Classify error by category and recoverability
        category, recoverable = classify_error(errorCode)

        # Handle system-wide errors (reqId=-1) separately
        if reqId == NO_VALID_ID:
            log_fn = logger.info if recoverable else logger.error
            log_fn(
                f"TWS system {category} [code={errorCode}, recoverable={recoverable}]: {errorString}"
            )
            return

        # Build message with optional advanced order info
        message = errorString
        if advancedOrderRejectJson:
            message = f"{errorString} | {advancedOrderRejectJson}"

        # Create standardized error and route through centralized handler
        # Detail format: {category}_{code} or {category}_{code}_NON_RECOVERABLE
        detail = (
            f"{category}_{errorCode}"
            if recoverable
            else f"{category}_{errorCode}_NON_RECOVERABLE"
        )
        self._handle_request_error(
            category=TWSErrorCategory.API,
            detail=detail,
            reqId=reqId,
            message=message,
            timestamp=errorTime // 1000 if errorTime > 10_000_000_000 else errorTime,
        )

    def errorProtoBuf(self, errorMessageProto: ErrorMessageProto) -> None:
        """Error callback using protobuf format (newer TWS API versions).

        Args:
            errorMessageProto: ErrorMessage protobuf object
        """
        # Extract fields from protobuf
        reqId = errorMessageProto.id if errorMessageProto.HasField("id") else -1
        errorCode = (
            errorMessageProto.errorCode
            if errorMessageProto.HasField("errorCode")
            else 0
        )
        errorMsg = (
            errorMessageProto.errorMsg if errorMessageProto.HasField("errorMsg") else ""
        )
        errorTime = (
            errorMessageProto.errorTime
            if errorMessageProto.HasField("errorTime")
            else 0
        )
        advancedOrderRejectJson = (
            errorMessageProto.advancedOrderRejectJson
            if errorMessageProto.HasField("advancedOrderRejectJson")
            else ""
        )

        # Delegate to standard error() method
        self.error(reqId, errorTime, errorCode, errorMsg, advancedOrderRejectJson)


class TWSClient:
    def __init__(
        self,
        host: str,
        port: int,
        client_id: int,
        *,
        timeout: float = 10.0,
    ) -> None:
        """Initialize IBSocket (pure callback handler).

        Note: No EClient instance - caller must provide via composition.
        """
        self._host = host
        self._port = port
        self._client_id = client_id
        self._timeout = timeout

        self.__ibsocket = IBSocket()

    @property
    def ibsocket(self) -> IBSocket:
        if not self.__ibsocket.running:
            self.__ibsocket.disconnect()
            self.__ibsocket = IBSocket()
            self.__ibsocket.connect(
                host=self._host,
                port=self._port,
                client_id=self._client_id,
            )
            # Wait for nextValidId signal (connection fully ready)
            if not self.__ibsocket._ready_event.wait(timeout=self._timeout):
                raise TimeoutError("Timeout waiting for TWS connection ready signal")
        return self.__ibsocket

    @property
    def next_req_id(self) -> int:
        return self.ibsocket.next_req_id

    async def reqMatchingSymbols(
        self, pattern: str, timeout: float | None = None
    ) -> list[ContractDescription]:
        reqId = self.next_req_id

        coroutine: Awaitable[list[ContractDescription]] = self.ibsocket.create_future(
            reqId, timeout=timeout or self._timeout, capability="shared"
        )
        self.ibsocket.send_message(OUT.REQ_MATCHING_SYMBOLS, [reqId, pattern])
        debug_log(f"awaiting symbolSamples for reqId {reqId} and pattern '{pattern}'")

        return await coroutine

    async def reqContractDetails(
        self, contract: Contract, timeout: float | None = None
    ) -> list[ContractDetails]:
        """Request contract details for a symbol.

        Args:
            contract: TWS Contract object specifying symbol, secType, exchange, etc.

        Returns:
            List of ContractDetails matching the contract specification.
            May return multiple results for ambiguous queries.
        """
        reqId = self.next_req_id
        coroutine: Awaitable[list[ContractDetails]] = self.ibsocket.create_future(
            reqId, timeout=timeout or self._timeout, capability="shared"
        )

        # Build message fields (VERSION=8 per ibapi/client.py)
        VERSION = 8
        fields: list[object] = [
            VERSION,
            reqId,
            contract.conId,
            contract.symbol,
            contract.secType,
            contract.lastTradeDateOrContractMonth,
            contract.strike if contract.strike else "",
            contract.right,
            contract.multiplier,
            contract.exchange,
            contract.primaryExchange,
            contract.currency,
            contract.localSymbol,
            contract.tradingClass,
            contract.includeExpired,
            contract.secIdType,
            contract.secId,
            contract.issuerId,
        ]

        self.ibsocket.send_message(OUT.REQ_CONTRACT_DATA, fields)
        if DEBUG_TWS_REQUEST:
            debug_log(
                f"awaiting contractDetails for reqId {reqId} and symbol '{contract.symbol}'"
            )
        return await coroutine

    async def reqHistoricalData(
        self,
        contract: Contract,
        end_date_time: str,
        duration_str: str,
        bar_size: str,
        useRTH: int = 0,
        format_date: int = 1,
        keepUpToDate: int = 0,
        timeout: float | None = None,
    ) -> list[BarData]:
        """Request historical bars from TWS.

        Args:
            contract: TWS Contract object
            end_date_time: End datetime ("20231215 16:00:00" or "" for now)
            duration_str: Time range ("1 D", "2 W", "1 M", etc.)
            bar_size: Bar size ("1 min", "5 mins", "1 hour", "1 day")
            whatToShow: Data type (default: "TRADES")
            useRTH: 1=regular hours only, 0=all hours (default: 1)
            format_date: 1=string format, 2=epoch (default: 1)

        Returns:
            List of BarData objects (one per bar, in ascending time order)
        """
        reqId = self.next_req_id
        coroutine: Awaitable[list[BarData]] = self.ibsocket.create_future(
            reqId,
            timeout=timeout or self._timeout,
            capability="datafeed",
        )

        asset_config = get_asset_config(contract.secType)

        # Select whatToShow based on keepUpToDate:
        # - keepUpToDate=True (live): Only TRADES, MIDPOINT, BID, ASK supported
        # - keepUpToDate=False (historical): All types per product supported
        whatToShow = (
            asset_config.what_to_show_live
            if keepUpToDate
            else asset_config.what_to_show_hist
        )

        # Build message fields (VERSION=6 per ibapi/client.py)
        fields: list[object] = [
            reqId,
            contract.conId,
            contract.symbol,
            contract.secType,
            contract.lastTradeDateOrContractMonth,
            contract.strike if contract.strike else "",
            contract.right,
            contract.multiplier,
            contract.exchange,
            contract.primaryExchange,
            contract.currency,
            contract.localSymbol,
            contract.tradingClass,
            contract.includeExpired,
            end_date_time,
            bar_size,
            duration_str,
            useRTH,
            whatToShow,
            format_date,
            keepUpToDate,
            [],  # chartOptions (empty list)
        ]

        self.ibsocket.send_message(OUT.REQ_HISTORICAL_DATA, fields)
        if DEBUG_TWS_REQUEST:
            debug_log(
                f"awaiting historicalData for reqId {reqId}, "
                f"symbol='{contract.symbol}', duration='{duration_str}', barSize='{bar_size}'"
            )
        return await coroutine

    async def reqQuoteSnapshot(
        self,
        contract: Contract,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        stream_key = ticker_name(contract)
        coroutine: Awaitable[dict[str, Any]]

        reqId = self.ibsocket.stream_req_id(stream_key)

        if reqId is not None:
            if DEBUG_TWS_REQUEST:
                debug_log(f"reusing active stream '{stream_key}' for reqQuoteSnapshot")
            coroutine = self.ibsocket.create_snapshot(
                reqId,
                stream_key,
                timeout=timeout or self._timeout,
                capability="datafeed",
            )
            return await coroutine

        reqId = self.next_req_id
        coroutine = self.ibsocket.create_snapshot(
            reqId,
            stream_key,
            timeout=timeout or self._timeout,
            capability="datafeed",
        )

        VERSION = 11
        # Build message fields for REQ_MKT_DATA
        mkt_data_fields: list[object] = [
            VERSION,
            reqId,
            contract.conId,
            contract.symbol,
            contract.secType,
            contract.lastTradeDateOrContractMonth,
            contract.strike if contract.strike else "",
            contract.right,
            contract.multiplier,
            contract.exchange,
            contract.primaryExchange,
            contract.currency,
            contract.localSymbol,
            contract.tradingClass,
            0,  # deltaNeutralContract (False = no delta neutral)
            [],  # Asset-type-specific tick list
            1,  # snapshot
            0,  # regulatorySnapshot
            [],  # mktDataOptions (empty list)
        ]

        self.ibsocket.send_message(OUT.REQ_MKT_DATA, mkt_data_fields)

        if DEBUG_TWS_REQUEST:
            debug_log(
                f"awaiting quote snapshot for reqId {reqId}, symbol='{contract.symbol}'"
            )
        return await coroutine

    # === Real-time bar subscriptions (continuous pattern) ===

    def reqBarDataStream(
        self,
        contract: Contract,
        bar_size: str,
        callback: Callable[
            [dict[str, Any], list[str]],
            Awaitable[None],
        ],
        on_error: Callable[[ProviderException], Awaitable[None]] | None = None,
        **kwargs: Any,
    ) -> str:
        """Create a real-time bar data subscription.

        Args:
            contract: TWS Contract for the symbol
            bar_size: Bar size string (e.g., "1 min", "5 mins")
            callback: Callback for bar updates
            on_error: Optional callback for streaming errors
            **kwargs: Additional options

        Returns:
            Stream key (for cancellation)
        """

        stream_key = ticker_name(contract, bar_size)
        reqId = self.ibsocket.stream_req_id(stream_key)

        if reqId is not None:
            logger.warning(f"BarDataStream for '{stream_key}' already active!")
            self.ibsocket.update_stream(reqId, callback, on_error)
            return stream_key

        reqId = self.next_req_id
        self.ibsocket.register_stream(
            reqId,
            stream_key,
            callback,
            capability="datafeed",
            on_error=on_error,
        )

        asset_config = get_asset_config(contract.secType)
        end_date_time: str = ""
        duration_str: str = get_duration_for_bars(bar_size)
        # Use what_to_show_live since keepUpToDate=True (live data)
        whatToShow: str = asset_config.what_to_show_live
        format_date: int = 1
        useRTH: int = 0
        keepUpToDate: int = 1

        bar_data_fields: list[object] = [
            reqId,
            contract.conId,
            contract.symbol,
            contract.secType,
            contract.lastTradeDateOrContractMonth,
            contract.strike if contract.strike else "",
            contract.right,
            contract.multiplier,
            contract.exchange,
            contract.primaryExchange,
            contract.currency,
            contract.localSymbol,
            contract.tradingClass,
            contract.includeExpired,
            end_date_time,
            bar_size,
            duration_str,
            useRTH,
            whatToShow,
            format_date,
            keepUpToDate,  # True for live updates
            [],  # chartOptions (empty list)
        ]

        self.ibsocket.send_message(OUT.REQ_HISTORICAL_DATA, bar_data_fields)
        if DEBUG_TWS_REQUEST:
            debug_log(
                f"subscribed to bar data for reqId {reqId}, "
                f"symbol='{contract.symbol}', duration='{duration_str}', barSize='{bar_size}'"
            )

        return stream_key

    def reqMktDataStream(
        self,
        contract: Contract,
        callback: Callable[
            [dict[str, Any], list[str]],
            Awaitable[None],
        ],
        on_error: Callable[[ProviderException], Awaitable[None]] | None = None,
        **kwargs: Any,
    ) -> str:
        """Create a real-time market data subscription.

        Args:
            contract: TWS Contract for the symbol
            callback: Callback for market data updates
            on_error: Optional callback for streaming errors
            **kwargs: Additional options

        Returns:
            Stream key (for cancellation)
        """

        stream_key = ticker_name(contract)
        reqId = self.ibsocket.stream_req_id(stream_key)
        if reqId is not None:
            logger.warning(f"MktDataStream for '{stream_key}' already active!")
            self.ibsocket.update_stream(reqId, callback, on_error)
            return stream_key

        reqId = self.next_req_id
        self.ibsocket.register_stream(
            reqId,
            stream_key,
            callback,
            capability="datafeed",
            on_error=on_error,
        )

        asset_config = get_asset_config(contract.secType)
        VERSION = 11
        # Build message fields for REQ_MKT_DATA
        mkt_data_fields: list[object] = [
            VERSION,
            reqId,
            contract.conId,
            contract.symbol,
            contract.secType,
            contract.lastTradeDateOrContractMonth,
            contract.strike if contract.strike else "",
            contract.right,
            contract.multiplier,
            contract.exchange,
            contract.primaryExchange,
            contract.currency,
            contract.localSymbol,
            contract.tradingClass,
            0,  # deltaNeutralContract (False = no delta neutral)
            asset_config.generic_tick_list_str,  # Asset-type-specific tick list
            0,  # snapshot
            0,  # regulatorySnapshot
            [],  # mktDataOptions (empty list)
        ]

        self.ibsocket.send_message(OUT.REQ_MKT_DATA, mkt_data_fields)
        if DEBUG_TWS_REQUEST:
            debug_log(
                f"subscribed to realtime reqMktData with reqId {reqId}, symbol='{contract.symbol}'"
            )

        return stream_key

    def cancelBarDataStream(self, stream_key: str) -> None:
        """Cancel a real-time data subscription."""

        reqId = self.ibsocket.stream_req_id(stream_key)
        assert reqId is not None, f"No active stream found for key '{stream_key}'"

        VERSION = 1
        if reqId is not None:
            self.ibsocket.send_message(OUT.CANCEL_HISTORICAL_DATA, [VERSION, reqId])
            if DEBUG_TWS_REQUEST:
                debug_log(f"cancelled realtime bars for reqId {reqId}")

        self.ibsocket.unregister_stream(reqId)

    def cancelMktDataStream(self, stream_key: str) -> None:
        """Cancel a real-time data subscription."""

        reqId = self.ibsocket.stream_req_id(stream_key)
        assert reqId is not None, f"No active stream found for key '{stream_key}'"

        VERSION = 2
        if reqId is not None:
            self.ibsocket.send_message(OUT.CANCEL_MKT_DATA, [VERSION, reqId])
            if DEBUG_TWS_REQUEST:
                debug_log(f"cancelled realtime market data for reqId {reqId}")

        self.ibsocket.unregister_stream(reqId)

    # === Order methods (broker capability) ===

    @property
    def next_order_id(self) -> int:
        """Get next valid order ID from IBSocket."""
        return self.ibsocket.next_order_id

    async def reqOpenOrders(self, timeout: float | None = None) -> list[TrackedOrder]:
        """Request all open orders for this client (snapshot).

        Returns open orders placed from this client. Each order triggers
        openOrder() and orderStatus() callbacks, then openOrderEnd().

        Args:
            timeout: Request timeout in seconds

        Returns:
            List of TrackedOrder objects (one per open order)
        """
        # Reset tracker and register snapshot hook
        loop = asyncio.get_event_loop()
        self.ibsocket._order_tracker.reset()
        future: asyncio.Future[list[TrackedOrder]] = loop.create_future()
        self.ibsocket._order_tracker.register_snapshot_hook(loop, future)

        VERSION = 1
        self.ibsocket.send_message(OUT.REQ_OPEN_ORDERS, [VERSION])

        if DEBUG_TWS_REQUEST:
            debug_log("requesting open orders")

        return await asyncio.wait_for(future, timeout=timeout or self._timeout)

    def placeOrder(self, contract: Contract, order: Order) -> int:
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
        # Allocate order ID internally
        order_id = self.ibsocket.next_order_id

        # Use protobuf encoding for server version >= 203
        proto_msg = createPlaceOrderRequestProto(order_id, contract, order)
        serialized = proto_msg.SerializeToString()
        # Protobuf message ID = OUT.PLACE_ORDER + 200
        proto_msg_id = OUT.PLACE_ORDER + PROTOBUF_MSG_ID
        self.ibsocket.send_message_proto(proto_msg_id, serialized)
        if DEBUG_TWS_REQUEST:
            debug_log(
                f"placed order (protobuf): id={order_id}, symbol={contract.symbol}, "
                f"action={order.action}, qty={order.totalQuantity}, type={order.orderType}"
            )
        return order_id

    def modifyOrder(self, order_id: int, contract: Contract, order: Order) -> None:
        """Modify an existing order via TWS.

        TWS modifies orders by re-submitting with the same order ID.

        Args:
            order_id: Existing order ID to modify
            contract: Contract (must match original order)
            order: Updated order parameters

        Note:
            For server version >= 203, uses protobuf encoding (required by TWS).
        """
        # Use protobuf encoding for server version >= 203
        proto_msg = createPlaceOrderRequestProto(order_id, contract, order)
        serialized = proto_msg.SerializeToString()
        proto_msg_id = OUT.PLACE_ORDER + PROTOBUF_MSG_ID
        self.ibsocket.send_message_proto(proto_msg_id, serialized)
        if DEBUG_TWS_REQUEST:
            debug_log(
                f"modified order (protobuf): id={order_id}, symbol={contract.symbol}, "
                f"action={order.action}, qty={order.totalQuantity}, type={order.orderType}"
            )

    def cancelOrder(self, order_id: int) -> None:
        """Cancel an order via TWS.

        Args:
            order_id: Order ID to cancel
        """
        VERSION = 1
        fields: list[object] = [
            VERSION,
            order_id,
            "",  # manualOrderCancelTime (empty for immediate)
        ]

        self.ibsocket.send_message(OUT.CANCEL_ORDER, fields)
        if DEBUG_TWS_REQUEST:
            debug_log(f"cancelled order: id={order_id}")

    async def placeWhatIfOrder(
        self, contract: Contract, order: Order, timeout: float | None = None
    ) -> TrackedOrder:
        """Place a WhatIf order and wait for margin info response.

        WhatIf orders are simulation-only orders that return margin requirements
        without actually executing. This method handles the one-shot callback
        pattern internally.

        Args:
            contract: Contract to simulate order for
            order: Order with whatIf=True flag set
            timeout: Timeout in seconds (default: self._timeout)

        Returns:
            TrackedOrder with OrderState containing margin info
        """
        loop = asyncio.get_event_loop()
        result_future: asyncio.Future[TrackedOrder] = loop.create_future()

        # Allocate order ID
        order_id = self.ibsocket.next_order_id

        async def capture_response(tracked: TrackedOrder) -> None:
            if tracked.orderId == order_id and not result_future.done():
                result_future.set_result(tracked)

        # Save current hooks and register one-shot callback
        original_hooks = self.ibsocket._order_tracker._stream_hooks
        self.registerOrderCallback(capture_response)

        try:
            # Submit whatif order
            proto_msg = createPlaceOrderRequestProto(order_id, contract, order)
            serialized = proto_msg.SerializeToString()
            proto_msg_id = OUT.PLACE_ORDER + PROTOBUF_MSG_ID
            self.ibsocket.send_message_proto(proto_msg_id, serialized)

            if DEBUG_TWS_REQUEST:
                debug_log(
                    f"placed whatif order (protobuf): id={order_id}, "
                    f"symbol={contract.symbol}"
                )

            return await asyncio.wait_for(
                result_future, timeout=timeout or self._timeout
            )
        finally:
            # Restore original hooks
            self.ibsocket._order_tracker._stream_hooks = original_hooks

    def registerOrderCallback(
        self,
        callback: Callable[[TrackedOrder], Awaitable[None]],
        on_error: Callable[[ProviderException], Awaitable[None]] | None = None,
    ) -> None:
        """Register callback for order updates (subscription mode).

        Args:
            callback: Called for each order update (openOrder/orderStatus)
            on_error: Optional error callback
        """
        loop = asyncio.get_event_loop()
        self.ibsocket._order_tracker.register_order_hook(loop, callback, on_error)

    def unregisterOrderCallback(self) -> None:
        """Unregister order update callback."""
        self.ibsocket._order_tracker.unregister_order_hook()

    # === Position methods (broker capability) ===

    async def reqPositions(self, timeout: float | None = None) -> list[dict[str, Any]]:
        """Request all positions for all accounts.

        Returns positions for all managed accounts. Each position triggers
        position() callback, then positionEnd().

        Args:
            timeout: Request timeout in seconds

        Returns:
            List of position data dicts (one per position)
        """
        # Create future for result
        loop = asyncio.get_event_loop()
        future: asyncio.Future[list[dict[str, Any]]] = loop.create_future()
        self.ibsocket._positions_future = (loop, future)
        self.ibsocket._position_data.clear()  # Clear stale position data

        VERSION = 1
        self.ibsocket.send_message(OUT.REQ_POSITIONS, [VERSION])

        if DEBUG_TWS_REQUEST:
            debug_log("requesting positions")

        return await asyncio.wait_for(future, timeout=timeout or self._timeout)

    def registerPositionCallback(
        self,
        callback: Callable[[dict[str, Any]], Awaitable[None]],
        on_error: Callable[[ProviderException], Awaitable[None]] | None = None,
    ) -> None:
        """Register callback for position updates.

        Args:
            callback: Called for each position update
            on_error: Optional error callback
        """
        loop = asyncio.get_event_loop()
        self.ibsocket._position_hooks = (loop, callback, on_error)

    def unregisterPositionCallback(self) -> None:
        """Unregister position update callback."""
        self.ibsocket._position_hooks = None

    def cancelPositions(self) -> None:
        """Cancel position updates subscription."""
        VERSION = 1
        self.ibsocket.send_message(OUT.CANCEL_POSITIONS, [VERSION])
        if DEBUG_TWS_REQUEST:
            debug_log("cancelled positions subscription")

    # === Account Summary methods (broker capability) ===

    async def reqAccountSummarySnapshot(
        self,
        group: str = "All",
        tags: str = "NetLiquidation,TotalCashValue,BuyingPower",
        timeout: float | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Request account summary for specified tags.

        Args:
            group: Account group ("All" for all accounts)
            tags: Comma-separated list of tags to request
            timeout: Request timeout in seconds

        Returns:
            Dict mapping tag names to their value data

        Available tags:
            AccountType, NetLiquidation, TotalCashValue, SettledCash,
            AccruedCash, BuyingPower, EquityWithLoanValue,
            PreviousEquityWithLoanValue, GrossPositionValue, ReqTEquity,
            ReqTMargin, SMA, InitMarginReq, MaintMarginReq, AvailableFunds,
            ExcessLiquidity, Cushion, FullInitMarginReq, FullMaintMarginReq,
            FullAvailableFunds, FullExcessLiquidity, LookAheadNextChange,
            LookAheadInitMarginReq, LookAheadMaintMarginReq,
            LookAheadAvailableFunds, LookAheadExcessLiquidity,
            HighestSeverity, DayTradesRemaining, Leverage
        """

        stream_key = f"account_summary_{group}_{tags}"
        coroutine: Awaitable[dict[str, Any]]

        reqId = self.ibsocket.stream_req_id(stream_key)

        if reqId is not None:
            if DEBUG_TWS_REQUEST:
                debug_log(f"reusing active stream '{stream_key}' for reqAccountSummary")
            coroutine = self.ibsocket.create_snapshot(
                reqId,
                stream_key,
                timeout=timeout or self._timeout,
                capability="broker",
            )
            return await coroutine

        reqId = self.next_req_id
        coroutine = self.ibsocket.create_snapshot(
            reqId,
            stream_key,
            timeout=timeout or self._timeout,
            capability="broker",
        )

        VERSION = 1
        self.ibsocket.send_message(
            OUT.REQ_ACCOUNT_SUMMARY, [VERSION, reqId, group, tags]
        )

        if DEBUG_TWS_REQUEST:
            debug_log(f"requesting account summary, reqId={reqId}, tags={tags}")

        return await coroutine

    def cancelAccountSummary(self, reqId: int) -> None:
        """Cancel account summary subscription.

        Args:
            reqId: Request ID from reqAccountSummary
        """
        VERSION = 1
        self.ibsocket.send_message(OUT.CANCEL_ACCOUNT_SUMMARY, [VERSION, reqId])
        if DEBUG_TWS_REQUEST:
            debug_log(f"cancelled account summary for reqId={reqId}")

    def shutdown(self) -> None:
        """Shutdown the TWSClient and underlying IBSocket."""
        self.__ibsocket.disconnect()
