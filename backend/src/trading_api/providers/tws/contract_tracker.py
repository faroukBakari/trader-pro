"""Contract tracking for TWS integration with SQLite persistence.

Provides caching for contract data with two-tier storage:
- SQLite: Persists ContractDescriptions (immutable instrument identity)
- In-Memory: ContractDetails (session-dependent, mutable metadata)

Follows the Tracker pattern established by OrderTracker/PositionTracker/AccountTracker.
SQLiteContractCache is internal and not exposed outside this module.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from typing import TYPE_CHECKING, cast

from ibapi.contract import ContractDescription, ContractDetails

from trading_api.providers.tws.cached_contract import CachedContract

if TYPE_CHECKING:
    from typing import Any

logger = logging.getLogger(__name__)

# Default cache location
DEFAULT_CACHE_PATH = ".cache/contracts.db"


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

    def get_by_con_id(self, con_id: int) -> dict[str, Any] | None:
        """Get contract description by conId.

        Args:
            con_id: Contract ID

        Returns:
            Dict suitable for CachedContract.from_dict(), or None if not found
        """
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT * FROM contract_descriptions WHERE con_id = ?",
            (con_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

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

    def get_by_ticker(self, ticker: str) -> dict[str, Any] | None:
        """Get contract description by exact ticker match.

        Ticker format: "PRIMARY_EXCHANGE:SYMBOL" (e.g., "NASDAQ:AAPL")

        Args:
            ticker: Ticker string

        Returns:
            Dict suitable for CachedContract.from_dict(), or None if not found
        """
        # Parse ticker: "EXCHANGE:SYMBOL" or just "SYMBOL"
        if ":" in ticker:
            parts = ticker.split(":")
            primary_exchange = parts[0]
            symbol = parts[1]
        else:
            primary_exchange = None
            symbol = ticker

        conn = self._get_connection()
        if primary_exchange:
            cursor = conn.execute(
                """SELECT * FROM contract_descriptions
                   WHERE symbol = ? AND primary_exchange = ?""",
                (symbol, primary_exchange),
            )
        else:
            cursor = conn.execute(
                "SELECT * FROM contract_descriptions WHERE symbol = ?",
                (symbol,),
            )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

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


class ContractTracker:
    """Contract tracking with SQLite persistence for descriptions.

    Follows the Tracker pattern (like OrderTracker/PositionTracker):
    - IBSocket owns ContractTracker
    - Callbacks populate tracker from reader thread
    - Main thread queries tracker for cached data

    Two-tier caching:
    - _descriptions: In-memory cache of ContractDescriptions (loaded from SQLite)
    - _details: In-memory cache of ContractDetails (session-only, not persisted)

    Lazy Loading Flow:
        get_by_*() → in-memory → SQLite → return None (caller fetches from IB API)

    Thread Safety:
        - Envelope (reset, close): main thread
        - Content (upsert): reader thread writes, main thread reads
        - SQLite: thread-local connections
    """

    def __init__(self, db_path: str | None = None) -> None:
        """Initialize ContractTracker.

        Args:
            db_path: Path to SQLite database. Defaults to TWS_CONTRACT_CACHE_PATH
                     env var or ".cache/contracts.db"
        """
        self._db_path = db_path or os.environ.get(
            "TWS_CONTRACT_CACHE_PATH", DEFAULT_CACHE_PATH
        )
        assert self._db_path, "Contract cache path must be specified"
        self._sqlite = SQLiteContractCache(self._db_path)

        # In-memory caches: conId → CachedContract
        self._descriptions: dict[int, CachedContract] = {}  # From SQLite + API
        self._details: dict[int, CachedContract] = {}  # Full details (memory-only)

    # === Lookup Methods (main thread) ===

    def get_by_con_id(self, con_id: int) -> CachedContract | None:
        """Get contract by conId (lazy loading: memory → SQLite).

        Args:
            con_id: Contract ID

        Returns:
            CachedContract or None if not found anywhere
        """
        # 1. Check in-memory (full details first)
        if con_id in self._details:
            return self._details[con_id]
        if con_id in self._descriptions:
            return self._descriptions[con_id]

        # 2. Check SQLite
        data = self._sqlite.get_by_con_id(con_id)
        if data:
            cached = CachedContract.from_dict(data)
            self._descriptions[con_id] = cached
            return cached

        # 3. Not found - caller should fetch from IB API
        return None

    def get_by_ticker(self, ticker: str) -> CachedContract | None:
        """Get contract by exact ticker match (lazy loading: memory → SQLite).

        Ticker format: "PRIMARY_EXCHANGE:SYMBOL" (e.g., "NASDAQ:AAPL")

        Args:
            ticker: Ticker string

        Returns:
            CachedContract or None if not found anywhere
        """
        # 1. Check in-memory (full details first, then descriptions)
        for cache in (self._details, self._descriptions):
            for cached in cache.values():
                if cached.ticker == ticker:
                    return cached

        # 2. Check SQLite
        data = self._sqlite.get_by_ticker(ticker)
        if data:
            cached = CachedContract.from_dict(data)
            self._descriptions[cached.con_id] = cached
            return cached

        # 3. Not found
        return None

    def get_by_symbol_prefix(self, prefix: str) -> list[CachedContract]:
        """Get contracts matching symbol prefix (lazy loading: memory → SQLite).

        Args:
            prefix: Symbol prefix (e.g., "AAPL", "AA")

        Returns:
            List of matching CachedContracts (may be empty)
        """
        # 1. Check in-memory
        memory_matches = [
            cached
            for cached in self._descriptions.values()
            if cached.contract.symbol.startswith(prefix)
        ]
        if memory_matches:
            return memory_matches

        # 2. Check SQLite
        rows = self._sqlite.get_by_symbol_prefix(prefix)
        if rows:
            result = []
            for data in rows:
                cached = CachedContract.from_dict(data)
                self._descriptions[cached.con_id] = cached
                result.append(cached)
            return result

        # 3. Not found - caller should fetch from IB API
        return []

    def get_full_details(self, con_id: int) -> CachedContract | None:
        """Get contract with full details (memory-only, no SQLite fallback).

        Use for operations requiring tradingHours, validExchanges, etc.

        Args:
            con_id: Contract ID

        Returns:
            CachedContract with has_full_details=True, or None
        """
        return self._details.get(con_id)

    # === Upsert Methods (reader thread via callbacks) ===

    def upsert_descriptions(
        self, descriptions: list[ContractDescription]
    ) -> list[CachedContract]:
        """Upsert ContractDescriptions from symbolSamples callback.

        Persists to SQLite AND adds to in-memory cache.
        Called from reader thread (symbolSamples callback).

        Args:
            descriptions: List of ContractDescription from TWS callback

        Returns:
            List of CachedContracts created/updated
        """
        if not descriptions:
            return []

        result: list[CachedContract] = []
        dicts_to_persist: list[dict[str, Any]] = []

        for desc in descriptions:
            if desc.contract.conId <= 0:
                continue  # Skip invalid conIds

            cached = CachedContract.from_contract_description(desc)
            self._descriptions[cached.con_id] = cached
            dicts_to_persist.append(cached.to_dict())
            result.append(cached)

        # Persist to SQLite
        if dicts_to_persist:
            try:
                self._sqlite.upsert_many(dicts_to_persist)
            except Exception as e:
                logger.warning(
                    f"Failed to persist contract descriptions to SQLite: {e}"
                )

        return result

    def upsert_details(
        self, details: ContractDetails, overnight_hours: str | None = None
    ) -> CachedContract:
        """Upsert ContractDetails from contractDetails callback.

        In-memory only - NOT persisted to SQLite (ContractDetails are mutable).
        Called from reader thread (contractDetails callback).

        Args:
            details: ContractDetails from TWS callback
            overnight_hours: Optional overnight trading hours (from OVERNIGHT exchange)

        Returns:
            CachedContract with full details
        """
        cached = CachedContract.from_contract_details(details, overnight_hours)
        self._details[cached.con_id] = cached
        return cached

    # === Session Management ===

    def clear_details_cache(self) -> None:
        """Clear in-memory ContractDetails cache.

        Called at session end or on TTL expiry. Descriptions remain in SQLite.
        """
        self._details.clear()

    def reset(self) -> None:
        """Full reset - clear all in-memory caches.

        SQLite data is preserved (immutable contract descriptions).
        Called from main thread.
        """
        self._descriptions.clear()
        self._details.clear()

    def close(self) -> None:
        """Close SQLite connection."""
        self._sqlite.close()
