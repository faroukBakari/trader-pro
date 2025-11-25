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
import queue
import threading
import time
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from socket import error as socketError
from socket import socket
from socket import timeout as socketTimeout
from typing import Any

from ibapi.common import *
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


def make_fields(values: list) -> bytes:
    return b"".join(
        str(int(v) if isinstance(v, bool) else v).encode() + b"\0" for v in values
    )


def decode_data(buf: bytes, buf_siz: int) -> tuple[int, bytes, bytes, int]:
    msg_size = int.from_bytes(buf[:4], byteorder="big")
    if msg_size <= buf_siz - 4:
        logger.debug("received length: %d", msg_size)
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
        self, host: str, port: int, client_id: int, block_interval: float = 1
    ) -> None:
        self._host = host
        self._port = port
        self._client_id = client_id
        self._block_interval = block_interval
        self._server_version: int = 203
        self.connection_time: str = ""
        self._socket = socket()
        self._lock = threading.Lock()

    @property
    def server_version(self) -> int:
        return self._server_version

    def connect(self, soc: socket | None = None) -> None:
        with self._lock:
            while True:
                try:
                    self._socket = soc or socket()
                # TODO: list the exceptions you want to catch
                except socketError:
                    logger.error(
                        NO_VALID_ID,
                        round(time.time() * 1000),
                        FAIL_CREATE_SOCK.code(),
                        FAIL_CREATE_SOCK.msg(),
                    )

                try:
                    self._socket.connect((self._host, self._port))
                    self._socket.settimeout(self._block_interval)
                    break
                except socketError:
                    logger.error(
                        NO_VALID_ID,
                        round(time.time() * 1000),
                        CONNECT_FAIL.code(),
                        CONNECT_FAIL.msg(),
                    )
                    time.sleep(1)
            connected = self.isConnected()
            assert connected, "Socket connection failed."
            logger.info(f"Socket connected: {connected}: {self._socket.getpeername()}")

            # Send initial handshake message
            v100prefix = "API\0"
            msg_prefix = str.encode(v100prefix, "ascii")
            v100version = "v%d..%d" % (MIN_CLIENT_VER, MAX_CLIENT_VER)
            msg_content = len(v100version).to_bytes(4, "big") + v100version.encode()
            message = msg_prefix + msg_content
            self._socket.sendall(message)
            logger.debug("Sent initial message: %s", message)
            data = self._socket.recv(4096)
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
            text = make_fields([VERSION, self._client_id, ""])
            msg2 = (
                (len(text) + 4).to_bytes(4, "big")
                + OUT.START_API.to_bytes(4, "big")
                + text
            )
            self._socket.sendall(msg2)
            connected = self.isConnected()
            assert connected, "Socket connection failed."
            logger.info("IBSocket connection successfully.")

    def isConnected(self):
        return (
            self._socket is not None
            and self._socket.fileno() != -1
            and self._socket.getpeername() is not None
        )

    def disconnect(self):
        with self._lock:
            if self.isConnected():
                self._socket.close()
                logger.info("IBSocket Socket disconnected.")

    def send_message(self, msgId: int, values: list[object]):
        text = make_fields(values)
        msg2 = (len(text) + 4).to_bytes(4, "big") + msgId.to_bytes(4, "big") + text
        logger.debug(f"Sending message: {msg2.decode('ascii', errors='ignore')}")
        assert self.isConnected(), "Socket is not connected."
        with self._lock:
            self._socket.sendall(msg2)

    def receive_data(
        self, read_buf: bytes = b"", buf_siz: int = 0
    ) -> tuple[int, bytes, bytes, int]:
        chunks = [read_buf]
        assert self.isConnected() is not None, "Socket is not connected."
        new_data_received = False
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


class TWSClientHelper(EWrapper):
    """TWSClient helper base class - enables mock injection for testing.

    Inherits EWrapper for callback methods.
    Manages asyncio.Future registry for request/response patterns.
    Uses _accumulators for streaming accumulation pattern (multiple callbacks → single result).
    """

    def __init__(
        self,
        ibsocket: IBSocket,
        client_thread: threading.Thread | None = None,
        running: threading.Event | None = None,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        """Initialize IBSocket (pure callback handler).

        Note: No EClient instance - caller must provide via composition.
        """
        self._ibsocket = ibsocket
        self._loop = loop or asyncio.get_event_loop()
        self._running = running or threading.Event()
        self._client_thread = client_thread or threading.Thread(
            target=self._client_loop, daemon=True
        )
        self._client_thread.start()
        self._next_req_id = 0
        self._futures: dict[int, asyncio.Future[Any]] = {}
        # Accumulators for streaming responses (contractDetails, historicalData, etc.)
        self._accumulators: dict[int, list[Any]] = {}

    def __del__(self) -> None:
        """Destructor to ensure clean shutdown."""
        self.disconnect()

    @property
    def curr_req_id(self) -> int:
        return self._next_req_id

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        return self._loop

    @property
    def running(self) -> threading.Event:
        return self._running

    @property
    def client_thread(self) -> threading.Thread:
        return self._client_thread

    @property
    def next_req_id(self) -> int:
        current_req_id = self._next_req_id
        self._next_req_id += 1
        return current_req_id

    def connect(self) -> threading.Thread:
        """Connect to TWS via IBSocket."""
        if not self._client_thread.is_alive():
            logger.info("Starting TWSClient reader thread.")
            self._client_thread = threading.Thread(
                target=self._client_loop, daemon=True
            )
            self._client_thread.start()
        return self._client_thread

    def disconnect(self) -> None:
        """Destructor to ensure clean shutdown."""
        self._running.clear()
        self._client_thread.join(timeout=2)
        self._ibsocket.disconnect()

    def _client_loop(self) -> None:
        """TWS reader loop - to be run in a separate thread.

        Note:
            This method should be called in a dedicated thread to continuously
            read messages from the TWSClient connection and dispatch them to
            the appropriate EWrapper callback methods.
        """
        self._running.set()
        while self._running.is_set():
            try:
                self._ibsocket.connect()
                decoder = Decoder(self, self._ibsocket.server_version)
                logger.info("TWSClient reader loop started.")
                buf = b""
                buf_siz = 0
                while self._ibsocket.isConnected() and self._running.is_set():
                    try:
                        msgId, data, buf, buf_siz = self._ibsocket.receive_data(
                            buf, buf_siz
                        )
                        if msgId == -1:
                            continue

                        logger.debug(
                            f"Dispatching message ID: {msgId} with fields: {data.decode('ascii', errors='ignore')}"
                        )
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
                        logger.debug(f"Exception in TWSClient reader loop: {e}")
                        time.sleep(0.5)
            except Exception as e:
                logger.debug(f"Exception in TWSClient client loop: {e}")
                time.sleep(0.5)
        logger.info("TWSClient reader loop finished.")

    def _resolve_future(self, reqId: int, result) -> None:
        """Helper to resolve a future in the asyncio loop."""
        assert reqId in self._futures, f"Unknown reqId {reqId} in _resolve_future."
        future = self._futures.pop(reqId)
        if not future.done():
            self._loop.call_soon_threadsafe(future.set_result, result)

    def _reject_future(self, reqId: int, exception: Exception) -> None:
        """Helper to reject a future with an exception in the asyncio loop."""
        assert reqId in self._futures, f"Unknown reqId {reqId} in _resolve_future."
        future = self._futures.pop(reqId)
        if not future.done():
            self._loop.call_soon_threadsafe(future.set_exception, exception)

    # === symbolSamples ===

    def symbolSamples(
        self, reqId: int, contractDescriptions: list[ContractDescription]
    ):
        self._resolve_future(reqId, contractDescriptions)

    async def reqMatchingSymbols(self, pattern: str) -> list[ContractDescription]:
        reqId = self.next_req_id
        # Create a future attached to the current running loop
        loop = asyncio.get_running_loop()
        future: asyncio.Future[list[ContractDescription]] = loop.create_future()
        self._futures[reqId] = future
        self._ibsocket.send_message(OUT.REQ_MATCHING_SYMBOLS, [reqId, pattern])
        logger.debug(
            f"awaiting symbolSamples for reqId {reqId} and pattern '{pattern}'"
        )
        contractDescriptions = await future
        return contractDescriptions

    # === contractDetails (streaming accumulation pattern) ===

    def contractDetails(self, reqId: int, contractDetails: ContractDetails) -> None:
        """Accumulate contract details (may be called multiple times).

        TWS sends one contractDetails callback per matching contract.
        Results are accumulated until contractDetailsEnd is called.
        """
        if reqId not in self._accumulators:
            self._accumulators[reqId] = []
        self._accumulators[reqId].append(contractDetails)

    def contractDetailsEnd(self, reqId: int) -> None:
        """End signal for contract details - resolve Future with accumulated results."""
        results = self._accumulators.pop(reqId, [])
        self._resolve_future(reqId, results)

    async def reqContractDetails(self, contract: Contract) -> list[ContractDetails]:
        """Request contract details for a symbol.

        Args:
            contract: TWS Contract object specifying symbol, secType, exchange, etc.

        Returns:
            List of ContractDetails matching the contract specification.
            May return multiple results for ambiguous queries.
        """
        reqId = self.next_req_id
        loop = asyncio.get_running_loop()
        future: asyncio.Future[list[ContractDetails]] = loop.create_future()
        self._futures[reqId] = future
        self._accumulators[reqId] = []  # Initialize accumulator

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

        self._ibsocket.send_message(OUT.REQ_CONTRACT_DATA, fields)
        logger.debug(
            f"awaiting contractDetails for reqId {reqId} and symbol '{contract.symbol}'"
        )
        return await future

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


class TWSClient(TWSClientHelper):

    def __init__(
        self,
        host: str,
        port: int,
        client_id: int,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        """Initialize IBSocket (pure callback handler).

        Note: No EClient instance - caller must provide via composition.
        """
        self._ibsocket = IBSocket(host, port, client_id, block_interval=1)
        super().__init__(
            ibsocket=self._ibsocket,
            loop=loop,
        )
