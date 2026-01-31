"""Unit tests for BarCacheManager.

Tests cover:
- Pending range management (add, remove, expiration, overlap detection)
- Covered range management (mark, retrieve)
- Gap detection (find_missing_ranges)
- Cleanup operations (expired pending, clear)
"""

import asyncio
import time

import pytest

from trading_api.datastores import InMemoryDatastore
from trading_api.models.market import Resolution, TimeRange
from trading_api.modules.datafeed.bar_cache_manager import BarCacheManager
from trading_api.shared.config import Settings
from trading_api.types import StorageType

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
async def manager() -> BarCacheManager:
    """Create a fresh BarCacheManager with short TTL for testing."""
    datastore = InMemoryDatastore()
    settings = Settings(BAR_CACHE_PENDING_TTL_MS=1000)
    return await BarCacheManager.create(datastore=datastore, settings=settings)


@pytest.fixture
def time_range() -> TimeRange:
    """Standard time range for tests (1000ms to 2000ms)."""
    return TimeRange(start=1000, end=2000)


# ============================================================================
# Pending Range Tests
# ============================================================================


async def test_add_pending_creates_entry(manager: BarCacheManager) -> None:
    """Test add_pending creates a PendingRange entry."""
    time_range = TimeRange(start=1000, end=2000)

    pending = await manager.add_pending("AAPL", Resolution.DAY_1, time_range)

    assert pending.symbol == "AAPL"
    assert pending.resolution == Resolution.DAY_1
    assert pending.time_range.start == 1000
    assert pending.time_range.end == 2000
    assert pending.expires_at > int(time.time() * 1000)


async def test_add_pending_custom_ttl(manager: BarCacheManager) -> None:
    """Test add_pending respects custom TTL parameter."""
    time_range = TimeRange(start=1000, end=2000)
    now_ms = int(time.time() * 1000)

    pending = await manager.add_pending(
        "AAPL", Resolution.DAY_1, time_range, ttl_ms=5000
    )

    # Should expire ~5 seconds from now (with some tolerance)
    assert pending.expires_at >= now_ms + 4900
    assert pending.expires_at <= now_ms + 5100


async def test_remove_pending_returns_true(manager: BarCacheManager) -> None:
    """Test remove_pending returns True on successful removal."""
    time_range = TimeRange(start=1000, end=2000)
    await manager.add_pending("AAPL", Resolution.DAY_1, time_range)

    result = await manager.remove_pending("AAPL", Resolution.DAY_1, time_range)

    assert result is True
    assert await manager.get_pending_ranges("AAPL", Resolution.DAY_1) == []


async def test_remove_pending_returns_false_not_found(manager: BarCacheManager) -> None:
    """Test remove_pending returns False when range not found."""
    time_range = TimeRange(start=1000, end=2000)

    result = await manager.remove_pending("AAPL", Resolution.DAY_1, time_range)

    assert result is False


async def test_get_pending_ranges_filters_expired(manager: BarCacheManager) -> None:
    """Test get_pending_ranges automatically filters out expired entries."""
    time_range = TimeRange(start=1000, end=2000)

    # Add with very short TTL
    await manager.add_pending("AAPL", Resolution.DAY_1, time_range, ttl_ms=1)

    # Wait for expiration
    await asyncio.sleep(0.01)

    # Should be empty after expiration
    result = await manager.get_pending_ranges("AAPL", Resolution.DAY_1)
    assert result == []


async def test_is_pending_detects_overlap(manager: BarCacheManager) -> None:
    """Test is_pending returns True when ranges overlap."""
    # Add pending range 1000-2000
    await manager.add_pending("AAPL", Resolution.DAY_1, TimeRange(start=1000, end=2000))

    # Check overlapping range 1500-2500
    result = await manager.is_pending(
        "AAPL", Resolution.DAY_1, TimeRange(start=1500, end=2500)
    )

    assert result is True


async def test_is_pending_no_overlap(manager: BarCacheManager) -> None:
    """Test is_pending returns False when ranges don't overlap."""
    # Add pending range 1000-2000
    await manager.add_pending("AAPL", Resolution.DAY_1, TimeRange(start=1000, end=2000))

    # Check disjoint range 3000-4000
    result = await manager.is_pending(
        "AAPL", Resolution.DAY_1, TimeRange(start=3000, end=4000)
    )

    assert result is False


async def test_is_pending_different_symbol(manager: BarCacheManager) -> None:
    """Test is_pending returns False for different symbol."""
    await manager.add_pending("AAPL", Resolution.DAY_1, TimeRange(start=1000, end=2000))

    result = await manager.is_pending(
        "GOOGL", Resolution.DAY_1, TimeRange(start=1000, end=2000)
    )

    assert result is False


async def test_is_pending_different_resolution(manager: BarCacheManager) -> None:
    """Test is_pending returns False for different resolution."""
    await manager.add_pending("AAPL", Resolution.DAY_1, TimeRange(start=1000, end=2000))

    result = await manager.is_pending(
        "AAPL", Resolution.HOUR_1, TimeRange(start=1000, end=2000)
    )

    assert result is False


# ============================================================================
# Covered Range Tests
# ============================================================================


async def test_mark_covered_creates_entry(manager: BarCacheManager) -> None:
    """Test mark_covered creates a CoveredRange entry."""
    time_range = TimeRange(start=1000, end=2000)

    covered = await manager.mark_covered(
        "AAPL", Resolution.DAY_1, time_range, StorageType.MEMORY, bar_count=10
    )

    assert covered.symbol == "AAPL"
    assert covered.resolution == Resolution.DAY_1
    assert covered.time_range.start == 1000
    assert covered.time_range.end == 2000
    assert covered.storage_type == StorageType.MEMORY
    assert covered.bar_count == 10


async def test_get_covered_ranges_empty(manager: BarCacheManager) -> None:
    """Test get_covered_ranges returns empty list for unknown symbol."""
    result = await manager.get_covered_ranges("UNKNOWN", Resolution.DAY_1)

    assert result == []


async def test_get_covered_ranges_returns_all(manager: BarCacheManager) -> None:
    """Test get_covered_ranges returns all ranges for symbol/resolution."""
    await manager.mark_covered(
        "AAPL",
        Resolution.DAY_1,
        TimeRange(start=1000, end=2000),
        StorageType.MEMORY,
        5,
    )
    await manager.mark_covered(
        "AAPL",
        Resolution.DAY_1,
        TimeRange(start=3000, end=4000),
        StorageType.MEMORY,
        5,
    )

    result = await manager.get_covered_ranges("AAPL", Resolution.DAY_1)

    assert len(result) == 2


# ============================================================================
# Gap Detection Tests
# ============================================================================


async def test_find_missing_full_miss(manager: BarCacheManager) -> None:
    """Test find_missing_ranges returns full range when no coverage exists.

    Request:  |------------|
    Covered:  (none)
    Missing:  |------------|
    """
    missing = await manager.find_missing_ranges("AAPL", Resolution.DAY_1, 1000, 2000)

    assert len(missing) == 1
    assert missing[0].start == 1000
    assert missing[0].end == 2000


async def test_find_missing_gap_at_start(manager: BarCacheManager) -> None:
    """Test find_missing_ranges detects gap at start.

    Request:  |------------|
    Covered:       |-------|
    Missing:  |----|
    """
    # Coverage from 1500-2000
    await manager.mark_covered(
        "AAPL",
        Resolution.DAY_1,
        TimeRange(start=1500, end=2000),
        StorageType.MEMORY,
        5,
    )

    missing = await manager.find_missing_ranges("AAPL", Resolution.DAY_1, 1000, 2000)

    assert len(missing) == 1
    assert missing[0].start == 1000
    assert missing[0].end == 1499  # min(2000, 1500-1)


async def test_find_missing_gap_at_end(manager: BarCacheManager) -> None:
    """Test find_missing_ranges detects gap at end.

    Request:  |------------|
    Covered:  |-------|
    Missing:         |----|
    """
    # Coverage from 1000-1500
    await manager.mark_covered(
        "AAPL",
        Resolution.DAY_1,
        TimeRange(start=1000, end=1500),
        StorageType.MEMORY,
        5,
    )

    missing = await manager.find_missing_ranges("AAPL", Resolution.DAY_1, 1000, 2000)

    assert len(missing) == 1
    assert missing[0].start == 1501  # max(1000, 1500+1)
    assert missing[0].end == 2000


async def test_find_missing_full_hit(manager: BarCacheManager) -> None:
    """Test find_missing_ranges returns empty when fully covered.

    Request:     |-----|
    Covered:  |----------|
    Missing:  (none)
    """
    # Coverage from 500-2500 (larger than request)
    await manager.mark_covered(
        "AAPL",
        Resolution.DAY_1,
        TimeRange(start=500, end=2500),
        StorageType.MEMORY,
        20,
    )

    missing = await manager.find_missing_ranges("AAPL", Resolution.DAY_1, 1000, 2000)

    assert len(missing) == 0


async def test_find_missing_gaps_both_ends(manager: BarCacheManager) -> None:
    """Test find_missing_ranges detects gaps at both ends.

    Request:  |--------------|
    Covered:     |-----|
    Missing:  |--|     |-----|
    """
    # Coverage from 1200-1800 (middle only)
    await manager.mark_covered(
        "AAPL",
        Resolution.DAY_1,
        TimeRange(start=1200, end=1800),
        StorageType.MEMORY,
        6,
    )

    missing = await manager.find_missing_ranges("AAPL", Resolution.DAY_1, 1000, 2000)

    assert len(missing) == 2
    # Gap at start
    assert missing[0].start == 1000
    assert missing[0].end == 1199
    # Gap at end
    assert missing[1].start == 1801
    assert missing[1].end == 2000


async def test_find_missing_exact_coverage(manager: BarCacheManager) -> None:
    """Test find_missing_ranges returns empty when coverage exactly matches request."""
    await manager.mark_covered(
        "AAPL",
        Resolution.DAY_1,
        TimeRange(start=1000, end=2000),
        StorageType.MEMORY,
        10,
    )

    missing = await manager.find_missing_ranges("AAPL", Resolution.DAY_1, 1000, 2000)

    assert len(missing) == 0


# ============================================================================
# Cleanup Tests
# ============================================================================


async def test_cleanup_expired_pending_removes_old(manager: BarCacheManager) -> None:
    """Test cleanup_expired_pending removes expired entries."""
    # Add with very short TTL
    await manager.add_pending(
        "AAPL", Resolution.DAY_1, TimeRange(start=1000, end=2000), ttl_ms=1
    )

    # Wait for expiration
    await asyncio.sleep(0.01)

    removed = await manager.cleanup_expired_pending()

    assert removed == 1
    assert await manager.get_pending_ranges("AAPL", Resolution.DAY_1) == []


async def test_cleanup_expired_pending_keeps_valid(manager: BarCacheManager) -> None:
    """Test cleanup_expired_pending keeps non-expired entries."""
    # Add with long TTL
    await manager.add_pending(
        "AAPL", Resolution.DAY_1, TimeRange(start=1000, end=2000), ttl_ms=60000
    )

    removed = await manager.cleanup_expired_pending()

    assert removed == 0
    assert len(await manager.get_pending_ranges("AAPL", Resolution.DAY_1)) == 1


async def test_clear_all(manager: BarCacheManager) -> None:
    """Test clear() removes all pending and covered entries."""
    await manager.add_pending("AAPL", Resolution.DAY_1, TimeRange(start=1000, end=2000))
    await manager.mark_covered(
        "AAPL",
        Resolution.DAY_1,
        TimeRange(start=1000, end=2000),
        StorageType.MEMORY,
        5,
    )
    await manager.add_pending(
        "GOOGL", Resolution.HOUR_1, TimeRange(start=3000, end=4000)
    )

    await manager.clear()

    assert await manager.get_pending_ranges("AAPL", Resolution.DAY_1) == []
    assert await manager.get_covered_ranges("AAPL", Resolution.DAY_1) == []
    assert await manager.get_pending_ranges("GOOGL", Resolution.HOUR_1) == []


async def test_clear_by_symbol(manager: BarCacheManager) -> None:
    """Test clear(symbol) removes only entries for that symbol."""
    await manager.add_pending("AAPL", Resolution.DAY_1, TimeRange(start=1000, end=2000))
    await manager.mark_covered(
        "AAPL",
        Resolution.DAY_1,
        TimeRange(start=1000, end=2000),
        StorageType.MEMORY,
        5,
    )
    await manager.add_pending(
        "GOOGL", Resolution.DAY_1, TimeRange(start=3000, end=4000)
    )

    await manager.clear(symbol="AAPL")

    # AAPL should be cleared
    assert await manager.get_pending_ranges("AAPL", Resolution.DAY_1) == []
    assert await manager.get_covered_ranges("AAPL", Resolution.DAY_1) == []
    # GOOGL should remain
    assert len(await manager.get_pending_ranges("GOOGL", Resolution.DAY_1)) == 1


# ============================================================================
# Range[T] Method Tests (via TimeRange)
# ============================================================================


def test_time_range_contains() -> None:
    """Test TimeRange.contains() method."""
    tr = TimeRange(start=1000, end=2000)

    assert tr.contains(1000) is True  # start boundary
    assert tr.contains(1500) is True  # middle
    assert tr.contains(2000) is True  # end boundary
    assert tr.contains(999) is False  # before
    assert tr.contains(2001) is False  # after


def test_time_range_overlaps() -> None:
    """Test TimeRange.overlaps() method."""
    tr = TimeRange(start=1000, end=2000)

    # Overlapping cases
    assert tr.overlaps(TimeRange(start=1500, end=2500)) is True  # partial right
    assert tr.overlaps(TimeRange(start=500, end=1500)) is True  # partial left
    assert tr.overlaps(TimeRange(start=1200, end=1800)) is True  # nested inside
    assert tr.overlaps(TimeRange(start=500, end=2500)) is True  # contains tr
    assert tr.overlaps(TimeRange(start=2000, end=3000)) is True  # adjacent end

    # Non-overlapping cases
    assert tr.overlaps(TimeRange(start=2001, end=3000)) is False  # after
    assert tr.overlaps(TimeRange(start=0, end=999)) is False  # before
