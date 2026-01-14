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
from typing import Any, TypeVar

from ibapi.client_utils import (
    createCancelOrderRequestProto,
    createPlaceOrderRequestProto,
)
from ibapi.common import BarData, TickAttrib
from ibapi.const import (
    DOUBLE_INFINITY,
    INFINITY_STR,
    UNSET_DECIMAL,
    UNSET_DOUBLE,
    UNSET_INTEGER,
)
from ibapi.contract import Contract, ContractDescription, ContractDetails
from ibapi.decoder import Decoder
from ibapi.message import OUT
from ibapi.order import Order
from ibapi.order_cancel import OrderCancel
from ibapi.order_state import OrderState
from ibapi.protobuf.ErrorMessage_pb2 import ErrorMessage as ErrorMessageProto
from ibapi.ticktype import TickTypeEnum
from ibapi.wrapper import EWrapper, current_fn_name

from trading_api.models.exceptions import ProviderException
from trading_api.providers.tws.account_tracker import (
    TWS_TAG_TO_FIELD,
    AccountTracker,
    TrackedAccount,
)
from trading_api.providers.tws.cached_contract import CachedContract
from trading_api.providers.tws.order_tracker import OrderTracker, TrackedOrder
from trading_api.providers.tws.position_tracker import PositionTracker, TrackedPosition
from trading_api.providers.tws.tws_mappers import (
    build_darkpool_contract,
    parse_ticker,
    ticker_name,
)
from trading_api.providers.tws.tws_models import (
    TICK_TYPE_TO_FIELD,
    StreamData,
    TWSErrorClassification,
    TWSErrorNature,
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
DEBUG_TWS_ACCOUNT = os.environ.get("DEBUG_TWS_ACCOUNT") == "true"
DEBUG_TWS_CACHE = os.environ.get("DEBUG_TWS_CACHE") == "true"

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
        self._req_id_count: count[int] = count()
        self._socket_lock = threading.Lock()
        self._state = IBSocketState.READY
        self._socket = socket()
        self._reader_loop: asyncio.AbstractEventLoop | None = None
        self.stale_delay_ms: int = 10_000

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
        self.order_tracker: OrderTracker = OrderTracker()
        self.position_tracker: PositionTracker = PositionTracker()
        self.account_tracker: AccountTracker = AccountTracker(
            self.reqAccountSubscriptions, self.cancelAccountSubscriptions
        )
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
            self._stream_hooks.clear()
            self._snapshot_hooks.clear()
            self._cleanup_hooks.clear()
            self._reader_accounts.clear()
            self._ready_event.clear()
            self._business_to_tws_key.clear()
            self._req_id_count = count()
            self.order_tracker.reset()
            self.position_tracker.reset()

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
        snapshot_hooks = self._snapshot_hooks.get(tws_key, [])
        for snapshot_loop, future in snapshot_hooks:

            def safe_set_exception(future: asyncio.Future, error: Exception) -> None:
                if not future.done():
                    future.set_exception(error)

            snapshot_loop.call_soon_threadsafe(safe_set_exception, future, error)

        for snapshot_loop, _ in snapshot_hooks:
            snapshot_loop.call_soon_threadsafe(self._clean_snapshot, business_key)
            break  # Only need to clean once

        # 2. Check for active stream
        stream_loop, _, on_error = self._stream_hooks.get(tws_key, (None, None, None))
        if stream_loop is not None and on_error is not None:
            stream_loop.call_soon_threadsafe(
                stream_loop.create_task,
                on_error(error),
            )

            if error.code.endswith("_NON_RECOVERABLE"):
                stream_loop.call_soon_threadsafe(self.remove_stream, business_key)

        # 3. Orphan error - log warning
        if not snapshot_hooks and not stream_loop:
            logger.error("Orphan TWS error for reqId %s", tws_key)
            logger.exception(error)

    # == exposed socket methods ===

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
        return next(self._req_id_count)

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

    def send_protobuf(self, msgId: int, protobuf_data: bytes) -> None:
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

    def get_cached_data(self, business_key: str) -> StreamData | None:
        """Get cached stream data for a business key, if available."""
        return self._stream_data.get(business_key)

    def create_snapshot(
        self,
        business_key: str,
        *,
        timeout: float | None = 5,
    ) -> tuple[int | None, Coroutine[Any, Any, StreamData]]:
        assert re.match(
            r"^(shared|datafeed|broker):", business_key
        ), "business_key must start with capability prefix."

        req_id: int | None = None

        tws_key, req_id = self._acquire_tws_key(business_key)
        stream = self._stream_data.get(tws_key)
        assert stream is not None, "Stream data must be initialized."

        loop = asyncio.get_event_loop()
        future: asyncio.Future[Any] = loop.create_future()

        self._snapshot_hooks.setdefault(tws_key, []).append((loop, future))
        if stream.snapshot_complete:
            future.set_result(stream)

        return req_id, self._timeout_wrapper(tws_key, business_key, future, timeout)

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
            business_key: Human-readable business_key
            callback: Callback for data updates (receives stream dict and updated fields)
            capability: Capability name for error routing
            on_error: Optional callback for streaming errors (receives ProviderException)
        """

        assert re.match(
            r"^(shared|datafeed|broker):", business_key
        ), "business_key must start with capability prefix."

        tws_key, req_id = self._acquire_tws_key(business_key)

        # main thread ownership
        self._stream_hooks[tws_key] = (
            asyncio.get_event_loop(),
            callback,
            on_error,
        )
        return req_id

    def remove_stream(self, business_key: str) -> None:
        tws_key = self._business_to_tws_key.get(business_key)
        if tws_key is None:
            return

        self._stream_hooks.pop(tws_key, None)

        if tws_key in self._snapshot_hooks:
            debug_log(
                f"remove_stream: snapshot hooks still pending for "
                f"[{tws_key} | {business_key}] => not removing stream data."
            )
            return

        self._business_to_tws_key.pop(business_key, None)
        stream = self._stream_data.pop(tws_key, None)
        if stream is not None:
            stream.snapshot_complete = False
            self._stream_data[business_key] = stream

        cleanup = self._cleanup_hooks.pop(tws_key, None)
        if cleanup is not None:
            loop, cleanup_func = cleanup
            loop.call_soon_threadsafe(cleanup_func)

    # === Stream management ===

    def _acquire_tws_key(self, business_key: str) -> tuple[str, int | None]:
        tws_key = self._business_to_tws_key.get(business_key)
        if tws_key is not None:
            return tws_key, None

        req_id = self.next_req_id
        tws_key = f"req_{req_id}"
        self._business_to_tws_key[business_key] = tws_key
        self._stream_data[tws_key] = self._stream_data.pop(
            business_key,
            StreamData(
                business_key,
                last_updated=int(time.time() * 1000),
                last_dispatched=int(time.time() * 1000),
            ),
        )

        return tws_key, req_id

    async def _timeout_wrapper(
        self,
        tws_key: str,
        business_key: str,
        future: asyncio.Future[StreamData],
        timeout: float | None,
    ) -> StreamData:
        """Await snapshot with automatic cleanup on timeout."""
        try:
            return await asyncio.wait_for(future, timeout)
        except TimeoutError:
            snapshot_hooks = self._snapshot_hooks.get(tws_key, [])
            current_hook = next(
                iter([hook for hook in snapshot_hooks if hook[1] == future]), None
            )
            if current_hook is not None:
                snapshot_hooks.remove(current_hook)
            if not snapshot_hooks:
                self._clean_snapshot(business_key)
            raise

    def _clean_snapshot(self, business_key: str) -> None:
        tws_key = self._business_to_tws_key.get(business_key)
        if tws_key is None:
            return
        self._snapshot_hooks.pop(tws_key, None)

        def stream_cleanup(tws_key: str, business_key: str) -> None:
            if tws_key not in self._stream_hooks:
                debug_log(
                    f"_resolve_snapshots::cleanup : no stream listeners => canceling "
                    f"[{tws_key} | {business_key}]"
                )
                self.remove_stream(business_key)

        asyncio.get_event_loop().call_later(11, stream_cleanup, tws_key, business_key)

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

        loop: asyncio.AbstractEventLoop | None = None
        for loop, future in snapshot_hooks:

            def set_result(stream: StreamData) -> None:
                if not future.done():
                    future.set_result(stream)

            loop.call_soon_threadsafe(set_result, stream)

        stream.last_dispatched = int(time.time() * 1000)

        for loop, future in snapshot_hooks:
            loop.call_soon_threadsafe(self._clean_snapshot, stream.business_key)
            break  # Only need to clean once

    def _dispatch_update(self, tws_key: str, stream: StreamData) -> None:
        stream_hooks = self._stream_hooks.get(tws_key)
        if stream_hooks is None:
            return

        stream_loop, stream_callback, _ = stream_hooks
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

    def reqMatchingSymbols(self, reqId: int, pattern: str) -> None:
        assert (
            isinstance(reqId, int) and reqId >= 0
        ), "reqId must be a non-negative integer."
        assert (
            isinstance(pattern, str) and pattern
        ), "Pattern must be a non-empty string."
        self.send_message(OUT.REQ_MATCHING_SYMBOLS, [reqId, pattern])
        debug_log(f"requested symbolSamples for reqId {reqId} and pattern '{pattern}'")

    def reqContractDetails(self, reqId: int, contract: Contract) -> None:
        assert (
            isinstance(reqId, int) and reqId >= 0
        ), "reqId must be a non-negative integer."
        assert (
            isinstance(contract, Contract) and contract.symbol and contract.secType
        ), "contract must be an instance of Contract with a non-empty symbol and secType."
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
        assert (
            isinstance(reqId, int) and reqId >= 0
        ), "reqId must be a non-negative integer."
        assert (
            isinstance(contract, Contract) and contract.conId != 0
        ), "contract must be an instance of Contract with a non-zero conId."
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

        def cancelation_task() -> None:
            VERSION = 1
            self.send_message(OUT.CANCEL_HISTORICAL_DATA, [VERSION, reqId])
            if DEBUG_TWS_REQUEST:
                debug_log(
                    f"canceled bar data for reqId {reqId}, "
                    f"symbol='{contract.symbol}', exchange='{contract.exchange}', "
                    f"end_date_time='{end_date_time}', duration='{duration_str}', barSize='{bar_size}'"
                )

        self._cleanup_hooks[f"req_{reqId}"] = (
            asyncio.get_event_loop(),
            cancelation_task,
        )

        self.send_message(OUT.REQ_HISTORICAL_DATA, fields)
        if DEBUG_TWS_REQUEST:
            debug_log(
                f"requested bar data for reqId {reqId}, "
                f"symbol='{contract.symbol}', exchange='{contract.exchange}', "
                f"end_date_time='{end_date_time}', duration='{duration_str}', barSize='{bar_size}'"
            )

    def reqQuote(self, reqId: int, contract: Contract) -> None:
        assert (
            isinstance(reqId, int) and reqId >= 0
        ), "reqId must be a non-negative integer."
        assert (
            isinstance(contract, Contract) and contract.conId != 0
        ), "contract must be an instance of Contract with a non-zero conId."
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

        def cancelation_task() -> None:
            VERSION = 2
            self.send_message(OUT.CANCEL_MKT_DATA, [VERSION, reqId])
            if DEBUG_TWS_REQUEST:
                debug_log(
                    f"canceled quote data for reqId {reqId} symbol='{contract.symbol}'"
                )

        self._cleanup_hooks[f"req_{reqId}"] = (
            asyncio.get_event_loop(),
            cancelation_task,
        )

        self.send_message(OUT.REQ_MKT_DATA, mkt_data_fields)
        if DEBUG_TWS_REQUEST:
            debug_log(
                f"requested quote data for reqId {reqId} symbol='{contract.symbol}'"
            )

    def placeOrder(self, order_id: int, contract: Contract, order: Order) -> None:
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
        self.send_protobuf(proto_msg_id, serialized)
        ticker = ticker_name(contract)
        if DEBUG_TWS_REQUEST:
            debug_log(
                f"placed order (protobuf): id={order_id}, ticker={ticker}, Exchange={contract.exchange} "
                f"action={order.action}, type={order.orderType} "
                f"qty={order.totalQuantity}, type={order.lmtPrice or order.auxPrice} "
            )

    def reqOpenOrders(self) -> None:
        def request_cb() -> None:
            VERSION = 1
            self.send_message(OUT.REQ_OPEN_ORDERS, [VERSION])
            if DEBUG_TWS_REQUEST:
                debug_log("requested open orders")

        self.order_tracker.ensure_snapshot_requested(request_cb)

    def cancelOrder(self, order_id: int) -> None:
        orderCancel = OrderCancel()
        cancelOrderRequestProto = createCancelOrderRequestProto(order_id, orderCancel)
        serializedString = cancelOrderRequestProto.SerializeToString()

        self.send_protobuf(OUT.CANCEL_ORDER + PROTOBUF_MSG_ID, serializedString)

        if DEBUG_TWS_REQUEST:
            debug_log(f"cancelled order: id={order_id}")

    def reqPositions(self) -> None:
        def request_cb() -> None:
            VERSION = 1
            self.send_message(OUT.REQ_POSITIONS, [VERSION])
            if DEBUG_TWS_REQUEST:
                debug_log("requested positions")

        self.position_tracker.ensure_snapshot_requested(request_cb)

    def reqAccountSummary(self) -> None:
        def request_cb() -> int:
            VERSION = 1
            reqId = self.next_req_id
            self.send_message(
                OUT.REQ_ACCOUNT_SUMMARY,
                [VERSION, reqId, "All", ",".join(TWS_TAG_TO_FIELD.keys())],
            )
            if DEBUG_TWS_REQUEST:
                debug_log("requested account summary")
            return reqId

        self.account_tracker.ensure_summary_requested(request_cb)

    def _reqAccountUpdates(self, subscribe: bool, acctCode: str) -> None:
        """Subscribe/unsubscribe to account updates.

        Triggers callbacks:
            - updateAccountValue() for each account metric
            - updatePortfolio() for each position
            - updateAccountTime() with timestamp
            - accountDownloadEnd() when batch complete

        Args:
            subscribe: True to subscribe, False to unsubscribe
            acctCode: Account code (required for FA accounts)
        """
        VERSION = 2
        self.send_message(OUT.REQ_ACCT_DATA, [VERSION, subscribe, acctCode])
        if DEBUG_TWS_REQUEST:
            debug_log(f"reqAccountUpdates subscribe={subscribe}, acct={acctCode}")

    def _reqPnL(self, reqId: int, account: str, modelCode: str = "") -> None:
        """Subscribe to real-time P&L updates.

        Triggers pnl() callback with dailyPnL, unrealizedPnL, realizedPnL.
        Updates are pushed in real-time (not on 3-min interval like reqAccountUpdates).

        Args:
            reqId: Request ID for tracking
            account: Account code
            modelCode: Model code (empty string for default)
        """
        self.send_message(OUT.REQ_PNL, [reqId, account, modelCode])
        if DEBUG_TWS_REQUEST:
            debug_log(f"reqPnL reqId={reqId}, account={account}")

    def reqAccountSubscriptions(self, account: str) -> int:
        """Subscribe to account updates with P&L.

        Combines _reqAccountUpdates and _reqPnL for comprehensive account tracking.

        Args:
            account: Account code
        Returns:
            Request ID for P&L subscription
        """

        self._reqAccountUpdates(True, account)
        reqId = self.next_req_id
        self._reqPnL(reqId, account)

        return reqId

    def _cancelPnL(self, reqId: int) -> None:
        """Cancel P&L subscription.

        Args:
            reqId: Request ID from reqPnL()
        """
        self.send_message(OUT.CANCEL_PNL, [reqId])
        if DEBUG_TWS_REQUEST:
            debug_log(f"cancelPnL reqId={reqId}")

    def cancelAccountSubscriptions(self, reqId: int) -> None:
        """Subscribe to account updates with P&L.

        Combines _reqAccountUpdates and _reqPnL for comprehensive account tracking.

        Args:
            account: Account code
        Returns:
            Request ID for P&L subscription
        """
        self._cancelPnL(reqId)

    # ================================================
    # == Dispatch handlers for subscription events ===
    # ================================================

    # === Trading / account management ===

    def managedAccounts(self, accountsList: str) -> None:
        if DEBUG_TWS_ACCOUNT:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")
        # should be sent upon connection
        self._reader_accounts = accountsList.split(",")
        for account in self._reader_accounts:
            self.account_tracker.upsert_account(account)

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
        if DEBUG_TWS_ACCOUNT:
            debug_log(
                f"{current_fn_name()}, reqId={reqId}, account={account}, "
                f"tag={tag}, value={value}, currency={currency}"
            )

        self.account_tracker.update_account(account, tag, value, currency)

    def accountSummaryEnd(self, reqId: int) -> None:
        """End signal for account summary request.

        Called after all accountSummary callbacks for reqAccountSummary().
        Resolves the pending future with accumulated summary data.
        """
        if DEBUG_TWS_ACCOUNT:
            debug_log(f"{current_fn_name()}")

        # Mark snapshot complete and resolve pending futures
        self.account_tracker.mark_snapshot_complete()

    # === Account Updates (reqAccountUpdates callbacks) ===

    def updateAccountValue(
        self, key: str, val: str, currency: str, accountName: str
    ) -> None:
        """Callback for account value updates from reqAccountUpdates().

        Called multiple times after reqAccountUpdates(True) for each account metric.
        Uses same routing as accountSummary() via account_tracker.update_account().

        Args:
            key: TWS PascalCase tag name (e.g., "NetLiquidation")
            val: Value as string
            currency: Currency of the value (may be empty)
            accountName: Account ID
        """
        if DEBUG_TWS_ACCOUNT:
            debug_log(f"{current_fn_name()}: {key}={val} {currency} for {accountName}")
        self.account_tracker.update_account(accountName, key, val, currency)

    def updatePortfolio(
        self,
        contract: Contract,
        position: Decimal,
        marketPrice: float,
        marketValue: float,
        averageCost: float,
        unrealizedPNL: float,
        realizedPNL: float,
        accountName: str,
    ) -> None:
        """Callback for portfolio updates from reqAccountUpdates().

        Called for each position after reqAccountUpdates(True).
        Currently logged only - per-position P&L enrichment deferred to future phase.

        Args:
            contract: Position contract
            position: Position quantity (positive=long, negative=short)
            marketPrice: Current market price
            marketValue: Position market value
            averageCost: Average cost per share
            unrealizedPNL: Unrealized P&L for this position
            realizedPNL: Realized P&L for this position
            accountName: Account ID
        """
        if DEBUG_TWS_ACCOUNT:
            debug_log(
                f"{current_fn_name()}: {contract.symbol} pos={position} "
                f"unrealPnL={unrealizedPNL} for {accountName}"
            )
        # Future: Route to position_tracker for per-position P&L enrichment
        # self.position_tracker.update_position_pnl(...)

    def updateAccountTime(self, timeStamp: str) -> None:
        """Callback for account update timestamp.

        Called during reqAccountUpdates() to indicate freshness of data.

        Args:
            timeStamp: Time string from TWS
        """
        if DEBUG_TWS_ACCOUNT:
            debug_log(f"{current_fn_name()}: {timeStamp}")
        # Update last_update_time on tracked accounts
        for tracked in self.account_tracker._accounts.values():
            tracked.last_update_time = timeStamp

    def accountDownloadEnd(self, accountName: str) -> None:
        """End signal for reqAccountUpdates() batch.

        Called after all updateAccountValue/updatePortfolio callbacks.
        Marks snapshot complete similar to accountSummaryEnd.

        Args:
            accountName: Account ID for which download completed
        """
        if DEBUG_TWS_ACCOUNT:
            debug_log(f"{current_fn_name()}: {accountName}")
        self.account_tracker.mark_snapshot_complete()

    # === Real-time P&L (reqPnL callback) ===

    def pnl(
        self, reqId: int, dailyPnL: float, unrealizedPnL: float, realizedPnL: float
    ) -> None:
        """Real-time P&L callback from reqPnL().

        Provides faster P&L updates than reqAccountUpdates() (real-time vs 3-min).
        Routes to account_tracker.update_pnl() to update TrackedAccount.

        Args:
            reqId: Request ID from reqPnL()
            dailyPnL: Today's profit/loss
            unrealizedPnL: Unrealized P&L across all positions
            realizedPnL: Realized P&L across all positions
        """
        if DEBUG_TWS_BROKER:
            debug_log(
                f"{current_fn_name()}: reqId={reqId} daily={dailyPnL} "
                f"unrealized={unrealizedPnL} realized={realizedPnL}"
            )
        self.account_tracker.update_pnl(reqId, dailyPnL, unrealizedPnL, realizedPnL)

    # === symbolSamples ===

    def symbolSamples(
        self, reqId: int, contractDescriptions: list[ContractDescription]
    ) -> None:
        if DEBUG_TWS_SHARED:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")

        tws_key = f"req_{reqId}"
        if contractDescriptions:
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

    # === Order management ===

    def nextValidId(self, orderId: int) -> None:
        if DEBUG_TWS_SHARED:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")
        # Signals connection fully established - safe to make requests
        self.order_tracker.set_next_order_id(orderId)
        self._ready_event.set()
        debug_log(f"TWS connection ready for requests. Next order ID: {orderId}")

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

        self.order_tracker.upsert_order(
            orderId=orderId,
            contract=contract,
            order=order,
            orderState=orderState,
        )

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
        self.order_tracker.update_status(
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

    def openOrderEnd(self) -> None:
        """End signal for open orders request.

        Called after all openOrder callbacks for reqOpenOrders().
        Marks snapshot as complete and resolves pending futures.
        """
        if DEBUG_TWS_BROKER:
            debug_log(f"{current_fn_name()}")

        # Mark snapshot complete and resolve pending futures
        self.order_tracker.mark_snapshot_complete()

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
        self.position_tracker.upsert_position(
            account=account,
            contract=contract,
            position=position,
            avgCost=avgCost,
        )

    def positionEnd(self) -> None:
        """End signal for positions request.

        Called after all position callbacks for reqPositions().
        Resolves the pending future with accumulated position data.
        """
        if DEBUG_TWS_BROKER:
            debug_log(f"{current_fn_name()}")

        # Mark snapshot complete and resolve pending futures
        self.position_tracker.mark_snapshot_complete()

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
            reqId: Request ID or Order ID (-1 for system-wide errors)
            errorTime: Unix timestamp of error
            errorCode: TWS error code (e.g., 10187, 200, etc.)
            errorString: Error message from TWS
            advancedOrderRejectJson: Advanced order reject details (optional)
        """
        # Classify error by nature, category, and recoverability
        nature, category, recoverable = classify_error(errorCode)

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

        # Info-level errors are logged but not raised
        if category == TWSErrorClassification.INFO:
            logger.info(f"TWS {nature} [code=PROVIDER_TWS_{errorCode}]: {message}")
            return

        # Route based on error nature
        if nature == TWSErrorNature.ORDER:
            # Order-related errors use order_{orderId} key format
            tws_key = f"order_{reqId}"
            self.order_tracker.raise_error(
                ProviderException(
                    provider="tws",
                    capability="broker",
                    code=f"PROVIDER_TWS_{errorCode}",
                    message=message,
                )
            )
        else:
            # Request-related errors use req_{reqId} key format
            tws_key = f"req_{reqId}"
            self._handle_request_error(
                category=TWSErrorCategory.API,
                detail=detail,
                tws_key=tws_key,
                message=message,
                timestamp=(
                    errorTime // 1000 if errorTime > 10_000_000_000 else errorTime
                ),
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

        # conId => CachedContract
        self.__contracts_cache: dict[int, CachedContract] = {}

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

    # === Generic snapshot executor ===

    _T = TypeVar("_T")

    async def _exec_snapshot(
        self,
        business_key: str,
        request_fn: Callable[[int], None],
        transform_fn: Callable[[list[dict[str, Any]]], _T],
        timeout: float | None = None,
    ) -> _T:
        """Generic snapshot pattern executor.

        Handles the common cache-check → create-snapshot → request → await pattern.

        Args:
            business_key: Unique key for caching/deduplication
            request_fn: Function called with reqId to issue the TWS request
            transform_fn: Function to transform raw data list to return type
            timeout: Optional timeout override

        Returns:
            Transformed result from TWS response
        """
        cached = self.ibsocket.get_cached_data(business_key)
        if cached and cached.snapshot_complete:
            return transform_fn(cached)

        reqId, coroutine = self.ibsocket.create_snapshot(
            business_key, timeout=timeout or self._timeout
        )
        if reqId is not None:
            request_fn(reqId)

        return transform_fn(await coroutine)

    # === Contract resolution and caching ===

    def _get_cached_details(
        self,
        contract: Contract,
    ) -> list[CachedContract]:
        """Get cached contracts matching ticker with optional exchange filtering.

        Args:
            ticker: Ticker string to match
            preferred_exchanges: Optional list of exchanges to filter by
            require_full_details: If True, only return contracts with full details

        Returns:
            List of CachedContract matching the criteria
        """
        contract_exchange = contract.primaryExchange or contract.exchange
        cached = [
            cached_contract
            for cached_contract in (
                [self.__contracts_cache.get(contract.conId)]
                if (contract.conId and contract.conId > 0)
                else [
                    con
                    for con in self.__contracts_cache.values()
                    if contract.symbol == con.contract.symbol
                    and (
                        not contract_exchange or contract_exchange in con.validExchanges
                    )
                    and con.has_full_details
                ]
            )
            if cached_contract is not None
        ]

        return cached

    async def reqMatchingSymbols(
        self, pattern: str, timeout: float | None = None
    ) -> list[CachedContract]:
        """Search for matching symbols by pattern.

        Uses cache-first strategy: results are cached by conId, and subsequent
        searches populate the cache for reuse by reqContractDetails.

        Args:
            pattern: Symbol search pattern (e.g., "AAPL", "MSFT")
            timeout: Optional timeout override

        Returns:
            List of ContractDescription matching the pattern
        """

        # TODO: need to cache data. IB has a tight ratelimit for this call.
        cached_list = [
            con
            for con in self.__contracts_cache.values()
            if con.contract.symbol.startswith(pattern)
        ]

        if cached_list:
            if DEBUG_TWS_CACHE:
                debug_log(
                    f"reqMatchingSymbols cache hit for conId {cached_list[0].contract.conId} => ({pattern})"
                )
            return cached_list

        reqId: int | None = None
        coroutine: Awaitable[list[dict[str, ContractDescription]]]
        business_key = f"shared:reqMatchingSymbols:{pattern}"

        reqId, coroutine = self.ibsocket.create_snapshot(
            business_key,
            timeout=3.0,
        )

        if reqId is not None:
            self.ibsocket.reqMatchingSymbols(reqId, pattern)

        data = await coroutine
        descriptions: list[ContractDescription] = [
            item["contractDescriptions"] for item in data
        ]

        # Create CachedContracts and populate cache
        results = [
            CachedContract.from_contract_description(desc)
            for desc in descriptions
            if desc.contract.conId > 0
        ]

        # Populate cache for reuse by reqContractDetails
        # for cached_contract in results:
        #     self.__contracts_cache[cached_contract.contract.conId] = cached_contract

        return results

    async def _reqContractDetails(
        self, contract: Contract, timeout: float | None = None
    ) -> list[ContractDetails]:
        """Get full contract details.

        Uses cache-first strategy:
        - If cached with full details, returns immediately
        - Otherwise fetches from TWS and updates cache

        Args:
            contract: The contract to get details for (must have conId)
            timeout: Optional timeout override

        Returns:
            List of ContractDetails (usually 1, but can be multiple for ambiguous contracts)
        """
        business_key = f"shared:reqContractDetails:{contract.exchange or 'ANY'}:{ticker_name(contract)}"
        data = self.ibsocket.get_cached_data(business_key)
        if not data:
            reqId, coroutine = self.ibsocket.create_snapshot(
                business_key,
                timeout=2.0,
            )
            if reqId is not None:
                self.ibsocket.reqContractDetails(reqId, contract)
            data = await coroutine

        details_list: list[ContractDetails] = [item["contractDetails"] for item in data]
        return details_list

    async def reqContractDetails(
        self, contract: Contract, timeout: float | None = None
    ) -> list[CachedContract]:
        """Get full contract details.

        Uses cache-first strategy:
        - If cached with full details, returns immediately
        - Otherwise fetches from TWS and updates cache

        Args:
            contract: The contract to get details for (must have conId)
            timeout: Optional timeout override

        Returns:
            List of ContractDetails (usually 1, but can be multiple for ambiguous contracts)
        """
        ticker_name(contract)
        cached_list: list[CachedContract] = self._get_cached_details(contract)

        if cached_list:
            if DEBUG_TWS_CACHE:
                debug_log(
                    f"reqContractDetails cache hit for conId {contract.conId} => "
                    f"({contract.primaryExchange or contract.exchange}:{contract.symbol})"
                )
            return cached_list

        cached_list = await self.reqMatchingSymbols(
            contract.symbol, timeout=timeout or self._timeout
        )

        async def load_and_cache(con: Contract) -> None:
            details = next(iter(await self._reqContractDetails(con, timeout=timeout)))
            overnight_hours: str | None = None
            if darkpool_contract := build_darkpool_contract(details):
                darkpool_details = next(
                    iter(
                        await self._reqContractDetails(
                            darkpool_contract, timeout=timeout
                        )
                    )
                )
                overnight_hours = darkpool_details.tradingHours
            self.__contracts_cache[
                details.contract.conId
            ] = CachedContract.from_contract_details(
                details, overnight_hours=overnight_hours
            )

        await asyncio.gather(
            *[
                load_and_cache(con)
                for con in {
                    cached.contract.conId: cached.contract for cached in cached_list
                }.values()
            ]
        )

        # return cached data
        return self._get_cached_details(contract)

    async def req_ticker_details(
        self,
        ticker: str,
        **kwargs: Any,
    ) -> CachedContract:
        """Get detailed symbol information.

        [ASYNC-BRIDGE]: Wraps sync TWS callback with async Future.
        [ACCUMULATION]: TWS may return multiple CachedContract, we use first match.
        [DOMAIN-ONLY]: Returns domain SymbolInfo (no TWS types).

        Args:
            symbol: Symbol name (e.g., "AAPL")
            exchange: Optional exchange filter (default: "SMART" for smart routing)

        Returns:
            Detailed symbol metadata (SymbolInfo)

        Raises:
            ProviderException: If symbol not found or request fails
        """

        symbol, primaryExchange, sec_type, _ = parse_ticker(ticker)
        contract = Contract()
        contract.symbol = symbol
        contract.secType = sec_type
        contract.primaryExchange = primaryExchange

        # Get contract details via TWSClient (returns list)
        details_list = await self.reqContractDetails(contract, **kwargs)

        if not details_list:
            raise ProviderException(
                code="PROVIDER_DATAFEED_SYMBOL_NOT_FOUND",
                message=f"Symbol not found: {ticker}",
                provider="tws",
                capability="datafeed",
            )

        return next(iter(details_list))

    # === Historical data snapshot (one-time pattern) ===

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
            timeout=30,
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
    ) -> dict[str, Any]:
        business_key = f"datafeed:Quote:{contract.exchange}:{ticker_name(contract)}"

        def transform(data: list[dict[str, Any]]) -> dict[str, Any]:
            assert data, "No data received for quote snapshot"
            return next(iter(data))

        return await self._exec_snapshot(
            business_key,
            lambda rid: self.ibsocket.reqQuote(rid, contract),
            transform,
            timeout,
        )

    # === Real-time data subscriptions (continuous pattern) ===

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

    def cancel_data_stream(self, stream_key: str) -> None:
        """Cancel a real-time data subscription (bars or market data)."""
        self.ibsocket.remove_stream(stream_key)

    # === Order management ===

    def _submit_order(
        self,
        contract: Contract,
        order: Order,
        parent_id: int = 0,
        transmit: bool = False,
    ) -> tuple[int, bool]:
        order_id = order.orderId
        place_flag = True
        tracked: TrackedOrder | None = (
            self.ibsocket.order_tracker.ensure_existing_order(order_id)
            if order_id > 0
            else (
                self.ibsocket.order_tracker.find_by_oca_group(
                    order.ocaGroup,
                    order.orderType,
                    order.action,
                )
                if order.ocaGroup
                else None
            )
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
            assert (
                not place_flag or order_ori.transmit == transmit
            ), f"Cannot change transmit flag of an existing order {order_ori.transmit} -> {transmit}"
            order = order_ori
            order.tif = ""  # do not modify time-in-force for existing orders
            order.transmit = True  # always transmit existing orders
        else:
            order_id = self.ibsocket.order_tracker.next_order_id
            order.parentId = parent_id
            order.transmit = transmit

        if place_flag:
            self.ibsocket.placeOrder(order_id, contract, order)

        return order_id, place_flag

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
        signed_oca_groups = self.ibsocket.order_tracker.signed_oca_groups()
        signed_oca_group = next(
            iter([group for group in signed_oca_groups if group.startswith(oca_group)]),
            f"{oca_group}@{int(time.time() * 1000)}",
        )

        # Assign OCA attributes to each order
        for order in order_list:
            order.ocaGroup = signed_oca_group
            order.ocaType = oca_type

        submit_results = [
            self._submit_order(contract, order, parent_id=parent_id, transmit=False)
            for order in order_list[:-1]
        ]
        submit_results.append(
            self._submit_order(
                contract, order_list[-1], parent_id=parent_id, transmit=True
            )
        )

        tracked_list = await asyncio.gather(
            *[
                self.ibsocket.order_tracker.order_update(
                    oid, timeout=timeout or self._timeout
                )
                for oid, placed in submit_results
                if placed
            ]
        ) + [
            self.ibsocket.order_tracker.ensure_existing_order(oid)
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
        parent_id, placed = self._submit_order(
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
            (
                await self.ibsocket.order_tracker.order_update(
                    parent_id, timeout=timeout or self._timeout
                )
            )
            if placed
            else self.ibsocket.order_tracker.ensure_existing_order(parent_id)
        )

        return parent_tracked, children_tracked

    async def placeWhatifOrder(
        self, contract: Contract, order: Order, timeout: float | None = None
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
        order_id = self.ibsocket.order_tracker.next_order_id
        self.ibsocket.placeOrder(order_id, contract, order)
        return await self.ibsocket.order_tracker.order_update(
            order_id, timeout=timeout or self._timeout
        )

    async def cancelOrder(
        self, order_id: int, timeout: float | None = None
    ) -> TrackedOrder:
        """Cancel an order via TWS.

        Args:
            order_id: Order ID to cancel
        """

        self.ibsocket.order_tracker.ensure_existing_order(order_id)
        self.ibsocket.cancelOrder(order_id)
        return await self.ibsocket.order_tracker.order_update(
            order_id, timeout=timeout or self._timeout
        )

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

        self.ibsocket.reqOpenOrders()

        return await self.ibsocket.order_tracker.all_orders(
            timeout=timeout or self._timeout
        )

    async def reqPositions(self, timeout: float | None = None) -> list[TrackedPosition]:
        """Request all positions for this client (snapshot).

        Returns positions for all accounts. Each position triggers
        position() callback, then positionEnd().

        Args:
            timeout: Request timeout in seconds

        Returns:
            List of TrackedPosition objects (one per position)
        """
        self.ibsocket.reqPositions()

        return await self.ibsocket.position_tracker.all_positions(
            timeout=timeout or self._timeout
        )

    async def reqAccountSummary(
        self, timeout: float | None = None
    ) -> list[TrackedAccount]:
        """Request all positions for this client (snapshot).

        Returns positions for all accounts. Each position triggers
        position() callback, then positionEnd().

        Args:
            timeout: Request timeout in seconds

        Returns:
            List of TrackedPosition objects (one per position)
        """
        self.ibsocket.reqAccountSummary()

        return await self.ibsocket.account_tracker.all_accounts(
            timeout=timeout or self._timeout
        )

    # === Real-time broker subscriptions ===

    def reqOrdersStream(
        self,
        callback: Callable[[TrackedOrder], Coroutine[Any, Any, None]],
        on_error: Callable[[ProviderException], Coroutine[Any, Any, None]],
    ) -> str:
        """Create order stream subscription.

        Returns stream_key for later unsubscription.
        """
        # 1. Register with OrderTracker
        stream_key = self.ibsocket.order_tracker.create_stream_hook(
            asyncio.get_event_loop(),
            callback,
            on_error,
        )

        # 2. Trigger initial snapshot (existing orders)
        self.ibsocket.reqOpenOrders()

        return stream_key

    def reqPositionsStream(
        self,
        callback: Callable[[TrackedPosition], Coroutine[Any, Any, None]],
        on_error: Callable[[ProviderException], Coroutine[Any, Any, None]],
    ) -> str:
        """Create position stream subscription.

        Returns stream_key for later unsubscription.
        """
        # 1. Register with PositionTracker
        stream_key = self.ibsocket.position_tracker.create_stream_hook(
            asyncio.get_event_loop(),
            callback,
            on_error,
        )

        # 2. Trigger initial snapshot (existing orders)
        self.ibsocket.reqPositions()

        return stream_key

    def reqAccountStream(
        self,
        callback: Callable[[TrackedAccount], Coroutine[Any, Any, None]],
        on_error: Callable[[ProviderException], Coroutine[Any, Any, None]],
    ) -> str:
        # 1. Register with AccountTracker
        stream_key = self.ibsocket.account_tracker.create_stream_hook(
            asyncio.get_event_loop(),
            callback,
            on_error,
        )

        # 2. Trigger initial snapshot (existing orders)
        self.ibsocket.reqAccountSummary()

        return stream_key

    def cancel_broker_stream(self, stream_key: str) -> None:
        """Cancel a real-time broker subscription (orders, positions, or accounts)."""
        self.ibsocket.order_tracker.remove_stream_hook(stream_key)
        self.ibsocket.position_tracker.remove_stream_hook(stream_key)
        self.ibsocket.account_tracker.remove_stream_hook(stream_key)

        # Cancel underlying TWS subscriptions if this was an account stream
        # TODO: Track stream_key → pnl_req_id mapping to cancel P&L subscription
        # self.ibsocket.cancelAccountSubscriptions(pnl_req_id)

    def shutdown(self) -> None:
        """Shutdown the TWSClient and underlying IBSocket."""
        self.__ibsocket.disconnect()
