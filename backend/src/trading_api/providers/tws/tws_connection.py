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

from __future__ import annotations

import asyncio
import logging
import os
import select
import struct
import threading
import time
from decimal import Decimal
from itertools import count
from socket import MSG_PEEK
from socket import error as socketError
from socket import socket
from socket import timeout as socketTimeout
from typing import TYPE_CHECKING, Any

from ibapi.commission_and_fees_report import CommissionAndFeesReport
from ibapi.common import PROTOBUF_MSG_ID, BarData, TickAttrib
from ibapi.const import DOUBLE_INFINITY, INFINITY_STR, UNSET_DOUBLE, UNSET_INTEGER
from ibapi.contract import Contract, ContractDescription, ContractDetails
from ibapi.decoder import Decoder
from ibapi.execution import Execution
from ibapi.message import OUT
from ibapi.order import Order

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

from ibapi.order_state import OrderState
from ibapi.protobuf.ErrorMessage_pb2 import ErrorMessage as ErrorMessageProto
from ibapi.ticktype import TickTypeEnum
from ibapi.wrapper import EWrapper, current_fn_name

from trading_api.models.exceptions import ProviderException
from trading_api.models.market import Bar, QuoteData
from trading_api.providers.tws.account_tracker import AccountTracker, TrackedAccount
from trading_api.providers.tws.bars_tracker import BarsTracker
from trading_api.providers.tws.cached_contract import CachedContract
from trading_api.providers.tws.contract_tracker import ContractTracker
from trading_api.providers.tws.execution_tracker import (
    ExecutionTracker,
    TrackedExecution,
)
from trading_api.providers.tws.order_tracker import OrderTracker, TrackedOrder
from trading_api.providers.tws.position_tracker import PositionTracker, TrackedPosition
from trading_api.providers.tws.quote_tracker import QuoteTracker
from trading_api.providers.tws.tws_mappers import parse_ticker
from trading_api.providers.tws.tws_models import (
    TICK_TYPE_TO_FIELD,
    TWSErrorClassification,
    TWSErrorNature,
    classify_error,
    get_bar_duration_seconds,
)
from trading_api.providers.tws.wiring_interfaces import (
    AccountTrackerCBWiringInterface,
    BarsTrackerCBWiringInterface,
    ContractTrackerCBWiringInterface,
    ExecutionTrackerCBWiringInterface,
    IbSocketWiringInterface,
    OrderTrackerCBWiringInterface,
    PositionTrackerCBWiringInterface,
    QuoteTrackerCBWiringInterface,
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


class IBSocket(EWrapper, IbSocketWiringInterface):
    def __init__(self) -> None:
        # socket related attributes
        self.__quote_tracker: QuoteTrackerCBWiringInterface | None = None
        self.__bars_tracker: BarsTrackerCBWiringInterface | None = None
        self.__contract_tracker: ContractTrackerCBWiringInterface | None = None
        self.__position_tracker: PositionTrackerCBWiringInterface | None = None
        self.__execution_tracker: ExecutionTrackerCBWiringInterface | None = None
        self.__order_tracker: OrderTrackerCBWiringInterface | None = None
        self.__account_tracker: AccountTrackerCBWiringInterface | None = None
        self._req_id_count: count[int] = count()
        self.__next_order_id: int | None = None
        self.__accounts_list: str | None = None
        self._socket_lock = threading.Lock()
        self._state = IBSocketState.READY
        self._socket = socket()
        self._reader_loop: asyncio.AbstractEventLoop | None = None

        self._server_version: str = ""
        self._connection_time: str = ""

        self._ready_event = (
            threading.Event()
        )  # Signals when IBKR connection is fully established

    # == infrastructure methods (internal) ==

    def wire_quote_tracker(
        self, tracker_interface: QuoteTrackerCBWiringInterface
    ) -> None:
        self.__quote_tracker = tracker_interface

    def wire_bars_tracker(
        self, tracker_interface: BarsTrackerCBWiringInterface
    ) -> None:
        self.__bars_tracker = tracker_interface

    def wire_contract_tracker(
        self, tracker_interface: ContractTrackerCBWiringInterface
    ) -> None:
        self.__contract_tracker = tracker_interface

    def wire_position_tracker(
        self, tracker_interface: PositionTrackerCBWiringInterface
    ) -> None:
        self.__position_tracker = tracker_interface

    def wire_execution_tracker(
        self, tracker_interface: ExecutionTrackerCBWiringInterface
    ) -> None:
        self.__execution_tracker = tracker_interface

    def wire_order_tracker(
        self, tracker_interface: OrderTrackerCBWiringInterface
    ) -> int | None:
        self.__order_tracker = tracker_interface
        return self.__next_order_id

    def wire_account_tracker(
        self, tracker_interface: AccountTrackerCBWiringInterface
    ) -> str:
        self.__account_tracker = tracker_interface
        assert (
            self.__accounts_list is not None
        ), "Accounts list should be set as part of the socket connection setup."
        return self.__accounts_list

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
                self._log_handled_error(
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
            self._ready_event.clear()
            self._req_id_count = count()

    def _log_handled_error(
        self,
        category: str,
        detail: str,
        tws_key: str,
        message: str,
        timestamp: int | None = None,
    ) -> None:
        capability = "shared"

        error = ProviderException(
            code=f"PROVIDER_TWS_{category}_{detail.upper()}",
            message=f"[{tws_key}] {message}",
            provider="tws",
            capability=capability,
            timestamp=timestamp,
        )

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
        timeout: float = 5.0,
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

        # Wait for nextValidId signal (connection fully ready)
        if not self._ready_event.wait(timeout=timeout):
            raise TimeoutError("Timeout waiting for TWS connection ready signal")

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

    # ================================================
    # =============== Request Methods ================
    # ================================================

    # Note: reqMatchingSymbols, reqContractDetails, and account-related requests
    # have been internalized into their respective trackers via the wiring interface pattern.
    # Use ContractTracker.request_descriptions() and request_details() instead.
    # Use AccountTracker for account summary and P&L subscriptions.

    # ================================================
    # == Dispatch handlers for subscription events ===
    # ================================================

    # === Trading / account management ===

    def managedAccounts(self, accountsList: str) -> None:
        if DEBUG_TWS_DISPATCH:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")
        # should be sent upon connection - route to wired AccountTracker
        assert (
            self.__account_tracker is not None or self.__accounts_list is None
        ), "Unexpected nextValidId callback: order tracker already wired."
        self.__accounts_list = accountsList
        if self.__account_tracker is not None:
            accounts = accountsList.split(",")
            for account in accounts:
                self.__account_tracker.upsert_account(account)

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
        if DEBUG_TWS_DISPATCH:
            debug_log(
                f"{current_fn_name()}, reqId={reqId}, account={account}, "
                f"tag={tag}, value={value}, currency={currency}"
            )

        if self.__account_tracker is not None:
            self.__account_tracker.update_account(account, tag, value, currency)

    def accountSummaryEnd(self, reqId: int) -> None:
        """End signal for account summary request.

        Called after all accountSummary callbacks for reqAccountSummary().
        Resolves the pending future with accumulated summary data.
        """
        if DEBUG_TWS_DISPATCH:
            debug_log(f"{current_fn_name()}")

        # Mark snapshot complete and resolve pending futures
        if self.__account_tracker is not None:
            self.__account_tracker.mark_summary_complete()

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
        if DEBUG_TWS_DISPATCH:
            debug_log(f"{current_fn_name()}: {key}={val} {currency} for {accountName}")

        if self.__account_tracker is not None:
            self.__account_tracker.update_account(accountName, key, val, currency)

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
        if DEBUG_TWS_DISPATCH:
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
        if DEBUG_TWS_DISPATCH:
            debug_log(f"{current_fn_name()}: {timeStamp}")

        if self.__account_tracker is not None:
            self.__account_tracker.update_account_time(timeStamp)

    def accountDownloadEnd(self, accountName: str) -> None:
        """End signal for reqAccountUpdates() batch.

        Called after all updateAccountValue/updatePortfolio callbacks.
        Marks snapshot complete similar to accountSummaryEnd.

        Args:
            accountName: Account ID for which download completed
        """
        if DEBUG_TWS_DISPATCH:
            debug_log(f"{current_fn_name()}: {accountName}")

        if self.__account_tracker is not None:
            self.__account_tracker.mark_summary_complete()

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
        if DEBUG_TWS_DISPATCH:
            debug_log(
                f"{current_fn_name()}: reqId={reqId} daily={dailyPnL} "
                f"unrealized={unrealizedPnL} realized={realizedPnL}"
            )
        if self.__account_tracker is not None:
            self.__account_tracker.update_pnl(
                reqId, dailyPnL, unrealizedPnL, realizedPnL
            )

    # === symbolSamples ===

    def symbolSamples(
        self, reqId: int, contractDescriptions: list[ContractDescription]
    ) -> None:
        if DEBUG_TWS_DISPATCH:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")

        # Route to ContractTracker via wired interface
        if self.__contract_tracker is not None:
            self.__contract_tracker.update_descriptions(reqId, contractDescriptions)

    # === contractDetails (streaming accumulation pattern) ===

    def contractDetails(self, reqId: int, contractDetails: ContractDetails) -> None:
        """Accumulate contract details (may be called multiple times).

        TWS sends one contractDetails callback per matching contract.
        Results are accumulated until contractDetailsEnd is called.
        """
        if DEBUG_TWS_DISPATCH:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")

        # Route to ContractTracker via wired interface
        if self.__contract_tracker is not None:
            self.__contract_tracker.update_details(reqId, contractDetails)

    def contractDetailsEnd(self, reqId: int) -> None:
        """End signal for contract details - resolve Future with accumulated results."""
        if DEBUG_TWS_DISPATCH:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")

        # Route to ContractTracker via wired interface
        if self.__contract_tracker is not None:
            self.__contract_tracker.flag_details_complete(reqId)

    # === historicalData (streaming accumulation pattern) ===

    def historicalData(self, reqId: int, bar: BarData) -> None:
        """Accumulate historical bars (may be called multiple times).

        TWS sends one historicalData callback per bar.
        Results are accumulated until historicalDataEnd is called.
        """

        if DEBUG_TWS_DISPATCH:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")

        # Route to BarsTracker via wired interface
        if self.__bars_tracker is not None:
            self.__bars_tracker.update(reqId, bar)

    def historicalDataUpdate(self, reqId: int, bar: BarData) -> None:
        """Returns updates in real time when keepUpToDate is set to True."""

        if DEBUG_TWS_DISPATCH:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")

        # Route to BarsTracker via wired interface
        if self.__bars_tracker is not None:
            self.__bars_tracker.update(reqId, bar)

    def historicalDataEnd(self, reqId: int, start: str, end: str) -> None:
        """End signal for historical data - resolve Future with accumulated results."""

        if DEBUG_TWS_DISPATCH:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")

        # Route to BarsTracker via wired interface
        if self.__bars_tracker is not None:
            self.__bars_tracker.flag_complete(reqId, start, end)

    # === Market data (accumulation pattern) ===

    def tickPrice(
        self, reqId: int, tickType: int, price: float, attrib: TickAttrib
    ) -> None:
        """Accumulate price ticks for market data snapshot."""

        if DEBUG_TWS_DISPATCH:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")

        tick_name = get_tick_type_name(tickType)
        field_name = TICK_TYPE_TO_FIELD.get(tick_name)  # type: ignore[arg-type]
        if field_name is None:
            return

        if self.__quote_tracker is not None:
            self.__quote_tracker.update(reqId, {field_name: price})

    def tickSize(self, reqId: int, tickType: int, size: Decimal) -> None:
        """Accumulate size ticks for market data snapshot."""

        if DEBUG_TWS_DISPATCH:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")

        tick_name = get_tick_type_name(tickType)
        field_name = TICK_TYPE_TO_FIELD.get(tick_name)  # type: ignore[arg-type]
        if field_name is None:
            return
        if self.__quote_tracker is not None:
            self.__quote_tracker.update(reqId, {field_name: float(size)})

    def marketDataType(self, reqId: int, marketDataType: int) -> None:
        """Set market data type for the request."""
        if DEBUG_TWS_DISPATCH:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")

        if self.__quote_tracker is not None:
            self.__quote_tracker.update(reqId, {"market_data_type": marketDataType})

    def tickReqParams(
        self, tickerId: int, minTick: float, bboExchange: str, snapshotPermissions: int
    ) -> None:
        """Returns exchange map of a particular contract."""

        if DEBUG_TWS_DISPATCH:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")

        if self.__quote_tracker is not None:
            self.__quote_tracker.update(
                tickerId,
                {
                    "min_tick": minTick,
                    "bbo_exchange": bboExchange,
                    "snapshot_permissions": snapshotPermissions,
                },
            )

    def tickString(self, reqId: int, tickType: int, value: str) -> None:
        """Generic string tick for market data snapshot."""
        if DEBUG_TWS_DISPATCH:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")

        tick_name = get_tick_type_name(tickType)
        field_name = TICK_TYPE_TO_FIELD.get(tick_name)  # type: ignore[arg-type]
        if field_name is None:
            return

        if self.__quote_tracker is not None:
            self.__quote_tracker.update(reqId, {field_name: value})

    def tickGeneric(self, reqId: int, tickType: int, value: float) -> None:
        """Generic float tick for market data snapshot."""
        if DEBUG_TWS_DISPATCH:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")

        tick_name = get_tick_type_name(tickType)
        field_name = TICK_TYPE_TO_FIELD.get(tick_name)  # type: ignore[arg-type]
        if field_name is None:
            return

        if self.__quote_tracker is not None:
            self.__quote_tracker.update(reqId, {field_name: value})

    def tickSnapshotEnd(self, reqId: int) -> None:
        """When requesting market data snapshots, this market will indicate the
        snapshot reception is finished."""

        if DEBUG_TWS_DISPATCH:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")

        if self.__quote_tracker is not None:
            self.__quote_tracker.update(reqId, {"snapshot_complete": True})

    # === Order management ===

    def nextValidId(self, orderId: int) -> None:
        if DEBUG_TWS_DISPATCH:
            debug_log(f"{current_fn_name()}, {clean_self(vars())}")
        # Signals connection fully established - safe to make requests
        assert (
            self.__order_tracker is not None or self.__next_order_id is None
        ), "Unexpected nextValidId callback: order tracker already wired."
        self.__next_order_id = orderId
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
        if DEBUG_TWS_DISPATCH:
            debug_log(
                f"{current_fn_name()}, orderId={orderId}, "
                f"symbol={contract.symbol}, status={orderState.status}"
            )

        if self.__order_tracker is not None:
            self.__order_tracker.upsert_order(
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
        if DEBUG_TWS_DISPATCH:
            debug_log(
                f"{current_fn_name()}, orderId={orderId}, status={status}, "
                f"filled={filled}, remaining={remaining}, avgFillPrice={avgFillPrice}"
            )

        # Update TrackedOrder (mutates Order/OrderState, appends OrderFill)
        if self.__order_tracker is not None:
            self.__order_tracker.update_status(
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
        if DEBUG_TWS_DISPATCH:
            debug_log(f"{current_fn_name()}")

        # Mark snapshot complete and resolve pending futures
        if self.__order_tracker is not None:
            self.__order_tracker.mark_snapshot_complete()

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
        if DEBUG_TWS_DISPATCH:
            debug_log(
                f"{current_fn_name()}, account={account}, "
                f"symbol={contract.symbol}, position={position}, avgCost={avgCost}"
            )

        # Build position data dict for domain conversion
        if self.__position_tracker is not None:
            self.__position_tracker.upsert_position(
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
        if DEBUG_TWS_DISPATCH:
            debug_log(f"{current_fn_name()}")

        # Mark snapshot complete and resolve pending futures
        if self.__position_tracker is not None:
            self.__position_tracker.mark_snapshot_complete()

    # === execution callbacks ===

    def execDetails(self, reqId: int, contract: Contract, execution: Execution) -> None:
        """Callback for execution details.

        TWS sends this callback for:
        1. Each execution after reqExecutions() is called
        2. Real-time when an order is filled

        Routes to ExecutionTracker via wired interface which dispatches to stream hooks.
        Commission arrives separately via commissionAndFeesReport().

        Args:
            reqId: Request ID from reqExecutions() or -1 for real-time fills
            contract: Contract the execution is for
            execution: Execution details (execId, price, shares, side, time)
        """
        if DEBUG_TWS_DISPATCH:
            debug_log(
                f"{current_fn_name()}, reqId={reqId}, "
                f"execId={execution.execId}, symbol={contract.symbol}, "
                f"side={execution.side}, shares={execution.shares}, "
                f"price={execution.price}"
            )

        if self.__execution_tracker is not None:
            self.__execution_tracker.upsert_execution(contract, execution)

    def execDetailsEnd(self, reqId: int) -> None:
        """End signal for executions request.

        Called after all execDetails callbacks for reqExecutions().
        Resolves the pending future with accumulated execution data.

        Args:
            reqId: Request ID from reqExecutions()
        """
        if DEBUG_TWS_DISPATCH:
            debug_log(f"{current_fn_name()}, reqId={reqId}")

        if self.__execution_tracker is not None:
            self.__execution_tracker.mark_snapshot_complete()

    def commissionAndFeesReport(
        self, commissionAndFeesReport: CommissionAndFeesReport
    ) -> None:
        """Callback for commission and fees data.

        TWS sends this callback:
        1. Immediately after a trade execution
        2. For each execution after reqExecutions() is called

        Enriches the TrackedExecution with commission data and re-dispatches
        to stream hooks so subscribers receive the updated execution.

        Args:
            commissionAndFeesReport: Commission report linked by execId
        """
        if DEBUG_TWS_DISPATCH:
            debug_log(
                f"{current_fn_name()}, execId={commissionAndFeesReport.execId}, "
                f"commission={commissionAndFeesReport.commissionAndFees}, "
                f"currency={commissionAndFeesReport.currency}"
            )

        if self.__execution_tracker is not None:
            self.__execution_tracker.update_commission(
                commissionAndFeesReport.execId,
                commissionAndFeesReport.commissionAndFees,
            )

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
            if self.__order_tracker is not None:
                self.__order_tracker.raise_error(
                    ProviderException(
                        provider="tws",
                        capability="broker",
                        code=f"PROVIDER_TWS_{errorCode}",
                        message=message,
                    )
                )
            return

        # Position-related errors (global subscription, no reqId)
        if nature == TWSErrorNature.POSITION:
            if self.__position_tracker is not None:
                self.__position_tracker.raise_error(
                    ProviderException(
                        provider="tws",
                        capability="broker",
                        code=f"PROVIDER_TWS_{errorCode}",
                        message=message,
                    )
                )
            return

        # Handle system-wide errors (reqId=-1) separately
        if reqId == NO_VALID_ID:
            log_fn = logger.info if recoverable else logger.error
            log_fn(
                f"TWS system {category} [code={errorCode}, recoverable={recoverable}]: {errorString}"
            )
            return

        # Fallback: non-ORDER errors with a valid reqId matching a known order
        # get routed to that specific order's hooks (not broadcast)
        if (
            self.__order_tracker is not None
            and reqId > 0
            and self.__order_tracker.has_order(reqId)
        ):
            self.__order_tracker.raise_error_for_order(
                reqId,
                ProviderException(
                    provider="tws",
                    capability="broker",
                    code=f"PROVIDER_TWS_{errorCode}",
                    message=message,
                ),
            )
            return

        # Request-related errors - try bars_tracker first, then quote_err
        datafeed_error = ProviderException(
            provider="tws",
            capability="datafeed",
            code=f"PROVIDER_DATAFEED_{errorCode}",
            message=message,
            timestamp=(errorTime // 1000 if errorTime > 10_000_000_000 else errorTime),
        )

        # Try BarsTracker first via wired interface
        if self.__bars_tracker is not None and self.__bars_tracker.raise_error(
            reqId, datafeed_error
        ):
            return

        # Try QuoteTracker via wired interface
        if self.__quote_tracker is not None and self.__quote_tracker.raise_error(
            reqId, datafeed_error
        ):
            return

        # Fallback: legacy request error handling
        tws_key = f"req_{reqId}"
        self._log_handled_error(
            category=TWSErrorCategory.API,
            detail=detail,
            tws_key=tws_key,
            message=message,
            timestamp=(errorTime // 1000 if errorTime > 10_000_000_000 else errorTime),
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


# TODO: optimize trackers for datafeed / broker capabilities (accout / order trackers are not lazy)
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
        self.__ibsocket: IBSocket | None = None
        self.__quote_tracker: QuoteTracker | None = None
        self.__bars_tracker: BarsTracker | None = None
        self.__contract_tracker: ContractTracker | None = None
        self.__position_tracker: PositionTracker | None = None
        self.__execution_tracker: ExecutionTracker | None = None
        self.__order_tracker: OrderTracker | None = None
        self.__account_tracker: AccountTracker | None = None

    @property
    def ibsocket(self) -> IBSocket:
        if not (self.__ibsocket and self.__ibsocket.running):
            logger.warning(
                f"Creating / Recreating new IBSocket with clientId {self._client_id}..."
            )
            if self.__ibsocket:
                self.__ibsocket.disconnect()
            if self.__quote_tracker:
                self.__quote_tracker.reset()
                self.__quote_tracker = None
            if self.__bars_tracker:
                self.__bars_tracker.reset()
                self.__bars_tracker = None
            if self.__contract_tracker:
                self.__contract_tracker.reset()
                self.__contract_tracker = None
            if self.__position_tracker:
                self.__position_tracker.reset()
                self.__position_tracker = None
            if self.__execution_tracker:
                self.__execution_tracker.reset()
                self.__execution_tracker = None
            if self.__account_tracker:
                self.__account_tracker.reset()
                self.__account_tracker = None
            self.__ibsocket = IBSocket()
            self.__ibsocket.connect(
                host=self._host,
                port=self._port,
                client_id=self._client_id,
            )
        return self.__ibsocket

    @property
    def quote_tracker(self) -> QuoteTracker:
        if self.__quote_tracker is None:
            self.__quote_tracker = QuoteTracker(self.ibsocket, self._timeout)

        return self.__quote_tracker

    @property
    def bars_tracker(self) -> BarsTracker:
        """Lazy-initialized BarsTracker for historical/streaming bar data."""
        if self.__bars_tracker is None:
            self.__bars_tracker = BarsTracker(self.ibsocket, self._timeout)
        return self.__bars_tracker

    @property
    def contract_tracker(self) -> ContractTracker:
        """Lazy-initialized ContractTracker for contract caching with SQLite."""
        if self.__contract_tracker is None:
            self.__contract_tracker = ContractTracker(self.ibsocket)
        return self.__contract_tracker

    @property
    def position_tracker(self) -> PositionTracker:
        """Lazy-initialized PositionTracker for position tracking."""
        if self.__position_tracker is None:
            self.__position_tracker = PositionTracker(self.ibsocket)
        return self.__position_tracker

    @property
    def execution_tracker(self) -> ExecutionTracker:
        """Lazy-initialized ExecutionTracker for execution tracking."""
        if self.__execution_tracker is None:
            self.__execution_tracker = ExecutionTracker(self.ibsocket)
        return self.__execution_tracker

    @property
    def order_tracker(self) -> OrderTracker:
        """Lazy-initialized orderTracker for order tracking."""
        if self.__order_tracker is None:
            self.__order_tracker = OrderTracker(self.ibsocket)
        return self.__order_tracker

    @property
    def account_tracker(self) -> AccountTracker:
        """Lazy-initialized AccountTracker for account tracking."""
        if self.__account_tracker is None:
            self.__account_tracker = AccountTracker(self.ibsocket)
        return self.__account_tracker

    # === Contract resolution and caching ===

    async def reqMatchingSymbols(
        self, pattern: str, timeout: float | None = None
    ) -> list[CachedContract]:
        """Search for matching symbols by pattern.

        Uses lazy loading via ContractTracker:
        1. Check in-memory cache
        2. Check SQLite persistence
        3. Fetch from IB API (callback populates tracker)

        Args:
            pattern: Symbol search pattern (e.g., "AAPL", "MSFT")
            timeout: Optional timeout override

        Returns:
            List of CachedContract matching the pattern
        """
        tracker = self.contract_tracker
        return await tracker.get_descriptions(pattern, timeout=timeout or self._timeout)

    async def reqContractDetails(
        self, contract: Contract, timeout: float | None = None
    ) -> CachedContract:
        """Get detailed contract information.
        args:
            contract: Contract with symbol and exchange (or conId)
            timeout: Optional timeout override
        Returns:
            CachedContract with full details
        Raises:
            ProviderException: If contract not found or request fails
        """
        return await self.contract_tracker.get_details(
            contract, timeout=timeout or self._timeout
        )

    async def reqTickerDetails(
        self,
        ticker: str,
        timeout: float | None = None,
    ) -> CachedContract:
        """Get detailed contract information by ticker string.
        Args:
            ticker: Ticker string (e.g., "AAPL", "MSFT", "GOOG")
            timeout: Optional timeout override
        Returns:
            CachedContract with full details
        Raises:
            ProviderException: If contract not found or request fails
        """

        symbol, primaryExchange, sec_type, _ = parse_ticker(ticker)
        contract = Contract()
        contract.symbol = symbol
        contract.secType = sec_type
        contract.primaryExchange = primaryExchange

        return await self.reqContractDetails(contract, timeout=timeout)

    # === Historical data snapshot (one-time pattern) ===

    async def reqHistoricalData(
        self,
        contract: Contract,
        end_date_time: str,
        duration_str: str,
        bar_size: str,
        timeout: float | None = None,
    ) -> list[Bar]:
        """Request historical bars using BarsTracker.

        Args:
            contract: Contract with ticker name and resolved contract
            end_date_time: End datetime string (TWS format) or empty for "now"
            duration_str: Duration string (e.g., "2 D")
            bar_size: TWS bar size string (e.g., "5 mins")
            timeout: Optional timeout override

        Returns:
            List of Bar domain models sorted by time
        """
        return await self.bars_tracker.request(
            contract,
            bar_size,
            end_date_time,
            duration_str,
            timeout=timeout,
        )

    async def reqQuoteSnapshot(
        self,
        contract: CachedContract,
        timeout: float | None = None,
    ) -> QuoteData:
        """Request a one-time market data snapshot for the given contract.

        Uses TWS reqMktData with snapshot flag to get current market data.

        Args:
            contract: CachedContract to get quote for
            timeout: Optional timeout override
        Returns:
            QuoteData with current market data
        """
        return await self.quote_tracker.request(contract, timeout=timeout)

    # === Real-time data subscriptions (continuous pattern) ===

    def reqBarDataStream(
        self,
        contract: Contract,
        bar_size: str,
        callback: Callable[
            [Bar],
            Coroutine[Any, Any, None],
        ],
        on_error: Callable[[ProviderException], Coroutine[Any, Any, None]],
        # **kwargs: Any,
    ) -> str:
        return self.bars_tracker.subscribe(
            contract,
            bar_size,
            callback,
            on_error,
        )

    def reqMktDataStream(
        self,
        contract: CachedContract,
        callback: Callable[
            [QuoteData],
            Coroutine[Any, Any, None],
        ],
        on_error: Callable[[ProviderException], Coroutine[Any, Any, None]],
        # **kwargs: Any,
    ) -> str:
        """Request a real-time market data subscription (bars or market data)."""
        return self.quote_tracker.subscribe(
            contract,
            callback,
            on_error,
        )

    def cancelDataSubscription(self, stream_key: str) -> None:
        """Cancel a real-time data subscription (bars or market data)."""
        self.quote_tracker.unsubscribe(stream_key)
        self.bars_tracker.unsubscribe(stream_key)

    # === Order management ===

    async def placeOcaGroup(
        self,
        contract: Contract,
        orders: list[Order],
        oca_group: str,
        oca_type: int = 1,
        timeout: float | None = None,
    ) -> list[TrackedOrder]:
        """Place an OCA (One-Cancels-All) order group via TWS.

        Args:
            contract: Contract the orders are for
            orders: List of orders in the OCA group
            oca_group: OCA group name
            oca_type: OCA type (1=Cancel with block, 2=Reduce with block, 3=Reduce without block)
            timeout: Request timeout in seconds
        Returns:
            List of TrackedOrder objects for the placed orders
        """
        return await self.order_tracker.placeOcaGroup(
            contract, orders, oca_group, oca_type, timeout=timeout or self._timeout
        )

    async def placeOrderGroup(
        self,
        contract: Contract,
        parent: Order,
        children: list[Order],
        timeout: float | None = None,
    ) -> tuple[TrackedOrder, list[TrackedOrder]]:
        """Place a parent-child order group via TWS.

        Args:
            contract: Contract the orders are for
            parent: Parent order
            children: List of child orders
            timeout: Request timeout in seconds
        Returns:
            Tuple of (parent TrackedOrder, list of child TrackedOrders)
        """
        return await self.order_tracker.placeOrderGroup(
            contract, parent, children, timeout=timeout or self._timeout
        )

    async def placeWhatifOrder(
        self, contract: Contract, order: Order, timeout: float | None = None
    ) -> TrackedOrder:
        """Place a what-if order via TWS (simulated order)."""
        return await self.order_tracker.placeWhatifOrder(
            contract, order, timeout=timeout or self._timeout
        )

    async def cancelOrder(
        self, order_id: int, timeout: float | None = None
    ) -> TrackedOrder:
        """Cancel an order via TWS.

        Args:
            order_id: Order ID to cancel
        """

        return await self.order_tracker.cancelOrder(
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

        return await self.order_tracker.reqOpenOrders(timeout=timeout or self._timeout)

    async def reqPositions(self, timeout: float | None = None) -> list[TrackedPosition]:
        """Request all positions for this client (snapshot).

        Returns positions for all accounts. Each position triggers
        position() callback, then positionEnd().

        Args:
            timeout: Request timeout in seconds

        Returns:
            List of TrackedPosition objects (one per position)
        """
        return await self.position_tracker.all_positions(
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
        return await self.account_tracker.reqAccountSummary(
            timeout=timeout or self._timeout
        )

    async def reqExecutions(
        self, timeout: float | None = None
    ) -> list[TrackedExecution]:
        """Request all executions for this client (snapshot).

        Returns executions for the past 24 hours (or longer if Trade Log is open).
        Each execution triggers execDetails() callback, then execDetailsEnd().

        Args:
            timeout: Request timeout in seconds

        Returns:
            List of TrackedExecution objects (one per execution)
        """
        return await self.execution_tracker.all_executions(
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
        stream_key = self.order_tracker.create_stream_hook(
            asyncio.get_event_loop(),
            callback,
            on_error,
        )

        return stream_key

    def reqPositionsStream(
        self,
        callback: Callable[[TrackedPosition], Coroutine[Any, Any, None]],
        on_error: Callable[[ProviderException], Coroutine[Any, Any, None]],
    ) -> str:
        """Create position stream subscription.

        Returns stream_key for later unsubscription.
        """
        return self.position_tracker.create_stream_hook(
            callback,
            on_error,
        )

    def reqAccountStream(
        self,
        callback: Callable[[TrackedAccount], Coroutine[Any, Any, None]],
        on_error: Callable[[ProviderException], Coroutine[Any, Any, None]],
    ) -> str:
        stream_key = self.account_tracker.create_stream_hook(
            callback,
            on_error,
        )
        return stream_key

    def reqExecutionsStream(
        self,
        callback: Callable[[TrackedExecution], Coroutine[Any, Any, None]],
        on_error: Callable[[ProviderException], Coroutine[Any, Any, None]],
    ) -> str:
        """Create execution stream subscription.

        Returns stream_key for later unsubscription.
        """
        return self.execution_tracker.create_stream_hook(
            callback,
            on_error,
        )

    def cancelBrokerStream(self, stream_key: str) -> None:
        """Cancel a real-time broker subscription (orders, positions, or accounts)."""
        self.position_tracker.remove_stream_hook(stream_key)
        self.execution_tracker.remove_stream_hook(stream_key)
        self.order_tracker.remove_stream_hook(stream_key)
        self.account_tracker.remove_stream_hook(stream_key)

        # Cancel underlying TWS subscriptions if this was an account stream
        # TODO: Track stream_key → pnl_req_id mapping to cancel P&L subscription
        # self.account_tracker.___cancel_account_subscriptions(pnl_req_id)

    def shutdown(self) -> None:
        """Shutdown the TWSClient and underlying IBSocket."""
        if self.__ibsocket and self.__ibsocket.running:
            self.__ibsocket.disconnect()
