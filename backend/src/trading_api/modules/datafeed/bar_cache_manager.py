"""
Bar cache manager for read-through caching of historical bar data.

Manages pending and covered ranges to support gap detection and
prevent duplicate provider requests.

Public API (minimal surface):
- create() - Factory method
- try_add_pending() - Atomically acquire a pending range (exclusion constraint)
- mark_covered() - Complete fetch: remove pending, add covered (atomic)
- find_missing_ranges() - Gap detection for cache-first pattern
- clear() - Cleanup for testing/reset
"""

import logging
import time
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from trading_api.models.exceptions import TradingApiException
from trading_api.models.market import CoveredRange, PendingRange, Resolution, TimeRange
from trading_api.shared.config import Settings
from trading_api.shared.datastore_interface import (
    DatastoreInterface,
    RangeQueryTableInterface,
    TableInterface,
)
from trading_api.types import IntRange, StorageType

logger = logging.getLogger(__name__)


def _primary_key(symbol: str, resolution: Resolution, time_range: TimeRange) -> str:
    """Create unique primary key for a range."""
    return f"{symbol}_{resolution.value}_{time_range.start}_{time_range.end}"


def _lookup_key(symbol: str, resolution: Resolution) -> str:
    """Create lookup key from symbol and resolution."""
    return f"{symbol}_{resolution.value}"


class BarCacheManager:
    """Manages cache metadata for bar data.

    Tracks:
    - Pending ranges: In-flight provider requests (prevents duplicate fetches)
    - Covered ranges: Successfully cached data (enables gap detection)

    Lifecycle:
    1. try_add_pending() - Acquire lock on range (returns None if overlap)
    2. Fetch bars from provider
    3. mark_covered() - Atomically: remove pending + add covered

    Failure recovery: TTL on pending ranges auto-expires stale entries.

    [THREAD-SAFETY]: Datastore provides per-table locking for concurrent access.
    [MEMORY]: Metadata only - actual bar storage is in BarRepository.
    """

    # Convention: Use a class-level variable as a "key"
    _AUTH_KEY = object()

    def __init__(
        self,
        key: object,
        datastore: DatastoreInterface,
        pending_ttl_ms: int,
    ) -> None:
        """Initialize cache manager.

        Args:
            datastore: DatastoreInterface for persistence
            pending_ttl_ms: Time-to-live for pending ranges in milliseconds
        """
        # Prevent direct instantiation
        if key is not self._AUTH_KEY:
            raise TradingApiException(
                code="BAR_CACHE_MANAGER_INIT_FORBIDDEN",
                message="Use BarCacheManager.create() to instantiate",
            )

        if not datastore.has_capability("exclusion"):
            raise TradingApiException(
                code="BAR_CACHE_MANAGER_NO_EXCLUSION_SUPPORT",
                message="Datastore must support exclusion constraints",
            )

        if not datastore.has_capability("transactions"):
            raise TradingApiException(
                code="BAR_CACHE_MANAGER_NO_TRANSACTION_SUPPORT",
                message="Datastore must support transactions for atomic operations",
            )

        if not datastore.has_capability("rangequery"):
            raise TradingApiException(
                code="BAR_CACHE_MANAGER_NO_RANGEQUERY_SUPPORT",
                message="Datastore must support rangequery for gap detection",
            )

        self._pending_ttl_ms = pending_ttl_ms
        self._datastore = datastore
        self._pending_table: TableInterface[PendingRange] | None = None
        self._covered_table: TableInterface[CoveredRange] | None = None
        self._rangequery_table: RangeQueryTableInterface[CoveredRange] | None = None

    @classmethod
    async def create(
        cls,
        datastore: DatastoreInterface,
        settings: Settings,
    ) -> "BarCacheManager":
        """Factory method to create BarCacheManager instance."""
        return cls(
            key=cls._AUTH_KEY,
            datastore=datastore,
            pending_ttl_ms=settings.BAR_CACHE_PENDING_TTL_MS,
        )

    @property
    def pending_table(self) -> TableInterface[PendingRange]:
        """Get or create the pending ranges table."""
        if self._pending_table is None:
            self._pending_table = self._datastore.table(PendingRange)
        return self._pending_table

    @property
    def covered_table(self) -> TableInterface[CoveredRange]:
        """Get or create the covered ranges table."""
        if self._covered_table is None:
            self._covered_table = self._datastore.table(CoveredRange)
        return self._covered_table

    @property
    def rangequery_table(self) -> RangeQueryTableInterface[CoveredRange]:
        """Get or create the rangequery table for gap detection."""
        if self._rangequery_table is None:
            self._rangequery_table = self._datastore.rangequery_table(CoveredRange)
        return self._rangequery_table

    @property
    def _session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Get session factory from datastore for transaction support."""
        assert (
            self._datastore.session_factory is not None
        ), "Datastore does not support transactions"
        return self._datastore.session_factory

    # =========================================================================
    # Pending Range Management
    # =========================================================================

    async def try_add_pending(
        self,
        symbol: str,
        resolution: Resolution,
        time_range: TimeRange,
        ttl_ms: Optional[int] = None,
    ) -> PendingRange | None:
        """Atomically add pending range if no overlap exists.

        Uses PostgreSQL exclusion constraint for atomic "acquire" semantics.
        If another request already owns an overlapping range, returns None
        instead of raising an error.

        This enables concurrent request deduplication:
        - First request wins (gets PendingRange)
        - Concurrent requests lose (get None, can wait/retry)

        Args:
            symbol: Trading symbol
            resolution: Bar resolution
            time_range: Time range being fetched
            ttl_ms: Custom TTL (uses default if not specified)

        Returns:
            PendingRange if acquired successfully
            None if overlapping pending range exists (exclusion violation)

        Raises:
            IntegrityError: For non-exclusion database errors
        """
        try:
            ttl = ttl_ms if ttl_ms is not None else self._pending_ttl_ms
            expires_at = int(time.time() * 1000) + ttl

            pending = PendingRange(
                symbol=symbol,
                resolution=resolution,
                time_range=time_range,
                expires_at=expires_at,
            )

            key = _primary_key(symbol, resolution, time_range)
            await self.pending_table.set(key, pending)

            logger.debug(
                f"Added pending range: {symbol}/{resolution.value} {time_range}"
            )
            return pending
        except IntegrityError as e:
            # PostgreSQL exclusion_violation SQLSTATE
            # psycopg3 uses 'sqlstate', older psycopg2 uses 'pgcode'
            sqlstate = getattr(e.orig, "sqlstate", None) or getattr(
                e.orig, "pgcode", None
            )
            if sqlstate == "23P01":  # exclusion_violation
                logger.debug(
                    f"Exclusion violation for {symbol}/{resolution.value} {time_range} - "
                    "overlapping pending range exists"
                )
                return None
            # Re-raise non-exclusion errors
            raise

    # =========================================================================
    # Covered Range Management
    # =========================================================================

    async def mark_covered(
        self,
        symbol: str,
        resolution: Resolution,
        time_range: TimeRange,
        storage_type: StorageType,
        bar_count: int,
    ) -> CoveredRange:
        """Mark a range as covered (successfully cached).

        Atomically:
        1. Removes the corresponding pending range (if exists)
        2. Creates a covered range entry

        Uses database transaction for atomicity when supported.
        Falls back to sequential operations for non-transactional datastores.

        This completes the fetch lifecycle: try_add_pending → fetch → mark_covered.
        Failure cleanup relies on TTL expiration of pending ranges.

        For simplicity, this version does not merge adjacent ranges.
        Future enhancement: merge overlapping/adjacent ranges.

        Args:
            symbol: Trading symbol
            resolution: Bar resolution
            time_range: Time range that was cached
            storage_type: Where the bars are stored
            bar_count: Number of bars in this range

        Returns:
            Created CoveredRange
        """
        covered = CoveredRange(
            symbol=symbol,
            resolution=resolution,
            time_range=time_range,
            storage_type=storage_type,
            bar_count=bar_count,
        )
        req_range_key = _primary_key(symbol, resolution, time_range)

        # Use transaction if available
        async with self._session_factory() as session:
            # Both operations use same transaction
            await self.pending_table.delete(req_range_key, session=session)
            await self.covered_table.set(req_range_key, covered, session=session)
            await session.commit()

        logger.debug(
            f"Marked covered: {symbol}/{resolution.value} {time_range} "
            f"({bar_count} bars in {storage_type.value})"
        )
        return covered

    # =========================================================================
    # Gap Detection
    # =========================================================================

    async def find_missing_ranges(
        self,
        symbol: str,
        resolution: Resolution,
        from_time: int,
        to_time: int,
    ) -> list[TimeRange]:
        """Find time ranges not covered by cache.

        Uses PostgreSQL multirange operations for accurate gap detection,
        including internal gaps between non-contiguous covered ranges.

        Args:
            symbol: Trading symbol
            resolution: Bar resolution
            from_time: Start of requested range (ms)
            to_time: End of requested range (ms)

        Returns:
            List of TimeRange gaps that need to be fetched
        """
        lookup_key = _lookup_key(symbol, resolution)
        query_range = IntRange(start=from_time, end=to_time)

        gaps = await self.rangequery_table.get_missing_ranges(
            lookup_key=lookup_key,
            query_range=query_range,
        )

        # Convert IntRange → TimeRange
        return [TimeRange(start=gap.start, end=gap.end) for gap in gaps]

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def clear(self, symbol: Optional[str] = None) -> None:
        """Clear cache metadata.

        Args:
            symbol: If provided, only clear for this symbol. Otherwise clear all.
        """
        if symbol is None:
            await self.pending_table.clear()
            await self.covered_table.clear()
            logger.debug("Cleared all cache metadata")
        else:
            # Clear all entries for this symbol (all resolutions)
            all_pending = await self.pending_table.values()
            for p in all_pending:
                if p.symbol == symbol:
                    key = _primary_key(p.symbol, p.resolution, p.time_range)
                    await self.pending_table.delete(key)

            all_covered = await self.covered_table.values()
            for c in all_covered:
                if c.symbol == symbol:
                    key = _primary_key(c.symbol, c.resolution, c.time_range)
                    await self.covered_table.delete(key)

            logger.debug(f"Cleared cache metadata for {symbol}")


__all__ = ["BarCacheManager"]
