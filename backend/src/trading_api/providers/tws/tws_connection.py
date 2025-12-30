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
import re
import select
import struct
import threading
import time
from collections.abc import Awaitable, Callable, Coroutine
from decimal import Decimal
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
from trading_api.providers.tws.tws_models import (
    TICK_TYPE_TO_FIELD,
    StreamData,
    classify_error,
    get_asset_config,
    get_bar_duration_seconds,
)

logger = logging.getLogger(__name__)
DEBUG_TWS_REQUEST = os.environ.get("DEBUG_TWS_REQUEST") == "true"
DEBUG_TWS_SEND = os.environ.get("DEBUG_TWS_SEND") == "true"
DEBUG_TWS_RECEIVE = os.environ.get("DEBUG_TWS_RECEIVE") == "true"
DEBUG_TWS_DISPATCH = os.environ.get("DEBUG_TWS_DISPATCH") == "true"
DEBUG_TWS_NOTIFY = os.environ.get("DEBUG_TWS_NOTIFY") == "true"
DEBUG_TWS_SHARED = os.environ.get("DEBUG_TWS_SHARED") == "true"
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


def least_duration_from_bar_size(bar_size: str, num_bars: int = 1) -> str:
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

        # stream hooks: tws-internal-id -> (
        #   caller-loop,
        #   on_data(last-item, list-of-updated-fields),
        #   on_error(tws-error)
        # )
        self._stream_hooks: dict[
            str,
            tuple[
                asyncio.AbstractEventLoop,
                Callable[
                    [dict[str, Any], list[str]],
                    Coroutine[Any, Any, None],
                ],
                Callable[[ProviderException], Coroutine[Any, Any, None]],
            ],
        ] = {}

        # snapshot hooks: tws-internal-id -> list of (
        #   caller-loop,
        #   list-of-accumulated-data-items
        # )
        self._snapshot_hooks: dict[
            str,
            list[
                tuple[asyncio.AbstractEventLoop, asyncio.Future[list[dict[str, Any]]]]
            ],
        ] = {}

        # stream data: tws-internal-id -> list of data items
        self._stream_data: dict[str, StreamData] = {}

        # correspondance dict => business-key-id to tws-internal-id
        # business-key-syntax: "capability:<business-specific-identifier>"
        # tws-internal-id: "(req|order)_${number}"
        self._business_to_tws_key: dict[str, str] = {}

        self._cleanup_hooks: dict[
            str, tuple[asyncio.AbstractEventLoop, Callable[[], None]]
        ] = {}

        # Data tracking attributes
        self._nxt_order_id: int | None = None
        self._reader_accounts: list[str] = []
        self._ready_event = (
            threading.Event()
        )  # Signals when IBKR connection is fully established

    # == infrastructure methods (internal) ==

    def _dispatchMessage(self, fnName: str, fnParams: dict) -> None:
        if DEBUG_TWS_DISPATCH:
            if "self" in fnParams:
                fnParams = dict(fnParams)
                del fnParams["self"]
            debug_log(f"!!!WARNING!!!: unimplemented {fnName} --> {fnParams}")

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
                    if DEBUG_TWS_RECEIVE:
                        debug_log("msgId: %d, protobuf: %s", msgId, data)
                    process_proto(data, msgId)
                else:
                    # Direct split - no list comprehension wrapper needed
                    fields = data.split(NULL)[:-1]  # Remove trailing empty field
                    if DEBUG_TWS_RECEIVE:
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
                self._handle_request_error(
                    TWSErrorCategory.CALLBACK,
                    str(e),
                    "COMMON",
                    f"Exception in IBSocket reader loop: {e!r}",
                )
                time.sleep(0.5)

        debug_log("IBSocket reader loop finished.")

    def _reset(self) -> None:
        """Reset internal state - clear futures, accumulators, callbacks."""
        with self._socket_lock:
            self._stream_data.clear()
            self._reader_accounts.clear()
            self._ready_event.clear()
            self._nxt_order_id = None

    def _handle_request_error(
        self,
        category: str,
        detail: str,
        tws_key: str,
        message: str,
        timestamp: int | None = None,
    ) -> None:
        capability = "shared"
        business_key = next(
            iter(
                [
                    business_key
                    for business_key, _tws_key in self._business_to_tws_key.items()
                    if _tws_key == tws_key
                ]
            ),
            "NOT_FOUND",
        )
        capability = next(iter(business_key.split(":", 1))) or "shared"

        error = ProviderException(
            code=f"PROVIDER_TWS_{category}_{detail.upper()}",
            message=f"[{tws_key}] {message}",
            provider="tws",
            capability=capability,
            timestamp=timestamp,
        )

        # 1. Check for pending _snapshot_hooks
        snapshot_hook = self._snapshot_hooks.get(tws_key, [])
        for snapshot_loop, future in snapshot_hook:
            if tws_key in self._snapshot_hooks:
                snapshot_loop.call_soon_threadsafe(
                    self._snapshot_hooks.pop, tws_key, None
                )

            def safe_set_exception(future: asyncio.Future, error: Exception) -> None:
                if not future.done():
                    future.set_exception(error)

            snapshot_loop.call_soon_threadsafe(safe_set_exception, future, error)

        # 2. Check for active stream
        stream_hook = self._stream_hooks.get(tws_key)
        if stream_hook is not None:
            stream_loop, _, on_error = stream_hook
            stream_loop.call_soon_threadsafe(
                stream_loop.create_task,
                on_error(error),
            )
            stream = self._stream_data.get(tws_key)
            if stream and error.code.endswith("_NON_RECOVERABLE"):
                if stream is not None:
                    stream_loop.call_soon_threadsafe(
                        self.remove_stream, stream.business_key
                    )

        # 3. Orphan error - log warning
        if snapshot_hook is None and stream_hook is None:
            logger.error("Orphan TWS error for reqId %s", tws_key)
            logger.exception(error)

    # == exposed socket methods ===

    def _get_tws_key(self, business_key: str) -> str | None:
        return self._business_to_tws_key.get(business_key)

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

    def get_cached_data(self, business_key: str) -> StreamData | None:
        """Get cached stream data for a business key, if available."""
        return self._stream_data.get(business_key)

    def create_snapshot(
        self,
        business_key: str,
        *,
        timeout: float | None = 5,
    ) -> tuple[int | None, Awaitable[StreamData]]:
        assert re.match(
            r"^(shared|datafeed|broker):", business_key
        ), "ticker_name must start with capability prefix."

        reqId: int | None = None

        tws_key = self._get_tws_key(business_key)
        if tws_key is None:
            reqId = self.next_req_id
            tws_key = f"req_{reqId}"
            self._business_to_tws_key[business_key] = tws_key

        loop = asyncio.get_event_loop()
        future: asyncio.Future[Any] = loop.create_future()

        self._snapshot_hooks.setdefault(tws_key, []).append((loop, future))

        stream = self._stream_data.setdefault(
            tws_key,
            self._stream_data.pop(
                business_key,
                StreamData(
                    business_key,
                    last_dispatched=int(time.time() * 1000),
                    last_updated=int(time.time() * 1000),
                ),
            ),
        )
        if stream.snapshot_complete:
            future.set_result(stream)

        return reqId, asyncio.wait_for(future, timeout)

    def create_stream(
        self,
        business_key: str,
        callback: Callable[
            [dict[str, Any], list[str]],
            Coroutine[Any, Any, None],
        ],
        on_error: Callable[[ProviderException], Coroutine[Any, Any, None]],
    ) -> int | None:
        """Create and register a new stream slot for a reqId.

        Args:
            reqId: Request ID for the stream
            ticker_name: Human-readable ticker_name
            callback: Callback for data updates (receives stream dict and updated fields)
            capability: Capability name for error routing
            on_error: Optional callback for streaming errors (receives ProviderException)
        """

        assert re.match(
            r"^(shared|datafeed|broker):", business_key
        ), "ticker_name must start with capability prefix."

        reqId: int | None = None

        tws_key = self._get_tws_key(business_key)
        if tws_key is None:
            reqId = self.next_req_id
            tws_key = f"req_{reqId}"
            self._business_to_tws_key[business_key] = tws_key
            self._stream_data[tws_key] = self._stream_data.pop(
                business_key,
                StreamData(
                    business_key,
                    last_updated=int(time.time() * 1000),
                    last_dispatched=int(time.time() * 1000),
                ),
            )

        # main thread ownership
        self._stream_hooks[tws_key] = (
            asyncio.get_event_loop(),
            callback,
            on_error,
        )

        return reqId

    def remove_stream(self, business_key: str) -> None:
        tws_key = self._business_to_tws_key.pop(business_key, None)
        if tws_key is None:
            return
        cleanup = self._cleanup_hooks.pop(tws_key, None)
        if cleanup is not None:
            loop, cleanup_func = cleanup
            loop.call_soon_threadsafe(cleanup_func)

        self._stream_hooks.pop(tws_key, None)
        self._business_to_tws_key.pop(tws_key, None)
        stream = self._stream_data.pop(tws_key, None)
        if stream is not None:
            stream.snapshot_complete = False
            self._stream_data[stream.business_key] = stream

    # === Stream management ===

    def _resolve_snapshots(self, tws_key: str, stream: StreamData) -> None:
        """Try to resolve pending snapshot futures if bid/ask/last complete.

        Called from tick callbacks when data is updated. Checks if the stream
        has all required quote fields and resolves the pending snapshot future
        if so.

        Args:
            tws_key: Request ID for the stream
            stream: Stream data dictionary

        Returns:
            The event loop used for resolution, or None if no snapshot was resolved.
        """

        if not stream.snapshot_complete:
            return

        snapshot_hooks = self._snapshot_hooks.get(tws_key)

        if snapshot_hooks is None:
            return

        if DEBUG_TWS_DISPATCH:
            debug_log(
                f"_resolve_snapshots [{tws_key} | {stream.business_key}]"
                + f" with fields: {stream.updated_fields}"
            )

        for loop, future in snapshot_hooks:

            def set_result(stream) -> None:
                if not future.done():
                    future.set_result(stream[:])

            loop.call_soon_threadsafe(set_result, stream)

        loop.call_soon_threadsafe(self._snapshot_hooks.pop, tws_key, None)

        stream.last_dispatched = int(time.time() * 1000)

        def cleanup(tws_key: str) -> None:
            stream = self._stream_data.get(tws_key)
            if stream is not None and (
                (int(time.time() * 1000)) - stream.last_dispatched > 10_000
            ):
                # No stream hook registered - snapshot only
                debug_log(
                    f"_resolve_snapshots::cleanup : no stream listeners => canceling "
                    f"[{tws_key} | {stream.business_key}]"
                )
                self.remove_stream(stream.business_key)

        loop.call_later(11, loop.call_soon_threadsafe, cleanup, tws_key)

    def _dispatch_update(self, tws_key: str, stream: StreamData) -> None:
        stream_hook = self._stream_hooks.get(tws_key)
        if stream_hook is None:
            return

        stream_loop, stream_callback, _ = stream_hook
        if DEBUG_TWS_DISPATCH:
            debug_log(
                f"_dispatch_update [{tws_key} | {stream.business_key}]"
                + f" with fields: {stream.updated_fields}"
            )

        stream_loop.call_soon_threadsafe(
            stream_loop.create_task,
            stream_callback(stream[-1], stream.updated_fields),
        )

        stream.last_dispatched = int(time.time() * 1000)

    def _notify_stream(self, tws_key: str, stream: StreamData) -> None:
        """Trigger stream callbacks if registered.

        Handles both snapshot resolution and continuous stream updates:
        1. Try to resolve pending snapshots (if bid/ask/last complete)
        2. Dispatch to stream callback if registered
        3. Clean up if snapshot-only (no stream hook)
        """
        # TODO: add rate limiting

        if DEBUG_TWS_NOTIFY:
            debug_log(
                f"_dispatch_update [{stream.business_key}]"
                + f" with fields: {stream.updated_fields}"
            )

        # Dispatch to stream callback
        self._dispatch_update(tws_key, stream)

        # Try to resolve pending snapshots
        self._resolve_snapshots(tws_key, stream)

    def _append_stream_data(
        self,
        tws_key: str,
        data: dict[str, Any],
    ) -> None:
        stream = self._stream_data.get(
            tws_key,
        )
        if stream is None:
            return
        data["business_key"] = stream.business_key
        stream.append(data)
        stream.updated_fields.clear()
        stream.last_updated = int(time.time() * 1000)
        self._notify_stream(tws_key, stream)

    def _extend_stream_data(
        self,
        tws_key: str,
        data: list[dict[str, Any]],
    ) -> None:
        stream = self._stream_data.get(tws_key)
        if stream is None:
            return
        data[-1]["business_key"] = stream.business_key
        stream.extend(data)
        stream.updated_fields.clear()
        stream.last_updated = int(time.time() * 1000)
        self._notify_stream(tws_key, stream)

    def _update_stream_data(
        self,
        tws_key: str,
        updates: dict[str, Any],
        *,
        tolerance: float = 1e-3,
    ) -> None:
        stream = self._stream_data.get(tws_key)
        if stream is None:
            return
        if not stream:
            stream.append({})
        last_slot = stream[-1]
        updated_fields: list[str] = []
        for field_name, field_value in updates.items():
            current_value = last_slot.get(field_name)
            if current_value == field_value or (
                isinstance(field_value, (float, int, Decimal))
                and isinstance(current_value, (float, int, Decimal))
                and math.isclose(
                    float(current_value), float(field_value), abs_tol=tolerance
                )
            ):
                continue
            updated_fields.append(field_name)
            last_slot[field_name] = field_value
        if updated_fields:
            stream.last_updated = int(time.time() * 1000)
            stream.updated_fields.clear()
            stream.updated_fields.extend(updated_fields)
            last_slot["business_key"] = stream.business_key
            self._notify_stream(tws_key, stream)

    def _flag_snapshot_complete(self, tws_key: str) -> None:
        stream = self._stream_data.get(tws_key)
        if stream is None:
            return
        stream.snapshot_complete = True
        self._notify_stream(tws_key, stream)

    # ================================================
    # =============== Request Methods ================
    # ================================================

    def reqMatchingSymbols(self, reqId, pattern) -> None:
        self.send_message(OUT.REQ_MATCHING_SYMBOLS, [reqId, pattern])
        debug_log(f"requested symbolSamples for reqId {reqId} and pattern '{pattern}'")

    def reqContractDetails(self, reqId: int, contract: Contract) -> None:
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

        self.send_message(OUT.REQ_CONTRACT_DATA, fields)
        if DEBUG_TWS_REQUEST:
            debug_log(
                f"requested contractDetails for reqId {reqId} and symbol '{contract.symbol}'"
            )

    def reqBars(
        self,
        reqId: int,
        contract: Contract,
        end_date_time: str,
        duration_str: str,
        bar_size: str,
        useRTH: int,
        format_date: int,
    ) -> None:
        asset_config = get_asset_config(contract.secType)
        whatToShow = asset_config.what_to_show_live

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
            not end_date_time,  # keepUpToDate only if end_date_time is empty
            [],  # chartOptions (empty list)
        ]

        def cleanup() -> None:
            VERSION = 1
            self.send_message(OUT.CANCEL_HISTORICAL_DATA, [VERSION, reqId])
            if DEBUG_TWS_REQUEST:
                debug_log(
                    f"canceled bar data for reqId {reqId}, "
                    f"symbol='{contract.symbol}', exchange='{contract.exchange}', "
                    f"end_date_time='{end_date_time}', duration='{duration_str}', barSize='{bar_size}'"
                )

        self._cleanup_hooks[f"req_{reqId}"] = (asyncio.get_event_loop(), cleanup)

        self.send_message(OUT.REQ_HISTORICAL_DATA, fields)
        if DEBUG_TWS_REQUEST:
            debug_log(
                f"requested bar data for reqId {reqId}, "
                f"symbol='{contract.symbol}', exchange='{contract.exchange}', "
                f"end_date_time='{end_date_time}', duration='{duration_str}', barSize='{bar_size}'"
            )

    def reqQuote(self, reqId: int, contract: Contract) -> None:
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
            get_asset_config(
                contract.secType
            ).generic_tick_list_str,  # Asset-type-specific tick list
            0,  # snapshot
            0,  # regulatorySnapshot
            [],  # mktDataOptions (empty list)
        ]

        def cleanup() -> None:
            VERSION = 2
            self.send_message(OUT.CANCEL_MKT_DATA, [VERSION, reqId])
            if DEBUG_TWS_REQUEST:
                debug_log(
                    f"canceled quote data for reqId {reqId} symbol='{contract.symbol}'"
                )

        self._cleanup_hooks[f"req_{reqId}"] = (asyncio.get_event_loop(), cleanup)

        self.send_message(OUT.REQ_MKT_DATA, mkt_data_fields)
        if DEBUG_TWS_REQUEST:
            debug_log(
                f"requested quote data for reqId {reqId} symbol='{contract.symbol}'"
            )

    # ================================================
    # == Dispatch handlers for subscription events ===
    # ================================================

    # === Trading / account management ===

    def managedAccounts(self, accountsList: str) -> None:
        if DEBUG_TWS_SHARED:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")
        # should be sent upon connection
        self._reader_accounts = accountsList.split(",")

    def nextValidId(self, orderId: int) -> None:
        if DEBUG_TWS_SHARED:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")
        # Signals connection fully established - safe to make requests
        self._nxt_order_id = orderId
        self._ready_event.set()

    # === symbolSamples ===

    def symbolSamples(
        self, reqId: int, contractDescriptions: list[ContractDescription]
    ) -> None:
        if DEBUG_TWS_SHARED:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")

        tws_key = f"req_{reqId}"
        self._extend_stream_data(
            tws_key, [{"contractDescriptions": cd} for cd in contractDescriptions]
        )
        self._flag_snapshot_complete(tws_key)

    # === contractDetails (streaming accumulation pattern) ===

    def contractDetails(self, reqId: int, contractDetails: ContractDetails) -> None:
        """Accumulate contract details (may be called multiple times).

        TWS sends one contractDetails callback per matching contract.
        Results are accumulated until contractDetailsEnd is called.
        """
        if DEBUG_TWS_SHARED:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")

        self._append_stream_data(f"req_{reqId}", {"contractDetails": contractDetails})

    def contractDetailsEnd(self, reqId: int) -> None:
        """End signal for contract details - resolve Future with accumulated results."""
        if DEBUG_TWS_SHARED:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")

        self._flag_snapshot_complete(f"req_{reqId}")

    # === historicalData (streaming accumulation pattern) ===

    def historicalData(self, reqId: int, bar: BarData) -> None:
        """Accumulate historical bars (may be called multiple times).

        TWS sends one historicalData callback per bar.
        Results are accumulated until historicalDataEnd is called.
        """
        # if DEBUG_TWS_DATAFEED:
        #     debug_log(f"{current_fn_name()}, {clean_self(vars())}")

        self._append_stream_data(f"req_{reqId}", bar.__dict__)

    def historicalDataUpdate(self, reqId: int, bar: BarData) -> None:
        """Returns updates in real time when keepUpToDate is set to True."""
        if DEBUG_TWS_DATAFEED:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")

        self._update_stream_data(f"req_{reqId}", bar.__dict__)

    def historicalDataEnd(self, reqId: int, start: str, end: str) -> None:
        """End signal for historical data - resolve Future with accumulated results."""
        if DEBUG_TWS_DATAFEED:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")

        self._flag_snapshot_complete(f"req_{reqId}")

    # === Market data (accumulation pattern) ===

    def tickPrice(
        self, reqId: int, tickType: int, price: float, attrib: TickAttrib
    ) -> None:
        """Accumulate price ticks for market data snapshot."""

        if DEBUG_TWS_DATAFEED:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")

        tick_name = get_tick_type_name(tickType)
        field_name = TICK_TYPE_TO_FIELD.get(tick_name)  # type: ignore[arg-type]
        if field_name is None:
            return

        self._update_stream_data(f"req_{reqId}", {field_name: price})

        stream = self._stream_data.get(f"req_{reqId}")
        if stream and not stream.snapshot_complete:
            last_item = stream[-1]
            if all(att in last_item for att in ["bid", "ask", "last"]):
                self._flag_snapshot_complete(f"req_{reqId}")

    def tickSize(self, reqId: int, tickType: int, size: Decimal) -> None:
        """Accumulate size ticks for market data snapshot."""

        if DEBUG_TWS_DATAFEED:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")

        tick_name = get_tick_type_name(tickType)
        field_name = TICK_TYPE_TO_FIELD.get(tick_name)  # type: ignore[arg-type]
        if field_name is None:
            return
        self._update_stream_data(f"req_{reqId}", {field_name: size})

    def marketDataType(self, reqId: int, marketDataType: int) -> None:
        """Set market data type for the request."""
        if DEBUG_TWS_DATAFEED:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")

        self._update_stream_data(f"req_{reqId}", {"market_data_type": marketDataType})

    def tickReqParams(
        self, tickerId: int, minTick: float, bboExchange: str, snapshotPermissions: int
    ) -> None:
        """Returns exchange map of a particular contract."""

        if DEBUG_TWS_DATAFEED:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")

        self._update_stream_data(
            f"req_{tickerId}",
            {
                "min_tick": minTick,
                "bbo_exchange": bboExchange,
                "snapshot_permissions": snapshotPermissions,
            },
        )

    def tickString(self, reqId: int, tickType: int, value: str) -> None:
        """Generic string tick for market data snapshot."""
        if DEBUG_TWS_DATAFEED:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")

        tick_name = get_tick_type_name(tickType)
        field_name = TICK_TYPE_TO_FIELD.get(tick_name)  # type: ignore[arg-type]
        if field_name is None:
            return

        self._update_stream_data(f"req_{reqId}", {field_name: value})

    def tickGeneric(self, reqId: int, tickType: int, value: float) -> None:
        """Generic float tick for market data snapshot."""
        if DEBUG_TWS_DATAFEED:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")

        tick_name = get_tick_type_name(tickType)
        field_name = TICK_TYPE_TO_FIELD.get(tick_name)  # type: ignore[arg-type]
        if field_name is None:
            return

        self._update_stream_data(f"req_{reqId}", {field_name: value})

    def tickSnapshotEnd(self, reqId: int) -> None:
        """When requesting market data snapshots, this market will indicate the
        snapshot reception is finished."""

        if DEBUG_TWS_DATAFEED:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")

        self._flag_snapshot_complete(f"req_{reqId}")

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
            tws_key=f"req_{reqId}",
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

    async def reqMatchingSymbols(
        self, pattern: str, timeout: float | None = None
    ) -> list[ContractDescription]:
        reqId: int | None = None
        coroutine: Awaitable[list[dict[str, ContractDescription]]]
        business_key = f"shared:reqMatchingSymbols:{pattern}"

        reqId, coroutine = self.ibsocket.create_snapshot(
            business_key,
            timeout=timeout or self._timeout,
        )

        if reqId is not None:
            self.ibsocket.reqMatchingSymbols(reqId, pattern)

        data = await coroutine
        return [item["contractDescriptions"] for item in data]

    async def reqContractDetails(
        self, contract: Contract, timeout: float | None = None
    ) -> list[ContractDetails]:
        reqId: int | None = None
        coroutine: Awaitable[list[dict[str, ContractDetails]]]
        business_key = f"shared:reqContractDetails:{ticker_name(contract)}"

        reqId, coroutine = self.ibsocket.create_snapshot(
            business_key,
            timeout=timeout or self._timeout,
        )

        if reqId is not None:
            self.ibsocket.reqContractDetails(reqId, contract)

        data = await coroutine
        return [item["contractDetails"] for item in data]

    async def reqHistoricalData(
        self,
        contract: Contract,
        end_date_time: str,
        duration_str: str,
        bar_size: str,
        useRTH: int = 0,
        format_date: int = 1,
        timeout: float | None = None,
    ) -> list[dict[str, Any]]:
        reqId: int | None = None
        coroutine: Awaitable[list[dict[str, Any]]]
        business_key = (
            f"datafeed:reqHistoricalData:{contract.exchange}:{duration_str}:"
            f"{end_date_time}:{ticker_name(contract, bar_size)}"
        )

        cached_data = self.ibsocket.get_cached_data(business_key)
        if cached_data is not None and cached_data.snapshot_complete:
            return cached_data

        reqId, coroutine = self.ibsocket.create_snapshot(
            business_key,
            timeout=timeout or self._timeout,
        )

        if reqId is not None:
            self.ibsocket.reqBars(
                reqId,
                contract,
                end_date_time,
                duration_str,
                bar_size,
                useRTH,
                format_date,
            )

        return await coroutine

    async def reqQuoteSnapshot(
        self,
        contract: Contract,
        timeout: float | None = None,
        # **kwargs: Any,
    ) -> dict[str, Any]:
        reqId: int | None = None
        coroutine: Awaitable[list[dict[str, Any]]]
        business_key = f"datafeed:Quote:{contract.exchange}:{ticker_name(contract)}"

        reqId, coroutine = self.ibsocket.create_snapshot(
            business_key,
            timeout=timeout or self._timeout,
        )

        if reqId is not None:
            self.ibsocket.reqQuote(reqId, contract)

        acc = await coroutine
        assert acc, "No data received for quote snapshot"
        return next(iter(acc))

    # === Real-time bar subscriptions (continuous pattern) ===

    def reqBarDataStream(
        self,
        contract: Contract,
        bar_size: str,
        callback: Callable[
            [dict[str, Any], list[str]],
            Coroutine[Any, Any, None],
        ],
        on_error: Callable[[ProviderException], Coroutine[Any, Any, None]],
        # **kwargs: Any,
    ) -> str:
        business_key = f"datafeed:reqBarDataStream:{contract.exchange}:{ticker_name(contract, bar_size)}"
        reqId: int | None = self.ibsocket.create_stream(
            business_key,
            callback,
            on_error,
        )

        if reqId is not None:
            self.ibsocket.reqBars(
                reqId,
                contract,
                end_date_time="",
                duration_str=least_duration_from_bar_size(bar_size),
                bar_size=bar_size,
                useRTH=0,
                format_date=1,
            )

        return business_key

    def reqMktDataStream(
        self,
        contract: Contract,
        callback: Callable[
            [dict[str, Any], list[str]],
            Coroutine[Any, Any, None],
        ],
        on_error: Callable[[ProviderException], Coroutine[Any, Any, None]],
        # **kwargs: Any,
    ) -> str:
        business_key = f"datafeed:Quote:{contract.exchange}:{ticker_name(contract)}"
        reqId: int | None = self.ibsocket.create_stream(
            business_key,
            callback,
            on_error,
        )

        if reqId is not None:
            self.ibsocket.reqQuote(reqId, contract)

        return business_key

    def cancelBarDataStream(self, stream_key: str) -> None:
        """Cancel a real-time data subscription."""
        self.ibsocket.remove_stream(stream_key)

    def cancelMktDataStream(self, stream_key: str) -> None:
        """Cancel a real-time data subscription."""
        self.ibsocket.remove_stream(stream_key)

    def shutdown(self) -> None:
        """Shutdown the TWSClient and underlying IBSocket."""
        self.__ibsocket.disconnect()
