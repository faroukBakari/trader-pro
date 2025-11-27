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
import os
import select
import struct
import threading
import time
from collections.abc import Awaitable
from dataclasses import dataclass
from decimal import Decimal
from itertools import count
from socket import MSG_PEEK
from socket import error as socketError
from socket import socket
from socket import timeout as socketTimeout
from tkinter import NO
from typing import Any, Callable

from ibapi.common import BarData, TickAttrib
from ibapi.const import DOUBLE_INFINITY, INFINITY_STR, UNSET_DOUBLE, UNSET_INTEGER
from ibapi.contract import Contract, ContractDescription, ContractDetails
from ibapi.decoder import Decoder
from ibapi.errors import CONNECT_FAIL, FAIL_CREATE_SOCK
from ibapi.message import OUT
from ibapi.protobuf.ErrorMessage_pb2 import ErrorMessage as ErrorMessageProto
from ibapi.ticktype import TickTypeEnum
from ibapi.wrapper import EWrapper, current_fn_name
from numpy import isin

logger = logging.getLogger(__name__)
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
            return "".join(to_str(item) for item in val)

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


get_tick_type_name = TickTypeEnum.idx2name.get
debug_log = logger.debug


class IBSocket:
    def __init__(
        self, soc: socket | None = None, loc: "threading.Lock | None" = None
    ) -> None:
        self._server_version: int = 203
        self.connection_time: str = ""
        self._req_id_counter = count()
        self._lock = loc or threading.Lock()
        self._reader_thread: threading.Thread | None = None
        try:
            self._socket = soc or socket()
        except socketError:
            logger.error(
                NO_VALID_ID,
                round(time.time() * 1000),
                FAIL_CREATE_SOCK.code(),
                FAIL_CREATE_SOCK.msg(),
            )

    def __del__(self) -> None:
        self.disconnect()

    @property
    def server_version(self) -> int:
        return self._server_version

    @property
    def next_req_id(self) -> int:
        return next(self._req_id_counter)

    @property
    def ready(self) -> bool:
        if self._socket.fileno() == -1:
            return False
        try:
            return self._socket.getpeername() is None
        except OSError:
            return True

    @property
    def running(self) -> bool:
        if self._socket.fileno() == -1:
            return False
        try:
            r, _, _ = select.select([self._socket], [], [], 0)
            if r:
                data = self._socket.recv(1, MSG_PEEK)
                return data != b""
            return True
        except OSError:
            return False

    @property
    def closed(self) -> bool:
        if self._socket.fileno() == -1:
            return True
        try:
            r, _, _ = select.select([self._socket], [], [], 0)
            if r:
                data = self._socket.recv(1, MSG_PEEK)
                return data == b""
            return False
        except OSError:
            return False

    def _reader_loop(self, cb_wrapper: EWrapper) -> None:
        """TWS reader loop - to be run in a separate thread.

        Note:
            This method should be called in a dedicated thread to continuously
            read messages from the IBSocket connection and dispatch them to
            the appropriate EWrapper callback methods.
        """
        decoder = Decoder(cb_wrapper, self.server_version)
        logger.info("IBSocket reader loop started.")

        # Cache method references for hot path (avoid attribute lookup per iteration)
        recv = self.receive_data
        process_proto = decoder.processProtoBuf
        interpret = decoder.interpret

        buf = bytearray()
        buf_siz = 0
        running = self.running
        while running:
            try:
                msgId, data, buf, buf_siz = recv(buf, buf_siz)
                if msgId == -1:
                    # Incomplete message - only log if debugging enabled
                    if buf_siz > 0 and logger.isEnabledFor(logging.WARNING):
                        logger.warning(
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
            except (socketError, socketTimeout) as e:
                running = self.running
                logger.exception("Socket exception in reader loop: %s", e)
                time.sleep(0.5)
            except Exception as e:
                running = self.running
                logger.exception(
                    "Unexpected exception in IBSocket reader loop (running: %d): %s",
                    running,
                    e,
                )
                time.sleep(0.5)

        logger.info("IBSocket reader loop finished.")

    def connect(
        self,
        host: str,
        port: int,
        client_id: int,
        cb_wrapper: EWrapper,
        block_interval: float = 0.01,
    ) -> threading.Thread:
        assert self.ready, "Socket already used!"

        with self._lock:
            while True:
                try:
                    self._socket.connect((host, port))
                    self._socket.settimeout(block_interval)
                    break
                except socketError:
                    cb_wrapper.error(
                        NO_VALID_ID,
                        round(time.time() * 1000),
                        CONNECT_FAIL.code(),
                        CONNECT_FAIL.msg(),
                    )
                except Exception as e:
                    cb_wrapper.error(
                        reqId=-1,
                        errorTime=int(time.time() * 1000),
                        errorCode=getattr(e, "errno", -1),
                        errorString=str(e),
                    )
                time.sleep(1)
            connected = self.running
            assert connected, "Socket connection failed."
            logger.info(f"Socket connected: {connected}: {self._socket.getpeername()}")

            # Send initial handshake message
            v100version = "v%d..%d" % (MIN_CLIENT_VER, MAX_CLIENT_VER)
            msg_content = len(v100version).to_bytes(4, "big") + v100version.encode()
            message = str.encode("API\0", "ascii") + msg_content
            self._socket.sendall(message)
            if DEBUG_TWS_SEND:
                debug_log(f"Sent initial message: {str(message)}")
            nb_retries = 3
            while True:
                try:
                    data = self._socket.recv(4096)
                    break
                except socketTimeout:
                    nb_retries -= 1
                    assert nb_retries > 0, f"Error while waiting for handshake response"
                    time.sleep(0.1)
            buf_size = len(data)
            msg_size = HEADER_STRUCT.unpack_from(data, 0)[0]
            if DEBUG_TWS_RECEIVE:
                debug_log(f"Received handshake data: {str(data)}")
            assert (
                msg_size <= buf_size - 4
            ), f"Initial read buffer size exceeds message size: {buf_size}"
            fields = [chunk for chunk in data[4 : 4 + msg_size].split(NULL) if chunk]
            assert len(fields) == 2, "Expected at two fields in handshake message."
            server_version, self.connection_time = [
                msg.decode("ascii") for msg in fields
            ]
            self._server_version = int(server_version)
            debug_log(
                f"Server version: {self.server_version}, Connection time: {self.connection_time}"
            )
            text = make_fields([VERSION, client_id, ""])
            msg2 = (
                (len(text) + 4).to_bytes(4, "big")
                + OUT.START_API.to_bytes(4, "big")
                + text
            )
            self._socket.sendall(msg2)
            connected = self.running
            assert connected, "Socket connection failed."
            logger.info("IBSocket connection successfully.")

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
        finally:
            logger.info("IBSocket Socket closed.")
            if self._reader_thread and self._reader_thread.is_alive():
                logger.info("Waiting for IBSocket reader thread to finish...")
                try:
                    self._reader_thread.join(timeout=2)
                    logger.info("IBSocket reader thread finished gracefully.")
                except Exception:
                    logger.error("Failed to join IBSocket reader thread.")

    def send_message(self, msgId: int, values: list[object]) -> None:
        text = make_fields(values)
        msg2 = (len(text) + 4).to_bytes(4, "big") + msgId.to_bytes(4, "big") + text
        if DEBUG_TWS_SEND:
            debug_log(f"Sending message: {str(msg2)}")
        assert self.running, "Socket is not connected."
        with self._lock:
            self._socket.sendall(msg2)

    def receive_data(
        self, read_buf: bytearray, buf_siz: int = 0
    ) -> tuple[int, bytes, bytearray, int]:
        """Optimized receive - called in hot path from _reader_loop."""
        new_data_received = False
        assert self.running, "Socket is not connected."
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


@dataclass
class TWSError(Exception):
    """TWS API Error with structured error details."""

    reqId: int
    errorCode: int
    errorString: str
    errorTime: int = 0
    advancedOrderRejectJson: str = ""

    def __str__(self) -> str:
        return f"TWS error {self.errorCode} (reqId={self.reqId}): {self.errorString}"


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
        self._callbacks: dict[int, Callable] = {}
        self._accumulators: dict[int, Any] = {}
        self._nxt_order_id: int | None = None
        self._accounts: list[str] = []
        self._ready_event = threading.Event()  # Signals when nextValidId received

    def dispatchMessage(self, fnName: str, fnParams: dict) -> None:
        if "self" in fnParams:
            fnParams = dict(fnParams)
            del fnParams["self"]
        logger.warning(f"!!!WARNING!!!: unimplemented {fnName} --> {fnParams}")

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        return asyncio.get_event_loop()

    # === Future / Coroutine management ===

    def create_future_coroutine(
        self, reqId: int, timeout: float | None = 5
    ) -> Awaitable[Any]:
        """Create a new Future attached to the current event loop."""
        future: asyncio.Future[Any] = self.loop.create_future()
        self._futures[reqId] = (self.loop, future)
        return asyncio.wait_for(future, timeout)

    def _resolve_future(self, reqId: int, result: object) -> None:
        """Helper to resolve a future in the asyncio loop."""
        loop, future = self._futures.pop(reqId, (None, None))
        if loop is not None and future is not None and not future.done():
            loop.call_soon_threadsafe(future.set_result, result)
        else:
            logger.error(f"Unknown reqId {reqId} in _resolve_future.")

    def _reject_future(self, reqId: int, exception: Exception) -> None:
        """Helper to reject a future with an exception in the asyncio loop."""
        loop, future = self._futures.pop(reqId, (None, None))
        if loop is not None and future is not None and not future.done():
            loop.call_soon_threadsafe(future.set_exception, exception)
        else:
            logger.error(f"Unknown reqId {reqId} in _reject_future.")

    def register_callback(self, reqId: int, callback: Callable) -> None:
        """Register a callback for a specific request ID."""
        self._callbacks[reqId] = callback

    def unregister_callback(self, reqId: int) -> None:
        """Unregister a callback for a specific request ID."""
        self._callbacks.pop(reqId, None)

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
        self._resolve_future(reqId, contractDescriptions)

    # === contractDetails (streaming accumulation pattern) ===

    def contractDetails(self, reqId: int, contractDetails: ContractDetails) -> None:
        """Accumulate contract details (may be called multiple times).

        TWS sends one contractDetails callback per matching contract.
        Results are accumulated until contractDetailsEnd is called.
        """
        if DEBUG_TWS_CALLBACK:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")
        accumulator = self._accumulators.setdefault(reqId, [])
        if isinstance(accumulator, list):
            accumulator.append(contractDetails)

    def contractDetailsEnd(self, reqId: int) -> None:
        """End signal for contract details - resolve Future with accumulated results."""
        if DEBUG_TWS_CALLBACK:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")
        results = self._accumulators.pop(reqId, [])
        self._resolve_future(reqId, results)

    # === historicalData (streaming accumulation pattern) ===

    def historicalData(self, reqId: int, bar: BarData) -> None:
        """Accumulate historical bars (may be called multiple times).

        TWS sends one historicalData callback per bar.
        Results are accumulated until historicalDataEnd is called.
        """
        if DEBUG_TWS_CALLBACK:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")
        accumulator = self._accumulators.setdefault(reqId, [])
        if isinstance(accumulator, list):
            accumulator.append(bar)

    def historicalDataUpdate(self, reqId: int, bar: BarData) -> None:
        """returns updates in real time when keepUpToDate is set to True"""
        if DEBUG_TWS_CALLBACK:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")
        accumulator = self._accumulators.setdefault(reqId, [])
        if isinstance(accumulator, list):
            accumulator.append(bar)

    def historicalDataEnd(self, reqId: int, start: str, end: str) -> None:
        """End signal for historical data - resolve Future with accumulated results."""
        if DEBUG_TWS_CALLBACK:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")
        results = self._accumulators.pop(reqId, [])
        self._resolve_future(reqId, results)

    # === Market data snapshot (accumulation pattern) ===

    def tickPrice(
        self, reqId: int, tickType: int, price: float, attrib: TickAttrib
    ) -> None:
        """Accumulate price ticks for market data snapshot.

        Called multiple times per snapshot with different tick types.
        Results accumulated until tickSnapshotEnd is called.
        """
        if DEBUG_TWS_CALLBACK:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")
        accumulator = self._accumulators.setdefault(reqId, {})
        accumulator[get_tick_type_name(tickType, f"UNKNOWN_{tickType}")] = price
        callback = self._callbacks.get(reqId, None)
        if callback is not None:
            callback(accumulator)

    def tickSize(self, reqId: int, tickType: int, size: Decimal) -> None:
        """Accumulate size ticks for market data snapshot.

        Called multiple times per snapshot with different tick types.
        Results accumulated until tickSnapshotEnd is called.
        """
        if DEBUG_TWS_CALLBACK:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")
        accumulator = self._accumulators.setdefault(reqId, {})
        accumulator[get_tick_type_name(tickType, f"UNKNOWN_{tickType}")] = int(size)
        callback = self._callbacks.get(reqId, None)
        if callback is not None:
            callback(accumulator)

    def marketDataType(self, reqId: int, marketDataType: int) -> None:
        """Set market data type for the request."""
        if DEBUG_TWS_CALLBACK:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")
        accumulator = self._accumulators.setdefault(reqId, {})
        accumulator["marketDataType"] = marketDataType
        callback = self._callbacks.get(reqId, None)
        if callback is not None:
            callback(accumulator)

    def tickReqParams(
        self, tickerId: int, minTick: float, bboExchange: str, snapshotPermissions: int
    ) -> None:
        """returns exchange map of a particular contract"""
        if DEBUG_TWS_CALLBACK:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")
        accumulator = self._accumulators.setdefault(tickerId, {})
        accumulator["minTick"] = minTick
        accumulator["bboExchange"] = bboExchange
        accumulator["snapshotPermissions"] = snapshotPermissions
        callback = self._callbacks.get(tickerId)
        if callback is not None:
            callback(accumulator)

    def tickString(self, reqId: int, tickType: int, value: str) -> None:
        """Generic string tick for market data snapshot."""
        if DEBUG_TWS_CALLBACK:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")
        accumulator = self._accumulators.setdefault(reqId, {})
        accumulator[get_tick_type_name(tickType, f"UNKNOWN_{tickType}")] = value
        callback = self._callbacks.get(reqId, None)
        if callback is not None:
            callback(accumulator)

    def tickGeneric(self, reqId: int, tickType: int, value: float) -> None:
        """Generic float tick for market data snapshot."""
        if DEBUG_TWS_CALLBACK:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")
        accumulator = self._accumulators.setdefault(reqId, {})
        accumulator[get_tick_type_name(tickType, f"UNKNOWN_{tickType}")] = value
        callback = self._callbacks.get(reqId, None)
        if callback is not None:
            callback(accumulator)

    def tickSnapshotEnd(self, reqId: int) -> None:
        """End signal for market data snapshot - resolve Future with accumulated ticks.

        Called ~11 seconds after reqMktData with snapshot=True.
        Resolves Future with dict containing "prices" and "sizes" mappings.
        """
        if DEBUG_TWS_CALLBACK:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")
        ticks = self._accumulators.pop(reqId, {})
        callback = self._callbacks.get(reqId, None)
        if callback is not None:
            self._callbacks.pop(reqId)
        else:
            self._resolve_future(reqId, ticks)

    # === Real-time bars (continuous subscription pattern) ===

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
        """Real-time 5-second bar callback - continuous subscription pattern.

        Uses queue.put_nowait via call_soon_threadsafe to pass data to main thread.
        Unlike Future-based callbacks, this is called repeatedly for each bar.
        """
        if DEBUG_TWS_CALLBACK:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")

        callback = self._callbacks.get(reqId, None)
        if callback is not None:
            # Pack bar data as tuple (domain conversion happens in main thread)
            callback(time, open_, high, low, close, int(volume), float(wap), count)
        else:
            logger.warning(f"No subscription queue for realtime bar reqId {reqId}")

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
        if reqId == -1:
            logger.error(
                f"TWS error [reqId={reqId}, time={errorTime}, code={errorCode}]: {errorString}"
            )
        else:
            self._reject_future(
                reqId,
                TWSError(
                    reqId=reqId,
                    errorTime=errorTime,
                    errorCode=errorCode,
                    errorString=errorString,
                    advancedOrderRejectJson=advancedOrderRejectJson,
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
            if not self.__ibsocket.ready:
                self.__ibsocket.disconnect()
                self.__ibsocket = IBSocket()
            self._cb_wrapper._ready_event.clear()  # Reset before new connection
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

        coroutine: Awaitable[list[ContractDescription]] = (
            self._cb_wrapper.create_future_coroutine(
                reqId, timeout=timeout or self._timeout
            )
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
        coroutine: Awaitable[list[ContractDetails]] = (
            self._cb_wrapper.create_future_coroutine(
                reqId, timeout=timeout or self._timeout
            )
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
        whatToShow: str = "TRADES",
        useRTH: int = 1,
        format_date: int = 1,
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
        coroutine: Awaitable[list[BarData]] = self._cb_wrapper.create_future_coroutine(
            reqId,
            timeout=timeout or self._timeout,
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
            False,  # keepUpToDate (always False for historical)
            [],  # chartOptions (empty list)
        ]

        self.ibsocket.send_message(OUT.REQ_HISTORICAL_DATA, fields)
        debug_log(
            f"awaiting historicalData for reqId {reqId}, "
            f"symbol='{contract.symbol}', duration='{duration_str}', barSize='{barSize_setting}'"
        )
        return await coroutine

    async def reqMktDataSnapshot(
        self,
        contract: Contract,
        genericTickList: str = "",
        timeout: float | None = None,
    ) -> dict[str, float | int]:
        """Request market data snapshot (single quote update).

        Args:
            contract: TWS Contract object
            genericTickList: Additional tick types (e.g., "233" for RTVolume)

        Returns:
            Dictionary with "prices" and "sizes" mappings (tickType → value)
            Example: {"prices": {1: 150.25, 2: 150.30}, "sizes": {0: 100, 3: 200}}
        """
        reqId = self.next_req_id
        coroutine: Awaitable[dict[str, float | int]] = (
            self._cb_wrapper.create_future_coroutine(
                reqId, timeout=timeout or self._timeout
            )
        )

        VERSION = 11

        # Build message fields for REQ_MKT_DATA
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
            False,  # ← ADD: deltaNeutralContract (False = no delta neutral)
            genericTickList,  # Now correctly positioned
            True,  # snapshot
            False,  # regulatorySnapshot
            [],  # mktDataOptions (empty list)
        ]

        self.ibsocket.send_message(OUT.REQ_MKT_DATA, fields)
        debug_log(
            f"awaiting tickSnapshotEnd for reqId {reqId}, symbol='{contract.symbol}'"
        )
        return await coroutine

    # === Real-time bar subscriptions (continuous pattern) ===

    def reqRealTimeBars(
        self,
        contract: Contract,
        callback: Callable[
            [
                int,
                float,
                float,
                float,
                float,
                Decimal,
                Decimal,
                int,
            ],
            None,
        ],
        barSize: int = 5,
        whatToShow: str = "TRADES",
        useRTH: bool = False,
        realTimeBarsOptions: list = [],
    ) -> int:
        """Subscribe to real-time 5-second bars.

        Unlike async methods, this returns immediately with a queue.
        Caller consumes queue to receive bar data tuples:
        (time, open, high, low, close, volume, wap, count)

        Args:
            contract: TWS Contract object
            barSize: Bar size in seconds (only 5 supported by TWS)
            whatToShow: Data type ("TRADES", "BID", "ASK", "MIDPOINT")
            useRTH: True for regular trading hours only

        Returns:
            Tuple of (reqId, queue) - queue receives bar data tuples
        """
        reqId = self.next_req_id
        self._cb_wrapper.register_callback(
            reqId,
            callback=callback,
        )

        # Build and send request (VERSION=3)
        VERSION = 3
        fields: list[object] = [
            VERSION,
            reqId,
            contract.conId,
            contract.symbol,
            contract.secType,
            contract.lastTradeDateOrContractMonth,
            (
                contract.strike if contract.strike else ""
            ),  # TODO: check "" swap vs raw UNSET_DOUBLE
            contract.right,
            contract.multiplier,
            contract.exchange,
            contract.primaryExchange,
            contract.currency,
            contract.localSymbol,
            contract.tradingClass,
            barSize,
            whatToShow,
            useRTH,
            realTimeBarsOptions,  # realTimeBarsOptions
        ]

        self.ibsocket.send_message(OUT.REQ_REAL_TIME_BARS, fields)
        debug_log(
            f"subscribed to realtime bars with reqId {reqId}, symbol='{contract.symbol}'"
        )
        return reqId

    def reqMktData(
        self,
        contract: Contract,
        callback: Callable[[dict[str, float | int]], None],
        genericTickList: str = "",
    ) -> int:
        """Request market data snapshot (single quote update).

        Args:
            contract: TWS Contract object
            genericTickList: Additional tick types (e.g., "233" for RTVolume)

        Returns:
            Dictionary with "prices" and "sizes" mappings (tickType → value)
            Example: {"prices": {1: 150.25, 2: 150.30}, "sizes": {0: 100, 3: 200}}
        """
        reqId = self.next_req_id
        self._cb_wrapper.register_callback(
            reqId,
            callback=callback,
        )

        VERSION = 11

        # Build message fields for REQ_MKT_DATA
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
            False,  # ← ADD: deltaNeutralContract (False = no delta neutral)
            genericTickList,
            False,  # snapshot
            False,  # regulatorySnapshot
            [],  # mktDataOptions (empty list)
        ]

        self.ibsocket.send_message(OUT.REQ_MKT_DATA, fields)
        debug_log(
            f"subscribed to realtime reqMktData with reqId {reqId}, symbol='{contract.symbol}'"
        )
        return reqId

    def cancelRealTimeBars(self, reqId: int) -> None:
        """Cancel real-time bars subscription.

        Args:
            reqId: Request ID from subscribe_realtime_bars
        """
        self._cb_wrapper.unregister_callback(reqId)

        VERSION = 1
        self.ibsocket.send_message(OUT.CANCEL_REAL_TIME_BARS, [VERSION, reqId])
        debug_log(f"cancelled realtime bars for reqId {reqId}")

    def cancelMktData(self, reqId: int):
        """Cancel tick-by-tick data subscription."""

        self._cb_wrapper.unregister_callback(reqId)

        VERSION = 2
        self.ibsocket.send_message(OUT.CANCEL_MKT_DATA, [VERSION, reqId])
        debug_log(f"cancelled realtime bars for reqId {reqId}")

    def disconnect(self) -> None:
        self.ibsocket.disconnect()

    def __del__(self) -> None:
        self.disconnect()
