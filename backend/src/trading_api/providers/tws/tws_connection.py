"""Pure TWS protocol - synchronous callbacks with zero-copy dispatch.

Layer 1 of TWS integration:
- Pure EWrapper implementation (callbacks only)
- Zero-copy callback dispatch (< 2µs latency target)
- No connection management (handled by TWSProvider)
- No request ID generation (handled by TWSProvider)
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
- Used via composition by TWSProvider
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

from ibapi.common import BarData, TickAttrib
from ibapi.const import DOUBLE_INFINITY, INFINITY_STR, UNSET_DOUBLE, UNSET_INTEGER
from ibapi.contract import Contract, ContractDescription, ContractDetails
from ibapi.decoder import Decoder
from ibapi.message import OUT
from ibapi.protobuf.ErrorMessage_pb2 import ErrorMessage as ErrorMessageProto
from ibapi.ticktype import TickTypeEnum
from ibapi.wrapper import EWrapper, current_fn_name

from trading_api.models.exceptions import ProviderException
from trading_api.providers.tws.tws_mappers import ticker_name

from .tws_models import TICK_TYPE_TO_FIELD, classify_error, get_asset_config

logger = logging.getLogger(__name__)
DEBUG_TWS_REQUEST = os.environ.get("DEBUG_TWS_REQUEST") == "true"
DEBUG_TWS_SEND = os.environ.get("DEBUG_TWS_SEND") == "true"
DEBUG_TWS_RECEIVE = os.environ.get("DEBUG_TWS_RECEIVE") == "true"
DEBUG_TWS_DISPATCH = os.environ.get("DEBUG_TWS_DISPATCH") == "true"
DEBUG_TWS_CALLBACK = os.environ.get("DEBUG_TWS_CALLBACK") == "true"


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


BAR_2_DURATION = {
    "1 secs": 1,
    "5 secs": 5,
    "10 secs": 10,
    "15 secs": 15,
    "30 secs": 30,
    "1 min": 60,
    "2 mins": 120,
    "3 mins": 180,
    "5 mins": 300,
    "10 mins": 600,
    "15 mins": 900,
    "20 mins": 1200,
    "30 mins": 1800,
    "1 hour": 3600,
    "2 hours": 7200,
    "3 hours": 10800,
    "4 hours": 14400,
    "8 hours": 28800,
    "1 day": 86400,
    "1 week": 604800,
    "1 month": 2592000,
}


def get_duration_for_bars(bar_size: str, num_bars: int = 2) -> str:
    """Convert bar size to duration string for N bars."""
    # Map bar size to seconds
    secs = BAR_2_DURATION.get(bar_size, 86400)
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

        # Data tracking attributes
        self._future_data: dict[int, list[Any]] = {}
        self._stream_data: dict[int, dict[str, Any]] = {}
        self._nxt_order_id: int | None = None
        self._reader_accounts: list[str] = []

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
        # Determine if error is non-recoverable from detail suffix
        is_non_recoverable = detail.endswith("_NON_RECOVERABLE")

        error = ProviderException(
            code=f"PROVIDER_TWS_{category}_{detail.upper()}",
            message=f"[reqId={reqId}] {message}",
            provider="tws",
            capability=self._reqId_to_capability.pop(reqId, capability_fallback),
            timestamp=timestamp,
        )

        # 1. Check for pending future
        future_loop, future = self._future_hooks.get(reqId, (None, None))
        if future_loop is not None and future is not None and not future.done():
            future_loop.call_soon_threadsafe(future.set_exception, error)

        # 2. Check for active stream
        stream = self._stream_data.get(reqId)
        stream_loop, _, on_error = self._stream_hooks.get(reqId, (None, None, None))
        if stream_loop is not None and stream is not None and on_error is not None:
            stream_loop.call_soon_threadsafe(stream_loop.create_task, on_error(error))  # type: ignore

        # 3. Log orphan error if neither future nor stream handler exists
        if (future is None or future.done()) and on_error is None:
            logger.warning(f"TWS orphan error [reqId={reqId}]: {error!r}")

        # 4. Cleanup data structures for non-recoverable errors
        if is_non_recoverable:
            # Remove future hooks and data
            self._future_hooks.pop(reqId, None)
            self._future_data.pop(reqId, None)
            # Remove stream hooks and data
            self._stream_hooks.pop(reqId, None)
            self._stream_data.pop(reqId, None)
            # Note: _reqId_to_capability already popped above

    # == exposed socket methods ===

    @property
    def next_req_id(self) -> int:
        return next(self._req_id_counter)

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

        server_version, connection_time = [msg.decode("ascii") for msg in fields]
        debug_log(
            f"Server version: {server_version}, Connection time: {connection_time}"
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
            args=(int(server_version),),
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

    # === Future / Coroutine management ===

    def _resolve_future(self, reqId: int) -> None:
        """Helper to resolve a future in the asyncio loop."""
        results = self._future_data.pop(reqId, [])
        loop, future = self._future_hooks.pop(reqId, (None, None))
        if loop is None or future is None or future.done():
            logger.warning(f"future/loop not found or already done for reqId {reqId}.")
            return
        loop.call_soon_threadsafe(future.set_result, results)

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

    def create_tick_future(
        self,
        reqId: int,
        ticker_name: str,
        *,
        capability: str,
        timeout: float | None = 5,
    ) -> Awaitable[Any]:
        """Create a new Future attached to the current event loop."""
        loop = asyncio.get_event_loop()
        future: asyncio.Future[Any] = loop.create_future()
        self._future_hooks[reqId] = (loop, future)
        self._reqId_to_capability[reqId] = capability
        stream = self._stream_data.setdefault(
            reqId,
            {
                "reqId": reqId,
                "ticker_name": ticker_name,
            },
        )
        if all(att in stream for att in ["bid", "ask", "last"]):
            future.set_result(stream)
        return asyncio.wait_for(future, timeout)

    # === Stream management ===

    def _notify_stream(
        self,
        reqId: int,
        updated_fields: list[str],
    ) -> None:
        """Trigger stream callbacks if registered."""
        # reader thread ownership
        stream = self._stream_data.get(reqId)
        if stream is None:
            debug_log(f"No stream slot found for reqId {reqId}")
            return

        # quote snapshot future resolution workaround
        if all(att in stream for att in ["bid", "ask", "last"]):
            loop, future = self._future_hooks.pop(reqId, (None, None))
            if loop is not None and future is not None and not future.done():
                loop.call_soon_threadsafe(future.set_result, stream)

        loop, callback, _ = self._stream_hooks.get(reqId, (None, None, None))
        if loop is None or callback is None:
            if DEBUG_TWS_CALLBACK:
                debug_log(f"No stream registered for reqId {reqId}")
            return

        # carefull here we are passing stream by reference and will have to prevent mutation issues
        # we do this to avoid model_dump overhead
        if DEBUG_TWS_CALLBACK:
            debug_log(
                f"_notify_stream [{stream.get('ticker_name', 'UNKNOWN')}] with fields: {updated_fields}"
            )
        loop.call_soon_threadsafe(loop.create_task, callback(stream, updated_fields))  # type: ignore

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
        # main thread ownership
        self._stream_hooks.pop(reqId, None)
        # assert self._reader_loop is not None, "Reader loop not initialized."
        # self._reader_loop.call_soon_threadsafe(self._unregister_stream, reqId)
        self._stream_data.pop(reqId, None)
        self._stream_hooks.pop(reqId, (None, None, None))

    # ================================================
    # == Dispatch handlers for subscription events ===
    # ================================================

    # === Trading / account management ===

    def managedAccounts(self, accountsList: str) -> None:
        if DEBUG_TWS_CALLBACK:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")
        # should be sent upon connection
        self._reader_accounts = accountsList.split(",")

    def nextValidId(self, orderId: int) -> None:
        if DEBUG_TWS_CALLBACK:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")
        # Signals connection fully established - safe to make requests
        self._nxt_order_id = orderId
        self._ready_event.set()

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
        if DEBUG_TWS_CALLBACK:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")
        accumulator = self._future_data.get(reqId)
        if isinstance(accumulator, list):
            accumulator.append(bar)
        else:
            debug_log(f"No accumulator found for reqId {reqId}")

    @error_handler(capability="datafeed")
    def historicalDataUpdate(self, reqId: int, bar: BarData) -> None:
        """Returns updates in real time when keepUpToDate is set to True."""
        stream = self._stream_data.get(reqId)
        if stream is None:
            return

        updated_fields: list[str] = []

        # Field mapping: (stream_attr, bar_attr, transform)
        field_mappings: list[tuple[str, object]] = [
            ("bar_date", bar.date),
            ("bar_open", bar.open),
            ("bar_high", bar.high),
            ("bar_low", bar.low),
            ("bar_close", bar.close),
            ("bar_volume", int(bar.volume)),
            ("bar_wap", float(bar.wap)),
            ("bar_count", bar.barCount),
        ]

        for field_name, new_value in field_mappings:
            current_value = stream.get(field_name)
            if current_value is None or not (
                math.isclose(current_value, new_value, abs_tol=1e-3)
                if isinstance(new_value, float)
                else current_value == new_value
            ):
                stream[field_name] = new_value
                updated_fields.append(field_name)

        # Only notify if at least one field changed
        if updated_fields:
            self._notify_stream(reqId, updated_fields)

    @error_handler(capability="datafeed")
    def historicalDataEnd(self, reqId: int, start: str, end: str) -> None:
        """End signal for historical data - resolve Future with accumulated results."""
        if DEBUG_TWS_CALLBACK:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")
        self._resolve_future(reqId)

    # === Market data (accumulation pattern) ===

    @error_handler(capability="datafeed")
    def tickPrice(
        self, reqId: int, tickType: int, price: float, attrib: TickAttrib
    ) -> None:
        """Accumulate price ticks for market data snapshot."""
        stream = self._stream_data.get(reqId)
        if stream is None:
            return
        tick_name = get_tick_type_name(tickType)
        field_name = TICK_TYPE_TO_FIELD.get(tick_name)  # type: ignore[arg-type]
        if field_name is None:
            return
        current_value: float | None = stream.get(field_name)
        if current_value is None or not math.isclose(
            current_value, price, abs_tol=1e-3
        ):
            stream[field_name] = price
            fields = [field_name]
            if field_name in ["last", "close"]:
                stream["bar_close"] = price
                fields.append("bar_close")
            self._notify_stream(reqId, fields)

    @error_handler(capability="datafeed")
    def tickSize(self, reqId: int, tickType: int, size: Decimal) -> None:
        """Accumulate size ticks for market data snapshot."""
        stream = self._stream_data.get(reqId)
        if stream is None:
            return
        tick_name = get_tick_type_name(tickType)
        field_name = TICK_TYPE_TO_FIELD.get(tick_name)  # type: ignore[arg-type]
        if field_name is None:
            return
        current_value: float | None = stream.get(field_name)
        if current_value is None or not math.isclose(current_value, size, abs_tol=1e-3):
            stream[field_name] = size
            self._notify_stream(reqId, [field_name])

    @error_handler(capability="datafeed")
    def marketDataType(self, reqId: int, marketDataType: int) -> None:
        """Set market data type for the request."""
        stream = self._stream_data.get(reqId)
        if stream is None:
            return
        current_val: int | None = stream.get("market_data_type")
        if current_val is None or current_val != marketDataType:
            stream["market_data_type"] = marketDataType
            self._notify_stream(reqId, ["market_data_type"])

    @error_handler(capability="datafeed")
    def tickReqParams(
        self, tickerId: int, minTick: float, bboExchange: str, snapshotPermissions: int
    ) -> None:
        """Returns exchange map of a particular contract."""
        stream = self._stream_data.get(tickerId)
        if stream is None:
            return
        update_list: list[str] = []
        if stream.get("min_tick") != minTick:
            stream["min_tick"] = minTick
            update_list.append("min_tick")
        if stream.get("bbo_exchange") != bboExchange:
            stream["bbo_exchange"] = bboExchange
            update_list.append("bbo_exchange")
        if stream.get("snapshot_permissions") != snapshotPermissions:
            stream["snapshot_permissions"] = snapshotPermissions
            update_list.append("snapshot_permissions")
        if update_list:
            self._notify_stream(tickerId, update_list)

    @error_handler(capability="datafeed")
    def tickString(self, reqId: int, tickType: int, value: str) -> None:
        """Generic string tick for market data snapshot."""
        stream = self._stream_data.get(reqId)
        if stream is None:
            return
        tick_name = get_tick_type_name(tickType)
        field_name = TICK_TYPE_TO_FIELD.get(tick_name)  # type: ignore[arg-type]
        if field_name is None:
            return
        if stream.get(field_name) != value:
            stream[field_name] = value
            self._notify_stream(reqId, [field_name])

    @error_handler(capability="datafeed")
    def tickGeneric(self, reqId: int, tickType: int, value: float) -> None:
        """Generic float tick for market data snapshot."""
        stream = self._stream_data.get(reqId)
        if stream is None:
            return
        tick_name = get_tick_type_name(tickType)
        field_name = TICK_TYPE_TO_FIELD.get(tick_name)  # type: ignore[arg-type]
        if field_name is None:
            return
        current_value: float | None = stream.get(field_name)
        if current_value is None or not math.isclose(
            current_value, value, abs_tol=1e-3
        ):
            stream[field_name] = value
            self._notify_stream(reqId, [field_name])

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

        self._active_streams: dict[str, int] = {}

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
        if stream_key in self._active_streams:
            self._active_streams[stream_key]
            if DEBUG_TWS_REQUEST:
                debug_log(f"reusing active stream '{stream_key}' for reqQuoteSnapshot")
            return await self.ibsocket.create_tick_future(  # type: ignore[no-any-return]
                self._active_streams[stream_key],
                stream_key,
                timeout=timeout or self._timeout,
                capability="datafeed",
            )

        reqId = self.next_req_id
        coroutine: Awaitable[dict[str, Any]] = self.ibsocket.create_tick_future(
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

        if stream_key in self._active_streams:
            logger.warning(f"BarDataStream for '{stream_key}' already active!")
            self.ibsocket.update_stream(
                self._active_streams[stream_key], callback, on_error
            )
            return stream_key

        bar_data_reqId = self.next_req_id
        self._active_streams[stream_key] = bar_data_reqId
        self.ibsocket.register_stream(
            bar_data_reqId,
            ticker_name(contract, bar_size),
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
            bar_data_reqId,
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
                f"subscribed to bar data for reqId {bar_data_reqId}, "
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
        if stream_key in self._active_streams:
            logger.warning(f"MktDataStream for '{stream_key}' already active!")
            self.ibsocket.update_stream(
                self._active_streams[stream_key], callback, on_error
            )
            return stream_key

        mkt_data_reqId = self.next_req_id
        self.ibsocket.register_stream(
            mkt_data_reqId,
            ticker_name(contract),
            callback,
            capability="datafeed",
            on_error=on_error,
        )
        self._active_streams[stream_key] = mkt_data_reqId

        asset_config = get_asset_config(contract.secType)
        VERSION = 11
        # Build message fields for REQ_MKT_DATA
        mkt_data_fields: list[object] = [
            VERSION,
            mkt_data_reqId,
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
                f"subscribed to realtime reqMktData with reqId {mkt_data_reqId}, symbol='{contract.symbol}'"
            )

        return stream_key

    def cancelBarDataStream(self, stream_key: str) -> None:
        """Cancel a real-time data subscription."""

        reqId = self._active_streams.pop(stream_key, None)
        assert reqId is not None, f"No active stream found for key '{stream_key}'"

        VERSION = 1
        if reqId is not None:
            self.ibsocket.send_message(OUT.CANCEL_HISTORICAL_DATA, [VERSION, reqId])
            if DEBUG_TWS_REQUEST:
                debug_log(f"cancelled realtime bars for reqId {reqId}")

        self.ibsocket.unregister_stream(reqId)

    def cancelMktDataStream(self, stream_key: str) -> None:
        """Cancel a real-time data subscription."""

        reqId = self._active_streams.pop(stream_key, None)
        assert reqId is not None, f"No active stream found for key '{stream_key}'"

        VERSION = 2
        if reqId is not None:
            self.ibsocket.send_message(OUT.CANCEL_MKT_DATA, [VERSION, reqId])
            if DEBUG_TWS_REQUEST:
                debug_log(f"cancelled realtime market data for reqId {reqId}")

        self.ibsocket.unregister_stream(reqId)

    def shutdown(self) -> None:
        """Shutdown the TWSClient and underlying IBSocket."""
        self.__ibsocket.disconnect()
