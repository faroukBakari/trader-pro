"""
Bar cache manager for read-through caching of historical bar data.

Manages pending and covered ranges to support gap detection and
prevent duplicate provider requests.
"""

import logging
import time
from typing import Optional

from trading_api.models.exceptions import TradingApiException
from trading_api.models.market import CoveredRange, PendingRange, Resolution, TimeRange
from trading_api.shared.config import Settings
from trading_api.shared.datastore_interface import DatastoreInterface, TableInterface
from trading_api.types import StorageType

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

    Uses DatastoreInterface for persistence with indexed lookups by symbol+resolution.

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

        self._pending_ttl_ms = pending_ttl_ms
        self._datastore = datastore
        self._pending_table: TableInterface[PendingRange] | None = None
        self._covered_table: TableInterface[CoveredRange] | None = None
        self._indexes_created = False

    @classmethod
    async def create(
        cls,
        datastore: DatastoreInterface,
        settings: Settings,
    ) -> "BarCacheManager":
        """Factory method to create BarCacheManager instance."""
        instance = cls(
            key=cls._AUTH_KEY,
            datastore=datastore,
            pending_ttl_ms=settings.BAR_CACHE_PENDING_TTL_MS,
        )
        await instance.__ensure_indexes()
        return instance

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

    async def __ensure_indexes(self) -> None:
        """Create indexes on first use (idempotent)."""
        if self._indexes_created:
            return
        await self.pending_table.create_index("lookup_key")
        await self.covered_table.create_index("lookup_key")
        self._indexes_created = True

    # =========================================================================
    # Pending Range Management
    # =========================================================================

    async def add_pending(
        self,
        symbol: str,
        resolution: Resolution,
        time_range: TimeRange,
        ttl_ms: Optional[int] = None,
    ) -> PendingRange:
        """Mark a range as pending (in-flight provider request).

        Args:
            symbol: Trading symbol
            resolution: Bar resolution
            time_range: Time range being fetched
            ttl_ms: Custom TTL (uses default if not specified)

        Returns:
            Created PendingRange
        """

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

        logger.debug(f"Added pending range: {symbol}/{resolution.value} {time_range}")
        return pending

    async def remove_pending(
        self,
        symbol: str,
        resolution: Resolution,
        time_range: TimeRange,
    ) -> bool:
        """Remove a pending range (request completed or failed).

        Args:
            symbol: Trading symbol
            resolution: Bar resolution
            time_range: Time range to remove

        Returns:
            True if removed, False if not found
        """
        key = _primary_key(symbol, resolution, time_range)
        result = await self.pending_table.delete(key)

        if result:
            logger.debug(
                f"Removed pending range: {symbol}/{resolution.value} {time_range}"
            )
        return result

    async def get_pending_ranges(
        self,
        symbol: str,
        resolution: Resolution,
    ) -> list[PendingRange]:
        """Get all non-expired pending ranges for symbol/resolution.

        Automatically cleans up expired entries.
        """

        lookup_key = _lookup_key(symbol, resolution)
        pending_list = await self.pending_table.get_all(lookup_key, index="lookup_key")

        now_ms = int(time.time() * 1000)
        valid: list[PendingRange] = []
        expired_keys: list[str] = []

        for p in pending_list:
            if p.expires_at > now_ms:
                valid.append(p)
            else:
                expired_keys.append(_primary_key(p.symbol, p.resolution, p.time_range))

        # Clean up expired entries
        for key in expired_keys:
            await self.pending_table.delete(key)

        return valid

    async def is_pending(
        self,
        symbol: str,
        resolution: Resolution,
        time_range: TimeRange,
    ) -> bool:
        """Check if a range overlaps with any pending request."""
        pending_ranges = await self.get_pending_ranges(symbol, resolution)
        return any(p.time_range.overlaps(time_range) for p in pending_ranges)

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

        key = _primary_key(symbol, resolution, time_range)
        await self.covered_table.set(key, covered)

        logger.debug(
            f"Marked covered: {symbol}/{resolution.value} {time_range} "
            f"({bar_count} bars in {storage_type.value})"
        )
        return covered

    async def get_covered_ranges(
        self,
        symbol: str,
        resolution: Resolution,
    ) -> list[CoveredRange]:
        """Get all covered ranges for symbol/resolution."""

        lookup_key = _lookup_key(symbol, resolution)
        return await self.covered_table.get_all(lookup_key, index="lookup_key")

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

        Simple boundary-based gap detection:
        - If no coverage: return full requested range
        - Otherwise: check for gaps at start and end

        Args:
            symbol: Trading symbol
            resolution: Bar resolution
            from_time: Start of requested range (ms)
            to_time: End of requested range (ms)

        Returns:
            List of TimeRange gaps that need to be fetched
        """
        covered_ranges = await self.get_covered_ranges(symbol, resolution)

        if not covered_ranges:
            # Full miss - need entire range
            return [TimeRange(start=from_time, end=to_time)]

        # Find the overall coverage bounds
        min_covered = min(c.time_range.start for c in covered_ranges)
        max_covered = max(c.time_range.end for c in covered_ranges)

        missing: list[TimeRange] = []

        # Gap at the beginning?
        if from_time < min_covered:
            missing.append(
                TimeRange(start=from_time, end=min(to_time, min_covered - 1))
            )

        # Gap at the end?
        if to_time > max_covered:
            missing.append(
                TimeRange(start=max(from_time, max_covered + 1), end=to_time)
            )

        return missing

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def cleanup_expired_pending(self) -> int:
        """Remove all expired pending ranges.

        Returns:
            Number of expired entries removed
        """
        now_ms = int(time.time() * 1000)
        removed = 0

        all_pending = await self.pending_table.values()

        for p in all_pending:
            if p.expires_at <= now_ms:
                key = _primary_key(p.symbol, p.resolution, p.time_range)
                if await self.pending_table.delete(key):
                    removed += 1

        if removed:
            logger.debug(f"Cleaned up {removed} expired pending ranges")

        return removed

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
