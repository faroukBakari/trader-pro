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
from collections.abc import Awaitable
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
from ibapi.errors import FAIL_CREATE_SOCK
from ibapi.message import OUT
from ibapi.protobuf.ErrorMessage_pb2 import ErrorMessage as ErrorMessageProto
from ibapi.ticktype import TickTypeEnum
from ibapi.wrapper import EWrapper, current_fn_name

from .tws_models import TICK_TYPE_TO_FIELD, RTMarketData, TWSError, get_asset_config

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


def get_duration_for_bars(barSize_setting: str, num_bars: int = 2) -> str:
    """Convert bar size to duration string for N bars."""
    # Map bar size to seconds
    secs = BAR_2_DURATION.get(barSize_setting, 86400)
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


# TODO REDESIGN SOCKET STATE MANAGEMENT!!! NEED TO USE FLAG INSTEAD OS SOCKET METHODS
class IBSocket:
    def __init__(
        self, soc: socket | None = None, loc: "threading.Lock | None" = None
    ) -> None:
        self._server_version: int = 203
        self.connection_time: str = ""
        self._req_id_counter = count()
        self._lock = loc or threading.Lock()
        self._reader_thread: threading.Thread | None = None
        self._state = IBSocketState.READY
        try:
            self._socket = soc or socket()
        except socketError:
            logger.error(
                NO_VALID_ID,
                round(time.time() * 1000),
                FAIL_CREATE_SOCK.code(),
                FAIL_CREATE_SOCK.msg(),
            )

    @property
    def server_version(self) -> int:
        return self._server_version

    @property
    def next_req_id(self) -> int:
        return next(self._req_id_counter)

    @property
    def ready(self) -> bool:
        return self._state == IBSocketState.READY

    @property
    def running(self) -> bool:
        return self._state == IBSocketState.RUNNING

    @property
    def closed(self) -> bool:
        return self._state == IBSocketState.CLOSED

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
        except socketError as e:
            logger.exception(f"Socket error while checking remote closure: {e}")
            return True  # Assume closed on error

    def _receive_data(
        self, read_buf: bytearray, buf_siz: int = 0
    ) -> tuple[int, bytes, bytearray, int]:
        """Optimized receive - called in hot path from _reader_loop."""
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

    def _reader_loop(self, cb_wrapper: EWrapper) -> None:
        """TWS reader loop - to be run in a separate thread.

        Note:
            This method should be called in a dedicated thread to continuously
            read messages from the IBSocket connection and dispatch them to
            the appropriate EWrapper callback methods.
        """

        if self._state != IBSocketState.CONNECTED:
            self._state = IBSocketState.ERROR
            raise RuntimeError("_reader_loop Startup error : Socket not connected.")

        decoder = Decoder(cb_wrapper, self.server_version)
        debug_log("IBSocket reader loop started.")

        # Cache method references for hot path (avoid attribute lookup per iteration)
        recv = self._receive_data
        process_proto = decoder.processProtoBuf
        interpret = decoder.interpret

        buf = bytearray()
        buf_siz = 0
        self._state = IBSocketState.RUNNING
        running = True
        while running:
            try:
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
                    logger.error("IBSocket connection closed remotely.")
                    self._state = IBSocketState.ERROR
                    break
                logger.exception(
                    "Unexpected exception in IBSocket reader loop (running: %d): %s",
                    running,
                    e,
                )
                time.sleep(0.5)

        debug_log("IBSocket reader loop finished.")

    def connect(
        self,
        host: str,
        port: int,
        client_id: int,
        cb_wrapper: EWrapper,
        block_interval: float = 0.01,
    ) -> threading.Thread:
        assert self.ready, "Socket already used!"

        self._state = IBSocketState.CONNECTING
        nb_retries = 3
        while nb_retries > 0:
            try:
                with self._lock:
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
        with self._lock:
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

        server_version, self.connection_time = [msg.decode("ascii") for msg in fields]
        self._server_version = int(server_version)
        debug_log(
            f"Server version: {self.server_version}, Connection time: {self.connection_time}"
        )
        text = make_fields([VERSION, client_id, ""])
        msg2 = (
            (len(text) + 4).to_bytes(4, "big") + OUT.START_API.to_bytes(4, "big") + text
        )
        with self._lock:
            self._socket.sendall(msg2)
        debug_log("IBSocket connection successfully.")

        self._state = IBSocketState.CONNECTED
        self._reader_thread = threading.Thread(
            target=self._reader_loop,
            args=(cb_wrapper,),
            daemon=False,
        )
        self._reader_thread.start()
        return self._reader_thread

    def disconnect(self) -> None:
        try:
            with self._lock:
                self._socket.close()
                self._state = IBSocketState.CLOSED
                # debug_log("IBSocket Socket closed.")
        except Exception as e:
            logger.exception(f"Error while closing IBSocket: {e}")

    def send_message(self, msgId: int, values: list[object]) -> None:
        text = make_fields(values)
        msg2 = (len(text) + 4).to_bytes(4, "big") + msgId.to_bytes(4, "big") + text
        if DEBUG_TWS_SEND:
            debug_log(f"Sending message: {str(msg2)}")
        assert self._state == IBSocketState.RUNNING, "Socket is not connected."
        with self._lock:
            self._socket.sendall(msg2)

    def __del__(self) -> None:
        try:
            self.disconnect()
        except Exception:
            pass


class TWSCallback(EWrapper):
    """TWSClient helper base class - enables mock injection for testing.

    Inherits EWrapper for callback methods.
    Manages asyncio.Future registry for request/response patterns.
    Uses _accumulators for streaming accumulation pattern (multiple callbacks → single result).
    Uses _sub_queues for continuous subscription pattern (realtime bars, market data).
    """

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        """Initialize TWSCallback (pure callback handler).

        Note: No EClient instance - caller must provide via composition.
        """
        self._loop = loop or asyncio.get_event_loop()
        self._futures: dict[int, tuple[asyncio.AbstractEventLoop, asyncio.Future]] = {}
        self._accumulators: dict[int, Any] = {}
        self._req_id_to_ticker_map: dict[int, RTMarketData] = {}
        self._nxt_order_id: int | None = None
        self._accounts: list[str] = []
        self._ready_event = threading.Event()  # Signals when nextValidId received

    def dispatchMessage(self, fnName: str, fnParams: dict) -> None:
        if DEBUG_TWS_DISPATCH:
            if "self" in fnParams:
                fnParams = dict(fnParams)
                del fnParams["self"]
            debug_log(f"!!!WARNING!!!: unimplemented {fnName} --> {fnParams}")

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        return asyncio.get_event_loop()

    # === Future / Coroutine management ===

    def reset(self) -> None:
        """Reset internal state - clear futures, accumulators, callbacks."""
        self._futures.clear()
        self._accumulators.clear()
        self._nxt_order_id = None
        self._accounts.clear()
        self._ready_event.clear()

    def create_future(self, reqId: int, timeout: float | None = 5) -> Awaitable[Any]:
        """Create a new Future attached to the current event loop."""
        future: asyncio.Future[Any] = self.loop.create_future()
        self._futures[reqId] = (self.loop, future)
        self._accumulators[reqId] = []
        return asyncio.wait_for(future, timeout)

    def _resolve_future(self, reqId: int) -> None:
        """Helper to resolve a future in the asyncio loop."""
        results = self._accumulators.pop(reqId, [])
        if results is None:
            logger.error(f"Accumulator not found for reqId {reqId}")
            self._futures.pop(reqId, (None, None))
            return
        loop, future = self._futures.pop(reqId, (None, None))
        if loop is None or future is None or future.done():
            logger.error(f"future/loop not found or already done for reqId {reqId}.")
            return
        loop.call_soon_threadsafe(future.set_result, results)

    def _reject_future(self, reqId: int, exception: Exception) -> None:
        """Helper to reject a future with an exception in the asyncio loop."""
        loop, future = self._futures.pop(reqId, (None, None))
        if loop is None or future is None or future.done():
            logger.error(f"future/loop not found or already done for reqId {reqId}.")
            return
        loop.call_soon_threadsafe(future.set_exception, exception)

    # === Ticker management ===

    def register_ticker(self, rt_data: RTMarketData) -> RTMarketData:
        """Create and register a new RTMarketData slot for a reqId."""
        for reqId in [rt_data.bar_data_reqId, rt_data.mkt_data_reqId]:
            if reqId is not None:
                self._req_id_to_ticker_map[reqId] = rt_data
        return rt_data

    def unregister_ticker(self, ticker: RTMarketData) -> None:
        """Remove RTMarketData slot and associated reqIds."""
        for reqId in [ticker.bar_data_reqId, ticker.mkt_data_reqId]:
            if reqId is not None:
                self._req_id_to_ticker_map.pop(reqId, None)

    def _notify_ticker(
        self, ticker: RTMarketData, updated_fields: list[str] | None = None
    ) -> None:
        """Trigger ticker callbacks if registered."""
        # TODO: this is very unsafe!!
        # asyncio loop is acting as a queue here, need to redesign this part
        # need to sync callbacks with the main thread ability to handle messages!!
        for key, (loop, callback) in ticker.reqId_callback_map.items():
            if DEBUG_TWS_CALLBACK:
                assert ticker.contract is not None, "Ticker contract is None."
                debug_log(
                    f"_notify_ticker callback {key} with fields: {updated_fields}"
                )
            loop.call_soon_threadsafe(loop.create_task, callback(ticker, updated_fields))  # type: ignore

    # === Trading / account management ===

    def managedAccounts(self, accountsList: str) -> None:
        if DEBUG_TWS_CALLBACK:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")
        # should be sent upon connection
        self._accounts = accountsList.split(",")

    def nextValidId(self, orderId: int) -> None:
        if DEBUG_TWS_CALLBACK:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")
        # Signals connection fully established - safe to make requests
        self._nxt_order_id = orderId
        self._ready_event.set()

    # === symbolSamples ===

    def symbolSamples(
        self, reqId: int, contractDescriptions: list[ContractDescription]
    ) -> None:
        if DEBUG_TWS_CALLBACK:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")
        accumulator = self._accumulators.get(reqId)
        if isinstance(accumulator, list):
            accumulator.extend(contractDescriptions)
            self._resolve_future(reqId)

    # === contractDetails (streaming accumulation pattern) ===

    def contractDetails(self, reqId: int, contractDetails: ContractDetails) -> None:
        """Accumulate contract details (may be called multiple times).

        TWS sends one contractDetails callback per matching contract.
        Results are accumulated until contractDetailsEnd is called.
        """
        if DEBUG_TWS_CALLBACK:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")
        accumulator = self._accumulators.get(reqId)
        if isinstance(accumulator, list):
            accumulator.append(contractDetails)

    def contractDetailsEnd(self, reqId: int) -> None:
        """End signal for contract details - resolve Future with accumulated results."""
        if DEBUG_TWS_CALLBACK:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")
        self._resolve_future(reqId)

    # === historicalData (streaming accumulation pattern) ===

    def historicalData(self, reqId: int, bar: BarData) -> None:
        """Accumulate historical bars (may be called multiple times).

        TWS sends one historicalData callback per bar.
        Results are accumulated until historicalDataEnd is called.
        """
        if DEBUG_TWS_CALLBACK:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")
        accumulator = self._accumulators.get(reqId)
        if isinstance(accumulator, list):
            accumulator.append(bar)
        else:
            debug_log(f"No accumulator found for reqId {reqId}")
            self.historicalDataUpdate(reqId, bar)

    def historicalDataUpdate(self, reqId: int, bar: BarData) -> None:
        """Returns updates in real time when keepUpToDate is set to True.

        Only updates fields if current value is None or different from new value.
        Only notifies callbacks if at least one field actually changed.
        """
        if DEBUG_TWS_CALLBACK:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")

        # 1. Update RTMarketData ticker bar fields if tracked
        ticker = self._req_id_to_ticker_map.get(reqId)
        if ticker is not None:
            updated_fields: list[str] = []

            # Field mapping: (ticker_attr, bar_attr, transform)
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
                current_value = getattr(ticker, field_name)
                if current_value is None or not (
                    math.isclose(current_value, new_value, abs_tol=1e-3)
                    if isinstance(new_value, float)
                    else current_value == new_value
                ):
                    setattr(ticker, field_name, new_value)
                    updated_fields.append(field_name)

            # Only notify if at least one field changed
            if updated_fields:
                self._notify_ticker(ticker, updated_fields)
        else:
            debug_log(f"No ticker found for reqId {reqId}")

    def historicalDataEnd(self, reqId: int, start: str, end: str) -> None:
        """End signal for historical data - resolve Future with accumulated results."""
        if DEBUG_TWS_CALLBACK:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")
        self._resolve_future(reqId)

    # === Market data (accumulation pattern) ===

    def tickPrice(
        self, reqId: int, tickType: int, price: float, attrib: TickAttrib
    ) -> None:
        """Accumulate price ticks for market data snapshot.

        Called multiple times per snapshot with different tick types.
        Results accumulated until tickSnapshotEnd is called.
        """
        ticker = self._req_id_to_ticker_map.get(reqId)
        assert ticker is not None, f"No RTMarketData found for tickerId {reqId}"
        tick_name = get_tick_type_name(tickType)
        assert tick_name is not None, "Tick name must not be None"
        field_name = TICK_TYPE_TO_FIELD.get(tick_name)
        assert field_name is not None, "Field name must not be None"
        current_value: float | None = getattr(ticker, field_name, None)
        if DEBUG_TWS_CALLBACK:
            assert ticker.contract is not None, "Ticker contract is None."
            debug_log(
                f"tickPrice: reqId=[{reqId}], ticker=[{ticker.contract.symbol}:{ticker.contract.exchange}], "
                f"field_name=[{field_name}], price=[{current_value} -> {price}]"
            )
        if current_value is None or not math.isclose(
            current_value, price, abs_tol=1e-3
        ):
            setattr(ticker, field_name, price)
            fields = [field_name]
            if field_name in ["last", "close"]:
                ticker.bar_close = price
                fields.append("bar_close")
            self._notify_ticker(ticker, fields)

    def tickSize(self, reqId: int, tickType: int, size: Decimal) -> None:
        """Accumulate size ticks for market data snapshot.

        Called multiple times per snapshot with different tick types.
        Results accumulated until tickSnapshotEnd is called.
        """

        ticker = self._req_id_to_ticker_map.get(reqId)
        assert ticker is not None, f"No RTMarketData found for tickerId {reqId}"
        tick_name = get_tick_type_name(tickType)
        assert tick_name is not None, "Tick name must not be None"
        field_name = TICK_TYPE_TO_FIELD.get(tick_name)
        assert field_name is not None, "Field name must not be None"
        current_value: float | None = getattr(ticker, field_name, None)
        if DEBUG_TWS_CALLBACK:
            assert ticker.contract is not None, "Ticker contract is None."
            debug_log(
                f"tickSize: reqId=[{reqId}], ticker=[{ticker.contract.symbol}:{ticker.contract.exchange}], "
                f"field_name=[{field_name}], size=[{current_value} -> {size}]"
            )
        if current_value is None or not math.isclose(current_value, size, abs_tol=1e-3):
            setattr(ticker, field_name, size)
            self._notify_ticker(ticker, [field_name])

    def marketDataType(self, reqId: int, marketDataType: int) -> None:
        """Set market data type for the request."""
        if DEBUG_TWS_CALLBACK:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")

        ticker = self._req_id_to_ticker_map.get(reqId)
        assert ticker is not None, f"No RTMarketData found for tickerId {reqId}"

        current_val: int | None = ticker.market_data_type

        if DEBUG_TWS_CALLBACK:
            assert ticker.contract is not None, "Ticker contract is None."
            debug_log(
                f"marketDataType: reqId=[{reqId}], ticker=[{ticker.contract.symbol}:{ticker.contract.exchange}], "
                f"field_name=[market_data_type], value=[{current_val} -> {marketDataType}]"
            )
        if current_val is None or current_val != marketDataType:
            ticker.market_data_type = marketDataType
            self._notify_ticker(ticker, ["market_data_type"])

    def tickReqParams(
        self, tickerId: int, minTick: float, bboExchange: str, snapshotPermissions: int
    ) -> None:
        """returns exchange map of a particular contract"""
        if DEBUG_TWS_CALLBACK:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")

        ticker = self._req_id_to_ticker_map.get(tickerId)
        assert ticker is not None, f"No RTMarketData found for tickerId {tickerId}"

        current_minTick: float | None = ticker.min_tick
        current_bboExchange: str | None = ticker.bbo_exchange
        current_snapshotPermissions: int | None = ticker.snapshot_permissions
        update_list: list[str] = []
        if current_minTick is None or math.isclose(
            current_minTick, minTick, abs_tol=1e-6
        ):
            update_list.append("min_tick")
            ticker.min_tick = minTick

        if current_bboExchange is None or current_bboExchange != bboExchange:
            update_list.append("bbo_exchange")
            ticker.bbo_exchange = bboExchange

        if (
            current_snapshotPermissions is None
            or current_snapshotPermissions != snapshotPermissions
        ):
            update_list.append("snapshot_permissions")
            ticker.snapshot_permissions = snapshotPermissions

        if DEBUG_TWS_CALLBACK:
            assert ticker.contract is not None, "Ticker contract is None."
            debug_log(
                f"tickReqParams: reqId=[{tickerId}], ticker=[{ticker.contract.symbol}:{ticker.contract.exchange}], "
                f"field_name=[min_tick], size=[{current_minTick} -> {minTick}]"
                f"field_name=[bbo_exchange], size=[{current_bboExchange} -> {bboExchange}]"
                f"field_name=[snapshot_permissions], size=[{current_snapshotPermissions} -> {snapshotPermissions}]"
            )

        if update_list:
            self._notify_ticker(ticker, update_list)

    def tickString(self, reqId: int, tickType: int, value: str) -> None:
        """Generic string tick for market data snapshot."""
        if DEBUG_TWS_CALLBACK:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")

        ticker = self._req_id_to_ticker_map.get(reqId)
        assert ticker is not None, f"No RTMarketData found for tickerId {reqId}"
        tick_name = get_tick_type_name(tickType)
        assert tick_name is not None, "Tick name must not be None"
        field_name = TICK_TYPE_TO_FIELD.get(tick_name)
        assert field_name is not None, "Field name must not be None"
        current_value: str | None = getattr(ticker, field_name, None)
        if DEBUG_TWS_CALLBACK:
            assert ticker.contract is not None, "Ticker contract is None."
            debug_log(
                f"tickString: reqId=[{reqId}], ticker=[{ticker.contract.symbol}:{ticker.contract.exchange}], "
                f"field_name=[{field_name}], value=[{current_value} -> {value}]"
            )
        if current_value is None or current_value != value:
            setattr(ticker, field_name, value)
            self._notify_ticker(ticker, [field_name])

    def tickGeneric(self, reqId: int, tickType: int, value: float) -> None:
        """Generic float tick for market data snapshot."""
        if DEBUG_TWS_CALLBACK:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")

        ticker = self._req_id_to_ticker_map.get(reqId)
        assert ticker is not None, f"No RTMarketData found for tickerId {reqId}"
        tick_name = get_tick_type_name(tickType)
        assert tick_name is not None, "Tick name must not be None"
        field_name = TICK_TYPE_TO_FIELD.get(tick_name)
        assert field_name is not None, "Field name must not be None"
        current_value: float | None = getattr(ticker, field_name, None)
        if DEBUG_TWS_CALLBACK:
            assert ticker.contract is not None, "Ticker contract is None."
            debug_log(
                f"tickGeneric: reqId=[{reqId}], ticker=[{ticker.contract.symbol}:{ticker.contract.exchange}], "
                f"field_name=[{field_name}], value=[{current_value} -> {value}]"
            )
        if current_value is None or not math.isclose(
            current_value, value, abs_tol=1e-3
        ):
            setattr(ticker, field_name, value)
            self._notify_ticker(ticker, [field_name])

    def tickSnapshotEnd(self, reqId: int) -> None:
        """End signal for market data snapshot - resolve Future with accumulated ticks.

        Called ~11 seconds after reqMktData with snapshot=True.
        Resolves Future with dict containing "prices" and "sizes" mappings.
        """
        if DEBUG_TWS_CALLBACK:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")
        ticker = self._req_id_to_ticker_map.get(reqId)
        if ticker is not None:
            ticker.reset()
            self._notify_ticker(ticker)

    # === error handling ===

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
        tws_error = TWSError(
            reqId=reqId,
            errorTime=errorTime,
            errorCode=errorCode,
            errorString=errorString,
            advancedOrderRejectJson=advancedOrderRejectJson,
        )

        # 1. Store error in RTMarketData ticker if tracked
        ticker = self._req_id_to_ticker_map.get(reqId)
        if ticker is not None:
            assert (
                ticker.contract is not None
            ), "Ticker contract must be set for error logging."
            logger.error(
                f"TWS rt data error [symbol= [{ticker.contract.symbol}:{ticker.contract.exchange}] "
                f"reqId={reqId}, time={errorTime}, code={errorCode}]: {errorString}"
            )
            ticker.error_messages.append(tws_error)
            return

        # 2. Handle error (existing behavior)
        if reqId == -1:
            logger.error(
                f"TWS error [reqId={reqId}, time={errorTime}, code={errorCode}]: {errorString}"
            )
            return

        self._reject_future(reqId, tws_error)

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
        loop: asyncio.AbstractEventLoop | None = None,
        timeout: float = 10.0,
    ) -> None:
        """Initialize IBSocket (pure callback handler).

        Note: No EClient instance - caller must provide via composition.
        """
        self._host = host
        self._port = port
        self._client_id = client_id
        self._cb_wrapper = TWSCallback(loop=loop or asyncio.get_event_loop())
        self._timeout = timeout

        self.__ibsocket = IBSocket()

    @property
    def ibsocket(self) -> IBSocket:
        if not self.__ibsocket.running:
            self.__ibsocket.disconnect()
            self.__ibsocket = IBSocket()
            self._cb_wrapper.reset()  # Reset before new connection
            self.__ibsocket.connect(
                host=self._host,
                port=self._port,
                client_id=self._client_id,
                cb_wrapper=self._cb_wrapper,
            )
            # Wait for nextValidId signal (connection fully ready)
            if not self._cb_wrapper._ready_event.wait(timeout=self._timeout):
                raise TimeoutError("Timeout waiting for TWS connection ready signal")
        return self.__ibsocket

    @property
    def next_req_id(self) -> int:
        return self.ibsocket.next_req_id

    async def reqMatchingSymbols(
        self, pattern: str, timeout: float | None = None
    ) -> list[ContractDescription]:
        reqId = self.next_req_id

        coroutine: Awaitable[
            list[ContractDescription]
        ] = self._cb_wrapper.create_future(reqId, timeout=timeout or self._timeout)
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
        coroutine: Awaitable[list[ContractDetails]] = self._cb_wrapper.create_future(
            reqId, timeout=timeout or self._timeout
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
        barSize_setting: str,
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
            barSize_setting: Bar size ("1 min", "5 mins", "1 hour", "1 day")
            whatToShow: Data type (default: "TRADES")
            useRTH: 1=regular hours only, 0=all hours (default: 1)
            format_date: 1=string format, 2=epoch (default: 1)

        Returns:
            List of BarData objects (one per bar, in ascending time order)
        """
        reqId = self.next_req_id
        coroutine: Awaitable[list[BarData]] = self._cb_wrapper.create_future(
            reqId,
            timeout=timeout or self._timeout,
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
            barSize_setting,
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
                f"symbol='{contract.symbol}', duration='{duration_str}', barSize='{barSize_setting}'"
            )
        return await coroutine

    # === Real-time bar subscriptions (continuous pattern) ===

    def create_ticker(
        self,
        contract: Contract,
        barSize_setting: str,
        **kwargs: Any,
    ) -> RTMarketData:
        """Create a real-time data subscription (stub for future use)."""

        bar_data_reqId = self.next_req_id
        mkt_data_reqId = self.next_req_id

        ticker = RTMarketData()

        ticker.bar_data_reqId = bar_data_reqId
        ticker.mkt_data_reqId = mkt_data_reqId
        ticker.contract = contract
        ticker.barSize_setting = barSize_setting
        ticker.format_date = 1

        ticker = self._cb_wrapper.register_ticker(ticker)

        # Get asset-type-specific configuration
        asset_config = get_asset_config(contract.secType)

        end_date_time: str = ""
        duration_str: str = get_duration_for_bars(barSize_setting)
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
            barSize_setting,
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
                f"symbol='{contract.symbol}', duration='{duration_str}', barSize='{barSize_setting}'"
            )
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

        return ticker

    def switch_ticker_resolution(
        self,
        ticker: RTMarketData,
        barSize_setting: str,
        **kwargs: Any,
    ) -> RTMarketData:
        """Create a real-time data subscription (stub for future use)."""

        VERSION = 1
        self.ibsocket.send_message(
            OUT.CANCEL_HISTORICAL_DATA, [VERSION, ticker.bar_data_reqId]
        )
        if DEBUG_TWS_REQUEST:
            debug_log(f"cancelled realtime bars for reqId {ticker.bar_data_reqId}")

        self._cb_wrapper.unregister_ticker(ticker)

        ticker.bar_data_reqId = self.next_req_id
        ticker.barSize_setting = barSize_setting

        self._cb_wrapper.register_ticker(ticker)

        contract = ticker.contract
        assert contract is not None, "Ticker contract must be set to switch resolution."

        # Get asset-type-specific configuration
        asset_config = get_asset_config(contract.secType)

        end_date_time: str = ""
        duration_str: str = get_duration_for_bars(barSize_setting)
        # Use what_to_show_live since keepUpToDate=True (live data)
        whatToShow: str = asset_config.what_to_show_live
        format_date: int = 1
        useRTH: int = 0
        keepUpToDate: int = 1

        bar_data_fields: list[object] = [
            ticker.bar_data_reqId,
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
            barSize_setting,
            duration_str,
            useRTH,
            whatToShow,
            format_date,
            keepUpToDate,
            [],  # chartOptions (empty list)
        ]

        self.ibsocket.send_message(OUT.REQ_HISTORICAL_DATA, bar_data_fields)
        if DEBUG_TWS_REQUEST:
            debug_log(
                f"subscribed to bar data for reqId {ticker.bar_data_reqId}, "
                f"symbol='{contract.symbol}', duration='{duration_str}', barSize='{barSize_setting}'"
            )

        return ticker

    def remove_ticker(self, ticker: RTMarketData) -> RTMarketData:
        """Cancel a real-time data subscription."""

        VERSION = 1
        if ticker.bar_data_reqId is not None:
            self.ibsocket.send_message(
                OUT.CANCEL_HISTORICAL_DATA, [VERSION, ticker.bar_data_reqId]
            )
            if DEBUG_TWS_REQUEST:
                debug_log(f"cancelled realtime bars for reqId {ticker.bar_data_reqId}")

        VERSION = 2
        if ticker.mkt_data_reqId is not None:
            self.ibsocket.send_message(
                OUT.CANCEL_MKT_DATA, [VERSION, ticker.mkt_data_reqId]
            )
            if DEBUG_TWS_REQUEST:
                debug_log(f"cancelled market data for reqId {ticker.mkt_data_reqId}")

        self._cb_wrapper.unregister_ticker(ticker)
        ticker.reset()

        return ticker

    def shutdown(self) -> None:
        """Shutdown the TWSClient and underlying IBSocket."""
        self.__ibsocket.disconnect()
