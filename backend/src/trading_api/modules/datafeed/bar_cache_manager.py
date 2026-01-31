"""
Bar cache manager for read-through caching of historical bar data.

Manages pending and covered ranges to support gap detection and
prevent duplicate provider requests.
"""

import logging
import time
from typing import Optional

from trading_api.models.market import CoveredRange, PendingRange, Resolution, TimeRange
from trading_api.types import StorageType

logger = logging.getLogger(__name__)

# Default pending range expiration: 30 seconds
DEFAULT_PENDING_TTL_MS = 30_000


class BarCacheManager:
    """Manages cache metadata for bar data.

    Tracks:
    - Pending ranges: In-flight provider requests (prevents duplicate fetches)
    - Covered ranges: Successfully cached data (enables gap detection)

    [THREAD-SAFETY]: Not thread-safe. Use with asyncio lock if concurrent access needed.
    [MEMORY]: Metadata only - actual bar storage is in BarRepository.
    """

    def __init__(self, pending_ttl_ms: int = DEFAULT_PENDING_TTL_MS) -> None:
        """Initialize cache manager.

        Args:
            pending_ttl_ms: Time-to-live for pending ranges in milliseconds
        """
        self._pending_ttl_ms = pending_ttl_ms
        # Key: (symbol, resolution.value) -> list of ranges
        self._pending: dict[tuple[str, str], list[PendingRange]] = {}
        self._covered: dict[tuple[str, str], list[CoveredRange]] = {}

    def _key(self, symbol: str, resolution: Resolution) -> tuple[str, str]:
        """Create lookup key from symbol and resolution."""
        return (symbol, resolution.value)

    # =========================================================================
    # Pending Range Management
    # =========================================================================

    def add_pending(
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

        key = self._key(symbol, resolution)
        if key not in self._pending:
            self._pending[key] = []
        self._pending[key].append(pending)

        logger.debug(f"Added pending range: {symbol}/{resolution.value} {time_range}")
        return pending

    def remove_pending(
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
        key = self._key(symbol, resolution)
        pending_list = self._pending.get(key, [])

        for i, pending in enumerate(pending_list):
            if (
                pending.time_range.start == time_range.start
                and pending.time_range.end == time_range.end
            ):
                pending_list.pop(i)
                logger.debug(
                    f"Removed pending range: {symbol}/{resolution.value} {time_range}"
                )
                return True

        return False

    def get_pending_ranges(
        self,
        symbol: str,
        resolution: Resolution,
    ) -> list[PendingRange]:
        """Get all non-expired pending ranges for symbol/resolution.

        Automatically cleans up expired entries.
        """
        key = self._key(symbol, resolution)
        now_ms = int(time.time() * 1000)

        # Filter out expired entries
        pending_list = self._pending.get(key, [])
        valid = [p for p in pending_list if p.expires_at > now_ms]

        # Update list if any expired
        if len(valid) != len(pending_list):
            self._pending[key] = valid

        return valid

    def is_pending(
        self,
        symbol: str,
        resolution: Resolution,
        time_range: TimeRange,
    ) -> bool:
        """Check if a range overlaps with any pending request."""
        pending_ranges = self.get_pending_ranges(symbol, resolution)
        return any(p.time_range.overlaps(time_range) for p in pending_ranges)

    # =========================================================================
    # Covered Range Management
    # =========================================================================

    def mark_covered(
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

        key = self._key(symbol, resolution)
        if key not in self._covered:
            self._covered[key] = []
        self._covered[key].append(covered)

        logger.debug(
            f"Marked covered: {symbol}/{resolution.value} {time_range} "
            f"({bar_count} bars in {storage_type.value})"
        )
        return covered

    def get_covered_ranges(
        self,
        symbol: str,
        resolution: Resolution,
    ) -> list[CoveredRange]:
        """Get all covered ranges for symbol/resolution."""
        key = self._key(symbol, resolution)
        return self._covered.get(key, [])

    # =========================================================================
    # Gap Detection
    # =========================================================================

    def find_missing_ranges(
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
        covered_ranges = self.get_covered_ranges(symbol, resolution)

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

    def cleanup_expired_pending(self) -> int:
        """Remove all expired pending ranges.

        Returns:
            Number of expired entries removed
        """
        now_ms = int(time.time() * 1000)
        removed = 0

        for key in list(self._pending.keys()):
            original_len = len(self._pending[key])
            self._pending[key] = [
                p for p in self._pending[key] if p.expires_at > now_ms
            ]
            removed += original_len - len(self._pending[key])

            # Remove empty keys
            if not self._pending[key]:
                del self._pending[key]

        if removed:
            logger.debug(f"Cleaned up {removed} expired pending ranges")

        return removed

    def clear(self, symbol: Optional[str] = None) -> None:
        """Clear cache metadata.

        Args:
            symbol: If provided, only clear for this symbol. Otherwise clear all.
        """
        if symbol is None:
            self._pending.clear()
            self._covered.clear()
            logger.debug("Cleared all cache metadata")
        else:
            # Clear all resolutions for this symbol
            keys_to_remove = [k for k in self._pending if k[0] == symbol]
            for key in keys_to_remove:
                del self._pending[key]

            keys_to_remove = [k for k in self._covered if k[0] == symbol]
            for key in keys_to_remove:
                del self._covered[key]

            logger.debug(f"Cleared cache metadata for {symbol}")


__all__ = ["BarCacheManager"]
