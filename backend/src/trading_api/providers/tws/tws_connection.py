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
import threading
import time
from collections.abc import Awaitable
from dataclasses import dataclass
from decimal import Decimal
from socket import error as socketError
from socket import socket
from socket import timeout as socketTimeout
from typing import Any

from ibapi.common import BarData, TickAttrib
from ibapi.const import DOUBLE_INFINITY, INFINITY_STR, UNSET_DOUBLE, UNSET_INTEGER
from ibapi.contract import Contract, ContractDescription, ContractDetails
from ibapi.decoder import Decoder
from ibapi.errors import CONNECT_FAIL, FAIL_CREATE_SOCK
from ibapi.message import OUT
from ibapi.protobuf.ErrorMessage_pb2 import ErrorMessage as ErrorMessageProto
from ibapi.wrapper import EWrapper

logger = logging.getLogger(__name__)


NO_VALID_ID = -1
MIN_CLIENT_VER = 100
MAX_CLIENT_VER = 203
PROTOBUF_MSG_ID = 200
VERSION = 2


def to_str(val: object) -> str:
    if isinstance(val, bool):
        return str(int(val))

    if isinstance(val, list):
        # Convert list to concatenated string (like official API)
        return "".join(to_str(item) for item in val)

    if UNSET_INTEGER == val or UNSET_DOUBLE == val:
        return ""

    if DOUBLE_INFINITY == val:
        return str(INFINITY_STR)

    return str(val)


def make_fields(values: list) -> bytes:
    return b"".join(to_str(v).encode() + b"\0" for v in values)


def decode_data(buf: bytes, buf_siz: int) -> tuple[int, bytes, bytes, int]:
    msg_size = int.from_bytes(buf[:4], byteorder="big")
    if msg_size <= buf_siz - 4:
        remaining_buff = buf[4 + msg_size :]
        buf_siz -= 4 + msg_size
        assert len(remaining_buff) == buf_siz, "Buffer size mismatch after decoding."
        return (
            int.from_bytes(buf[4:8], "big"),
            # [chunk for chunk in buf[8 : 4 + msg_size].split(b"\0")],
            buf[8 : 4 + msg_size],
            remaining_buff,
            buf_siz,
        )
    else:
        return -1, b"", buf, buf_siz


class IBSocket:
    def __init__(
        self, soc: socket | None = None, loc: "threading.Lock | None" = None
    ) -> None:
        self._server_version: int = 203
        self.connection_time: str = ""
        self._next_req_id: int = 0
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
        with self._lock:
            current_req_id = self._next_req_id
            self._next_req_id += 1
            return current_req_id

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
            return self._socket.getpeername() is not None
        except OSError:
            return False

    @property
    def closed(self) -> bool:
        return self._socket.fileno() == -1

    def _reader_loop(self, cb_wrapper: EWrapper) -> None:
        """TWS reader loop - to be run in a separate thread.

        Note:
            This method should be called in a dedicated thread to continuously
            read messages from the IBSocket connection and dispatch them to
            the appropriate EWrapper callback methods.
        """
        decoder = Decoder(cb_wrapper, self.server_version)
        logger.info("IBSocket reader loop started.")
        buf = b""
        buf_siz = 0
        while self.running:
            try:
                msgId, data, buf, buf_siz = self.receive_data(buf, buf_siz)
                if msgId == -1:
                    if buf_siz > 0:
                        logger.debug(
                            f"Incomplete message in buffer, waiting for more data. "
                            f"Buffer size: {buf_siz}"
                        )
                    continue

                if msgId > PROTOBUF_MSG_ID:
                    msgId -= PROTOBUF_MSG_ID
                    logger.debug("msgId: %d, protobuf: %s", msgId, data)
                    decoder.processProtoBuf(data, msgId)
                else:
                    fields = [chunk for chunk in data.split(b"\0")]
                    logger.debug("msgId: %d, fields: %s", msgId, fields)
                    # Remove trailing empty field
                    decoder.interpret(fields[:-1], msgId)
            except Exception as e:
                logger.debug(f"Exception in IBSocket reader loop: {e}")
                time.sleep(0.5)

        logger.info("IBSocket reader loop finished.")

    def connect(
        self,
        host: str,
        port: int,
        client_id: int,
        cb_wrapper: EWrapper,
        block_interval: float = 1,
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
            logger.debug("Sent initial message: %s", message)
            nb_retries = 3
            while True:
                try:
                    data = self._socket.recv(4096)
                    break
                except Exception as e:
                    nb_retries -= 1
                    assert (
                        nb_retries > 0
                    ), f"Error while waiting for handshake response: {e}"
            buf_size = len(data)
            msg_size = int.from_bytes(data[:4], byteorder="big")
            logger.debug("received length: %d", msg_size)
            assert (
                msg_size <= buf_size - 4
            ), f"Initial read buffer size exceeds message size: {buf_size}"
            fields = [chunk for chunk in data[4 : 4 + msg_size].split(b"\0") if chunk]
            assert len(fields) == 2, "Expected at two fields in handshake message."
            server_version, self.connection_time = [
                msg.decode("ascii") for msg in fields
            ]
            self._server_version = int(server_version)
            logger.debug(
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
            daemon=True,
        )
        self._reader_thread.start()
        return self._reader_thread

    def disconnect(self) -> None:
        try:
            with self._lock:
                self._socket.close()
        finally:
            while self._reader_thread and self._reader_thread.is_alive():
                logger.info("Waiting for IBSocket reader thread to finish...")
                self._reader_thread.join(timeout=2)
            logger.info("IBSocket Socket disconnected.")

    def send_message(self, msgId: int, values: list[object]) -> None:
        text = make_fields(values)
        msg2 = (len(text) + 4).to_bytes(4, "big") + msgId.to_bytes(4, "big") + text
        logger.debug(f"Sending message: {msg2.decode('ascii', errors='ignore')}")
        assert self.running, "Socket is not connected."
        with self._lock:
            self._socket.sendall(msg2)

    def receive_data(
        self, read_buf: bytes = b"", buf_siz: int = 0
    ) -> tuple[int, bytes, bytes, int]:
        chunks = [read_buf]
        new_data_received = False
        assert self.running, "Socket is not connected."
        while True:
            try:
                data = self._socket.recv(4096)
                assert data, "Socket connection closed."
                chunks.append(data)
                receiv_siz = len(data)
                buf_siz += receiv_siz
                new_data_received = True
                if receiv_siz < 4096:
                    break
            except socketTimeout:
                # No more data available right now
                break

        if new_data_received:
            read_buf = b"".join([chunk for chunk in chunks if chunk])
            logger.debug(
                f"Final received data: <{read_buf.decode('ascii', errors='ignore')}>"
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
    """

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        """Initialize IBSocket (pure callback handler).

        Note: No EClient instance - caller must provide via composition.
        """
        self._loop = loop or asyncio.get_event_loop()
        self._futures: dict[int, asyncio.Future[Any]] = {}
        self._accumulators: dict[
            int, list[Any] | dict[str, dict[int, float | int]]
        ] = {}

    def dispatchMessage(self, fnName: str, fnParams: dict) -> None:
        if logger.isEnabledFor(logging.INFO):
            if "self" in fnParams:
                fnParams = dict(fnParams)
                del fnParams["self"]
            logger.info(f"!!!WARNING!!!: unimplemented {fnName} --> {fnParams}")

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        return self._loop

    def create_future_coroutine(self, reqId: int, timeout: float = 5) -> Awaitable[Any]:
        """Create a new Future attached to the current event loop."""
        future: asyncio.Future[Any] = self.loop.create_future()
        self._futures[reqId] = future
        return asyncio.wait_for(future, timeout)

    def _resolve_future(self, reqId: int, result: object) -> None:
        """Helper to resolve a future in the asyncio loop."""
        if reqId in self._futures:
            future = self._futures.pop(reqId)
            if not future.done():
                self.loop.call_soon_threadsafe(future.set_result, result)
        else:
            logger.error(f"Unknown reqId {reqId} in _resolve_future.")

    def _reject_future(self, reqId: int, exception: Exception) -> None:
        """Helper to reject a future with an exception in the asyncio loop."""
        if reqId in self._futures:
            future = self._futures.pop(reqId)
            if not future.done():
                self.loop.call_soon_threadsafe(future.set_exception, exception)
        else:
            logger.error(f"Unknown reqId {reqId} in _reject_future.")

    # === symbolSamples ===

    def symbolSamples(
        self, reqId: int, contractDescriptions: list[ContractDescription]
    ) -> None:
        self._resolve_future(reqId, contractDescriptions)

    # === contractDetails (streaming accumulation pattern) ===

    def contractDetails(self, reqId: int, contractDetails: ContractDetails) -> None:
        """Accumulate contract details (may be called multiple times).

        TWS sends one contractDetails callback per matching contract.
        Results are accumulated until contractDetailsEnd is called.
        """
        if reqId not in self._accumulators:
            self._accumulators[reqId] = []
        # Type assertion: accumulator is list for contractDetails
        accumulator = self._accumulators[reqId]
        if isinstance(accumulator, list):
            accumulator.append(contractDetails)

    def contractDetailsEnd(self, reqId: int) -> None:
        """End signal for contract details - resolve Future with accumulated results."""
        results = self._accumulators.pop(reqId, [])
        self._resolve_future(reqId, results)

    # === historicalData (streaming accumulation pattern) ===

    def historicalData(self, reqId: int, bar: BarData) -> None:
        """Accumulate historical bars (may be called multiple times).

        TWS sends one historicalData callback per bar.
        Results are accumulated until historicalDataEnd is called.
        """
        if reqId not in self._accumulators:
            self._accumulators[reqId] = []
        # Type assertion: accumulator is list for historicalData
        accumulator = self._accumulators[reqId]
        if isinstance(accumulator, list):
            accumulator.append(bar)

    def historicalDataEnd(self, reqId: int, start: str, end: str) -> None:
        """End signal for historical data - resolve Future with accumulated results."""
        results = self._accumulators.pop(reqId, [])
        self._resolve_future(reqId, results)

    # === Market data snapshot (accumulation pattern) ===

    def tickPrice(
        self, reqId: int, tickType: int, price: float, tickAttrib: TickAttrib
    ) -> None:
        """Accumulate price ticks for market data snapshot.

        Called multiple times per snapshot with different tick types.
        Results accumulated until tickSnapshotEnd is called.
        """
        if reqId not in self._accumulators:
            self._accumulators[reqId] = {"prices": {}, "sizes": {}}
        # Type assertion: accumulator is dict for tick data
        accumulator = self._accumulators[reqId]
        if isinstance(accumulator, dict):
            accumulator["prices"][tickType] = price

    def tickSize(self, reqId: int, tickType: int, size: Decimal) -> None:
        """Accumulate size ticks for market data snapshot.

        Called multiple times per snapshot with different tick types.
        Results accumulated until tickSnapshotEnd is called.
        """
        if reqId not in self._accumulators:
            self._accumulators[reqId] = {"prices": {}, "sizes": {}}
        # Type assertion: accumulator is dict for tick data
        accumulator = self._accumulators[reqId]
        if isinstance(accumulator, dict):
            accumulator["sizes"][tickType] = int(size)

    def tickSnapshotEnd(self, reqId: int) -> None:
        """End signal for market data snapshot - resolve Future with accumulated ticks.

        Called ~11 seconds after reqMktData with snapshot=True.
        Resolves Future with dict containing "prices" and "sizes" mappings.
        """
        ticks = self._accumulators.pop(reqId, {"prices": {}, "sizes": {}})
        self._resolve_future(reqId, ticks)

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
    def _ibsocket(self) -> IBSocket:
        if not self.__ibsocket.running:
            if not self.__ibsocket.ready:
                self.__ibsocket.disconnect()
                self.__ibsocket = IBSocket()
            self.__ibsocket.connect(
                host=self._host,
                port=self._port,
                client_id=self._client_id,
                cb_wrapper=self._cb_wrapper,
            )
        return self.__ibsocket

    @property
    def next_req_id(self) -> int:
        return self._ibsocket.next_req_id

    async def reqMatchingSymbols(self, pattern: str) -> list[ContractDescription]:
        reqId = self.next_req_id

        coroutine: Awaitable[
            list[ContractDescription]
        ] = self._cb_wrapper.create_future_coroutine(reqId)
        self.__ibsocket.send_message(OUT.REQ_MATCHING_SYMBOLS, [reqId, pattern])
        logger.debug(
            f"awaiting symbolSamples for reqId {reqId} and pattern '{pattern}'"
        )

        return await coroutine

    async def reqContractDetails(self, contract: Contract) -> list[ContractDetails]:
        """Request contract details for a symbol.

        Args:
            contract: TWS Contract object specifying symbol, secType, exchange, etc.

        Returns:
            List of ContractDetails matching the contract specification.
            May return multiple results for ambiguous queries.
        """
        reqId = self.next_req_id
        coroutine: Awaitable[
            list[ContractDetails]
        ] = self._cb_wrapper.create_future_coroutine(reqId)

        # Build message fields (VERSION=8 per ibapi/client.py)
        version = 8
        fields: list[object] = [
            version,
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

        self.__ibsocket.send_message(OUT.REQ_CONTRACT_DATA, fields)
        logger.debug(
            f"awaiting contractDetails for reqId {reqId} and symbol '{contract.symbol}'"
        )
        return await coroutine

    async def reqHistoricalData(
        self,
        contract: Contract,
        end_date_time: str,
        duration_str: str,
        bar_size_setting: str,
        what_to_show: str = "TRADES",
        use_rth: int = 1,
        format_date: int = 1,
    ) -> list[BarData]:
        """Request historical bars from TWS.

        Args:
            contract: TWS Contract object
            end_date_time: End datetime ("20231215 16:00:00" or "" for now)
            duration_str: Time range ("1 D", "2 W", "1 M", etc.)
            bar_size_setting: Bar size ("1 min", "5 mins", "1 hour", "1 day")
            what_to_show: Data type (default: "TRADES")
            use_rth: 1=regular hours only, 0=all hours (default: 1)
            format_date: 1=string format, 2=epoch (default: 1)

        Returns:
            List of BarData objects (one per bar, in ascending time order)
        """
        reqId = self.next_req_id
        coroutine: Awaitable[list[BarData]] = self._cb_wrapper.create_future_coroutine(
            reqId
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
            bar_size_setting,
            duration_str,
            use_rth,
            what_to_show,
            format_date,
            False,  # keepUpToDate (always False for historical)
            [],  # chartOptions (empty list)
        ]

        self.__ibsocket.send_message(OUT.REQ_HISTORICAL_DATA, fields)
        logger.debug(
            f"awaiting historicalData for reqId {reqId}, "
            f"symbol='{contract.symbol}', duration='{duration_str}', barSize='{bar_size_setting}'"
        )
        return await coroutine

    async def reqMktDataSnapshot(
        self, contract: Contract, generic_tick_list: str = ""
    ) -> dict[str, dict[int, float | int]]:
        """Request market data snapshot (single quote update).

        Args:
            contract: TWS Contract object
            generic_tick_list: Additional tick types (e.g., "233" for RTVolume)

        Returns:
            Dictionary with "prices" and "sizes" mappings (tickType → value)
            Example: {"prices": {1: 150.25, 2: 150.30}, "sizes": {0: 100, 3: 200}}
        """
        reqId = self.next_req_id
        coroutine: Awaitable[
            dict[str, dict[int, float | int]]
        ] = self._cb_wrapper.create_future_coroutine(reqId, self._timeout)

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
            generic_tick_list,
            True,  # snapshot=True (single update)
            False,  # regulatorySnapshot
            [],  # mktDataOptions (empty list)
        ]

        self.__ibsocket.send_message(OUT.REQ_MKT_DATA, fields)
        logger.debug(
            f"awaiting tickSnapshotEnd for reqId {reqId}, symbol='{contract.symbol}'"
        )
        return await coroutine
