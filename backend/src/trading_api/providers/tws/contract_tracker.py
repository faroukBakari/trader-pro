"""Contract tracking for TWS integration with SQLite persistence.

Provides caching for contract data with two-tier storage:
- SQLite: Persists ContractDescriptions (immutable instrument identity)
- In-Memory: ContractDetails (session-dependent, mutable metadata)

Follows the Tracker pattern established by QuoteTracker/BarsTracker with wiring interface.
SQLiteContractCache is internal and not exposed outside this module.
"""

import asyncio
import json
import logging
import os
import sqlite3
import threading
import uuid
from typing import Any, cast

from ibapi.contract import Contract, ContractDescription, ContractDetails
from ibapi.message import OUT

from trading_api.models.exceptions import ProviderException
from trading_api.providers.tws.cached_contract import CachedContract
from trading_api.providers.tws.tws_mappers import ticker_name
from trading_api.providers.tws.wiring_interfaces import (
    ContractTrackerCBWiringInterface,
    IbSocketWiringInterface,
)

logger = logging.getLogger(__name__)

DEBUG_TWS_REQUEST = os.environ.get("DEBUG_TWS_REQUEST") == "true"
DEBUG_TWS_CACHE = os.environ.get("DEBUG_TWS_CACHE") == "true"

# Default cache location
DEFAULT_CACHE_PATH = ".local/DB/sqlite/contracts.db"


def get_cache_path() -> str:
    """Get contract cache path from env var or default."""
    return os.environ.get("TWS_CONTRACT_CACHE_PATH", DEFAULT_CACHE_PATH)


class _ThreadLocalConnection:
    """Typed wrapper for thread-local SQLite connection."""

    conn: sqlite3.Connection | None = None


class SQLiteContractCache:
    """Internal SQLite persistence layer for ContractDescriptions.

    NOT exposed outside ContractTracker. Thread-safe via connection-per-thread pattern.

    Features:
    - WAL mode for concurrent read/write
    - Upsert semantics (ON CONFLICT)
    - Symbol prefix index for fast searches
    """

    def __init__(self, db_path: str) -> None:
        """Initialize SQLite cache.

        Args:
            db_path: Path to SQLite database file. Directory created if needed.
        """
        self._db_path = db_path
        self._local = cast(_ThreadLocalConnection, threading.local())

        # Ensure directory exists
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        # Initialize schema on first connection
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local connection (created on first access)."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self._db_path)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_schema(self) -> None:
        """Initialize database schema with WAL mode."""
        conn = self._get_connection()
        conn.executescript(
            """
            PRAGMA journal_mode=WAL;
            PRAGMA synchronous=NORMAL;

            CREATE TABLE IF NOT EXISTS contract_descriptions (
                con_id INTEGER PRIMARY KEY,
                symbol TEXT NOT NULL,
                sec_type TEXT NOT NULL,
                primary_exchange TEXT NOT NULL,
                currency TEXT NOT NULL,
                derivative_sec_types TEXT,
                description TEXT,
                created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
            );

            CREATE INDEX IF NOT EXISTS idx_symbol
                ON contract_descriptions(symbol);
            CREATE INDEX IF NOT EXISTS idx_symbol_sec_exchange
                ON contract_descriptions(symbol, sec_type, primary_exchange);
        """
        )
        conn.commit()

    def upsert_many(self, descriptions: list[dict[str, Any]]) -> None:
        """Insert or update multiple contract descriptions.

        Uses INSERT OR REPLACE for upsert semantics.

        Args:
            descriptions: List of dicts from CachedContract.to_dict()
        """
        if not descriptions:
            return

        conn = self._get_connection()
        conn.executemany(
            """
            INSERT OR REPLACE INTO contract_descriptions
                (con_id, symbol, sec_type, primary_exchange, currency,
                 derivative_sec_types, description)
            VALUES
                (:con_id, :symbol, :sec_type, :primary_exchange, :currency,
                 :derivative_sec_types, :description)
            """,
            [
                {
                    **desc,
                    "derivative_sec_types": json.dumps(
                        desc.get("derivative_sec_types") or []
                    ),
                }
                for desc in descriptions
            ],
        )
        conn.commit()

    def get_by_symbol_prefix(self, prefix: str) -> list[dict[str, Any]]:
        """Get contract descriptions matching symbol prefix.

        Args:
            prefix: Symbol prefix (e.g., "AAPL", "AA")

        Returns:
            List of dicts suitable for CachedContract.from_dict()
        """
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT * FROM contract_descriptions WHERE symbol LIKE ? || '%'",
            (prefix,),
        )
        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        """Convert SQLite row to dict for CachedContract.from_dict()."""
        return {
            "con_id": row["con_id"],
            "symbol": row["symbol"],
            "sec_type": row["sec_type"],
            "primary_exchange": row["primary_exchange"],
            "currency": row["currency"],
            "derivative_sec_types": json.loads(row["derivative_sec_types"] or "[]"),
            "description": row["description"] or "",
        }

    def close(self) -> None:
        """Close thread-local connection if open."""
        if hasattr(self._local, "conn") and self._local.conn is not None:
            self._local.conn.close()
            self._local.conn = None


def compute_routed_description(
    contract: Contract,
) -> str:
    """Compute routing exchange aware description as business identifier."""
    ticker = ticker_name(contract)
    route_description = f"{contract.exchange or contract.primaryExchange}>>{ticker}"
    return route_description


def resolve_snapshot(
    fut: asyncio.Future[list[CachedContract]], cached: list[CachedContract]
) -> None:
    if not fut.done():
        fut.set_result(cached)


# TODO: wire is tradable calls here maybe
class ContractTracker(ContractTrackerCBWiringInterface):
    """Contract tracking with SQLite persistence for descriptions.

    Follows the Tracker pattern (like QuoteTracker/BarsTracker):
    - TWSClient owns ContractTracker
    - IBSocket routes callbacks via wired interface
    - Main thread queries tracker for cached data

    Two-tier caching:
    - _descriptions: In-memory cache of ContractDescriptions (loaded from SQLite)
    - _details: In-memory cache of ContractDetails (session-only, not persisted)

    Request Patterns:
    - Descriptions: request_descriptions(pattern) → symbolSamples callback
    - Details: request_details(contract) → contractDetails/contractDetailsEnd callbacks

    Thread Safety:
        - Envelope (reset, close): main thread
        - Content (upsert): reader thread writes via wired interface
        - SQLite: thread-local connections
        - Pending requests: protected by tracker_lock
    """

    def __init__(
        self, ibsocket: IbSocketWiringInterface, db_path: str | None = None
    ) -> None:
        """Initialize ContractTracker.

        Args:
            ibsocket: IbSocketWiringInterface for TWS communication and wiring
            db_path: Path to SQLite database. Defaults to TWS_CONTRACT_CACHE_PATH
                     env var or ".local/DB/sqlite/contracts.db"
        """
        self.tracker_lock = threading.Lock()
        ibsocket.wire_contract_tracker(self)
        self.ibsocket = ibsocket

        self._db_path = db_path or os.environ.get(
            "TWS_CONTRACT_CACHE_PATH", DEFAULT_CACHE_PATH
        )
        assert self._db_path, "Contract cache path must be specified"
        self._sqlite = SQLiteContractCache(self._db_path)

        self._cached_contracts: dict[
            str, CachedContract
        ] = {}  # in-memory cache of CachedContract by ticker

        # contract description requests
        self._descriptions: dict[
            int, CachedContract
        ] = {}  # Full descriptions (memory-only) req_id → list of CachedContract
        self._pending_descriptions: dict[
            int,
            dict[
                str,
                tuple[asyncio.AbstractEventLoop, asyncio.Future[list[CachedContract]]],
            ],
        ] = {}
        self._descriptions_to_req_id: dict[str, int] = {}

        # contract details requests
        self._details: dict[
            int, list[CachedContract]
        ] = {}  # contract details (memory-only) req_id → list of CachedContract
        self._completed_details_request_ids: set[int] = set()
        self._pending_details: dict[
            int,
            dict[
                str,
                tuple[
                    asyncio.AbstractEventLoop,
                    asyncio.Future[list[CachedContract]],
                ],
            ],
        ] = {}
        self._details_to_req_id: dict[str, int] = {}

    # === TWS Protocol Hooks (TWS Request building methods) ===

    def _send_descriptions_req(self, pattern: str) -> int:
        """Request symbol matching from TWS.

        Internalizes OUT.REQ_MATCHING_SYMBOLS protocol.

        Args:
            pattern: Symbol pattern to search for

        Returns:
            req_id: TWS request ID allocated for this request
        """
        req_id = self._descriptions_to_req_id.get(pattern)
        if req_id is not None:
            if DEBUG_TWS_CACHE:
                logger.info(f"in-memory cache hit for pattern='{pattern}'")
            return req_id

        with self.tracker_lock:
            req_id = self._descriptions_to_req_id[pattern] = self.ibsocket.next_req_id

        self.ibsocket.send_message(OUT.REQ_MATCHING_SYMBOLS, [req_id, pattern])
        if DEBUG_TWS_REQUEST:
            logger.info(f"requested symbolSamples reqId={req_id} pattern='{pattern}'")

        return req_id

    def _send_details_req(self, contract: Contract) -> int:
        """Request contract details from TWS.

        Internalizes OUT.REQ_CONTRACT_DATA protocol.

        Args:
            contract: Contract to request details for

        Returns:
            req_id: TWS request ID allocated for this request
        """

        business_key = compute_routed_description(contract)
        req_id = self._details_to_req_id.get(business_key)
        if req_id is not None:
            if DEBUG_TWS_CACHE:
                logger.info(
                    f"in-memory cache hit for routed_description='{business_key}'"
                )
            return req_id

        req_id = self.ibsocket.next_req_id
        with self.tracker_lock:
            req_id = self._details_to_req_id[business_key] = self.ibsocket.next_req_id

        VERSION = 8
        fields: list[object] = [
            VERSION,
            req_id,
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
            logger.info(
                f"requested contractDetails reqId={req_id} symbol='{contract.symbol}'"
            )

        return req_id

    # === Wiring Interface Implementation (reader thread callbacks) ===

    def update_descriptions(
        self, req_id: int, descriptions: list[ContractDescription]
    ) -> None:
        """Handle symbolSamples callback from IBSocket.

        Persists to SQLite, updates in-memory cache, resolves pending Future.

        Args:
            req_id: TWS request ID
            descriptions: List of ContractDescription from TWS
        """
        result = [
            CachedContract.from_contract_description(desc)
            for desc in descriptions
            if desc.contract.conId > 0
        ]

        # Resolve pending Future
        with self.tracker_lock:
            pending_descriptions_hooks = list(
                self._pending_descriptions.setdefault(req_id, {}).values()
            )

        for loop, future in pending_descriptions_hooks:
            loop.call_soon_threadsafe(resolve_snapshot, future, result)

    def update_details(self, req_id: int, details: ContractDetails) -> None:
        """Handle contractDetails callback from IBSocket.

        Accumulates details until flag_details_complete is called.

        Args:
            req_id: TWS request ID
            details: ContractDetails from TWS
        """
        # No auto-caching here - Only qualified cache from _load_and_cache
        # Accumulate details
        results = CachedContract.from_contract_details(details)
        with self.tracker_lock:
            accumulated = self._details.setdefault(req_id, [])
        accumulated.append(results)

    def flag_details_complete(self, req_id: int) -> None:
        """Handle contractDetailsEnd callback from IBSocket.

        Resolves pending Future with accumulated details.

        Args:
            req_id: TWS request ID
        """
        with self.tracker_lock:
            pending_details_hooks = list(
                self._pending_details.setdefault(req_id, {}).values()
            )
            accumulated = self._details.setdefault(req_id, [])
            self._completed_details_request_ids.add(req_id)

        for loop, future in pending_details_hooks:
            loop.call_soon_threadsafe(resolve_snapshot, future, accumulated)

    def raise_error(self, req_id: int, exception: ProviderException) -> bool:
        """Handle error callback from IBSocket.

        Propagates error to pending Future.

        Args:
            req_id: TWS request ID
            exception: ProviderException to propagate

        Returns:
            True if error was handled (pending request found), False otherwise
        """
        with self.tracker_lock:
            pending_description = list(
                self._pending_descriptions.pop(req_id, {}).values()
            )
            pending_detail = list(self._pending_details.pop(req_id, {}).values())
            self._completed_details_request_ids.discard(req_id)
            self._descriptions.pop(req_id, None)
            self._details.pop(req_id, None)
            business_key = next(
                iter(
                    (k for k, v in self._descriptions_to_req_id.items() if v == req_id),
                ),
                None,
            )
            if business_key:
                self._descriptions_to_req_id.pop(business_key, None)
            business_key = next(
                iter(
                    (k for k, v in self._details_to_req_id.items() if v == req_id),
                ),
                None,
            )
            if business_key:
                self._details_to_req_id.pop(business_key, None)

        if pending_description:
            for loop, future in pending_description:
                loop.call_soon_threadsafe(future.set_exception, exception)
            return True

        if pending_detail:
            for loop, future in pending_detail:
                loop.call_soon_threadsafe(future.set_exception, exception)
            return True

        return False

    # === Async TWS API Requests (main thread) ===

    async def _request_descriptions(
        self, pattern: str, timeout: float = 10.0
    ) -> list[CachedContract]:
        """Request symbol matching from TWS and wait for results.

        Args:
            pattern: Symbol pattern to search for
            timeout: Timeout in seconds

        Returns:
            List of matching CachedContracts
        """

        key = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        future: asyncio.Future[list[CachedContract]] = loop.create_future()

        req_id = self._send_descriptions_req(pattern)

        with self.tracker_lock:
            pending_descriptions = self._pending_descriptions.setdefault(req_id, {})
            pending_descriptions[key] = (loop, future)

        if req_id in self._descriptions:
            future.set_result([self._descriptions[req_id]])

        try:
            results = await asyncio.wait_for(future, timeout=timeout)
            return results
        finally:
            with self.tracker_lock:
                pending_descriptions.pop(key, None)

    async def _request_details(
        self, contract: Contract, timeout: float = 10.0
    ) -> list[CachedContract]:
        """Request contract details from TWS and wait for results.

        Args:
            contract: Contract to request details for
            timeout: Timeout in seconds

        Returns:
            List of CachedContracts with full details
        """
        key = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        future: asyncio.Future[list[CachedContract]] = loop.create_future()

        req_id = self._send_details_req(contract)

        with self.tracker_lock:
            pending_details = self._pending_details.setdefault(req_id, {})
            pending_details[key] = (loop, future)

        if req_id in self._details:
            future.set_result(self._details[req_id])

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        finally:
            with self.tracker_lock:
                pending_details.pop(key, None)

    # === Cache management methods (main thread) ===

    def _cache_results(self, result: list[CachedContract]) -> None:
        """Upsert ContractDescriptions from symbolSamples callback.

        Persists to SQLite AND adds to in-memory cache.
        Called from reader thread (symbolSamples callback).

        Args:
            descriptions: List of CachedContract from TWS callback

        Returns:
            List of CachedContracts created/updated
        """

        to_extend = [
            contract
            for contract in result
            if contract.has_full_details and contract.ticker in self._cached_contracts
        ]

        if to_extend:
            for contract in to_extend:
                cached = self._cached_contracts[contract.ticker]
                cached.update_from_details(contract)

        to_create = [
            desc for desc in result if desc.ticker not in self._cached_contracts
        ]

        if to_create:
            # Update in-memory cache
            self._cached_contracts.update(
                {cached.ticker: cached for cached in to_create}
            )
            # Persist to SQLite
            dicts_to_persist = [cached.to_dict() for cached in to_create]
            try:
                self._sqlite.upsert_many(dicts_to_persist)
            except Exception as e:
                logger.warning(
                    f"Failed to persist contract descriptions to SQLite: {e}"
                )

    async def _fetch_and_cache(
        self, contract: Contract, timeout: float
    ) -> CachedContract:
        details_list = list(
            {
                d.contract.conId: d
                for d in (await self._request_details(contract, timeout=timeout))
            }.values()
        )
        # details.contract = con  # remove this! tests should not rely on it
        cached_list = []
        for details in details_list:
            overnight_hours: str | None = None
            if darkpool_contract := details.build_darkpool_contract():
                darkpool_details = next(
                    iter(
                        await self._request_details(darkpool_contract, timeout=timeout)
                    )
                )
                overnight_hours = darkpool_details.tradingHours
            cached = CachedContract.from_contract_details(details, overnight_hours)
            cached_list.append(cached)

        self._cache_results(cached_list)
        return next(iter(cached_list))

    def _search_cache(self, pattern: str) -> list[CachedContract]:
        """Get contracts matching symbol prefix (lazy loading: memory → SQLite).

        Args:
            pattern: Symbol prefix (e.g., "AAPL", "AA")
        Returns:
            List of matching CachedContracts (may be empty)
        """

        # 1- I feel lucky: exact match in-memory
        exact_match = self._cached_contracts.get(pattern)
        if exact_match:
            return [exact_match]

        parts = pattern.split(":", 1)
        symbol = parts[-1]

        # 1. In depth memory search
        result = [
            cached
            for cached in self._cached_contracts.values()
            if symbol in cached.ticker
        ]

        # 2. Check SQLite
        if not result:
            rows = self._sqlite.get_by_symbol_prefix(symbol)
            result = [CachedContract.from_dict(data) for data in rows]
            self._cached_contracts.update({cached.ticker: cached for cached in result})

        # 3. Filter by exchange if provided
        exchange = parts[0] if len(parts) == 2 else None
        if exchange:
            result = [
                cached for cached in result if (exchange in cached.valid_exchanges)
            ]

        return result

    # === Exposed Lookup Methods (main thread) ===

    async def get_descriptions(
        self, pattern: str, timeout: float = 10.0
    ) -> list[CachedContract]:
        """Request symbol matching from TWS and wait for results.

        Args:
            pattern: Symbol pattern to search for
            timeout: Timeout in seconds

        Returns:
            List of matching CachedContracts
        """

        cached_list = self._search_cache(pattern)
        if cached_list:
            if DEBUG_TWS_CACHE:
                logger.info(f"cache hit for pattern='{pattern}'")
            return cached_list

        cached_list = await self._request_descriptions(pattern, timeout=timeout)
        self._cache_results(cached_list)

        return cached_list

    async def get_details(self, contract: Contract, timeout: float) -> CachedContract:
        """Get detailed contract information.
        args:
            contract: Contract with symbol and exchange (or conId)
            timeout: Optional timeout override
        Returns:
            CachedContract with full details
        Raises:
            ProviderException: If contract not found or request fails
        """
        assert contract.symbol, "Contract must have symbol"
        assert (
            contract.primaryExchange or contract.exchange
        ), "Contract must have primaryExchange or exchange"

        ticker = ticker_name(contract)

        cached_list: list[CachedContract] = self._search_cache(ticker)
        if cached_list:
            details = next(iter([c for c in cached_list if c.has_full_details]), None)
            if details:
                if DEBUG_TWS_CACHE:
                    logger.info(
                        f"get_details cache hit for conId "
                        f"{ticker} => ({details.contract.conId})"
                    )
                return details
        else:
            cached_list = await self.get_descriptions(contract.symbol, timeout=timeout)

        cached_list = await asyncio.gather(
            *[
                self._fetch_and_cache(con, timeout=timeout)
                for con in {
                    cached.contract.conId: cached.contract for cached in cached_list
                }.values()
            ]
        )

        if not cached_list:
            raise ProviderException(
                code="PROVIDER_TWS_CONTRACT_NOT_FOUND",
                message=f"Contract details not found for {ticker}",
                provider="tws",
                capability="datafeed",
            )

        return next(iter(cached_list))

    # === Session Management ===

    def reset(self) -> None:
        """Full reset - clear all in-memory caches.

        SQLite data is preserved (immutable contract descriptions).
        Called from main thread.
        """
        with self.tracker_lock:
            self._descriptions.clear()
            self._details.clear()
            self._pending_descriptions.clear()
            self._pending_details.clear()
            self._descriptions_to_req_id.clear()
            self._details_to_req_id.clear()
            self._cached_contracts.clear()

    def close(self) -> None:
        """Close SQLite connection."""
        self._sqlite.close()
