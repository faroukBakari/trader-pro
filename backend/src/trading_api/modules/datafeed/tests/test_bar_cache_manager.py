"""Integration tests for BarCacheManager.

Tests the minimal public API:
- create() - Factory method
- try_add_pending() - Atomic pending range acquisition (exclusion constraint)
- mark_covered() - Complete lifecycle: removes pending + adds covered
- find_missing_ranges() - Gap detection for cache-first pattern
- clear() - Cleanup

Requires PostgresDatastore because PendingRange/CoveredRange use exclusion constraints.
"""

import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from trading_api.datastores import PostgresDatastore
from trading_api.models.market import Resolution, TimeRange
from trading_api.modules.datafeed.bar_cache_manager import BarCacheManager
from trading_api.shared.config import Settings
from trading_api.types import StorageType

pytestmark = pytest.mark.integration

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
async def manager(test_settings: Settings) -> BarCacheManager:
    """Create a fresh BarCacheManager with short TTL for testing."""
    datastore = await PostgresDatastore.create(config=test_settings)
    settings = Settings(BAR_CACHE_PENDING_TTL_MS=1000)
    mgr = await BarCacheManager.create(datastore=datastore, settings=settings)
    # Clear any existing data for clean test state
    await mgr.clear()
    return mgr


# ============================================================================
# try_add_pending() Tests
# ============================================================================


async def test_try_add_pending_success(manager: BarCacheManager) -> None:
    """Test try_add_pending returns PendingRange on success."""
    time_range = TimeRange(start=1000, end=2000)

    result = await manager.try_add_pending("AAPL", Resolution.DAY_1, time_range)

    assert result is not None
    assert result.symbol == "AAPL"
    assert result.resolution == Resolution.DAY_1
    assert result.time_range.start == 1000
    assert result.time_range.end == 2000


async def test_try_add_pending_custom_ttl(manager: BarCacheManager) -> None:
    """Test try_add_pending with custom TTL sets correct expiration."""
    time_range = TimeRange(start=1000, end=2000)
    now_ms = int(time.time() * 1000)

    result = await manager.try_add_pending(
        "AAPL", Resolution.DAY_1, time_range, ttl_ms=5000
    )

    assert result is not None
    # Should expire ~5 seconds from now
    assert result.expires_at >= now_ms + 4900
    assert result.expires_at <= now_ms + 5100


async def test_try_add_pending_returns_none_on_exclusion_violation(
    manager: BarCacheManager,
) -> None:
    """Test try_add_pending returns None when exclusion constraint violated.

    Simulates PostgreSQL exclusion_violation (SQLSTATE 23P01) by mocking
    the underlying pending_table.set() method.
    """
    time_range = TimeRange(start=1000, end=2000)

    # Create a mock IntegrityError with SQLSTATE 23P01 (exclusion_violation)
    mock_orig = MagicMock()
    mock_orig.sqlstate = "23P01"
    exc = IntegrityError("", [], mock_orig)

    with patch.object(manager.pending_table, "set", side_effect=exc):
        result = await manager.try_add_pending("AAPL", Resolution.DAY_1, time_range)

    assert result is None


async def test_try_add_pending_returns_none_with_pgcode(
    manager: BarCacheManager,
) -> None:
    """Test try_add_pending handles psycopg2-style 'pgcode' attribute.

    Older psycopg2 uses 'pgcode' instead of 'sqlstate'.
    """
    time_range = TimeRange(start=1000, end=2000)

    # Create a mock IntegrityError with pgcode (psycopg2 style)
    mock_orig = MagicMock()
    mock_orig.sqlstate = None  # Not set in psycopg2
    mock_orig.pgcode = "23P01"
    exc = IntegrityError("", [], mock_orig)

    with patch.object(manager.pending_table, "set", side_effect=exc):
        result = await manager.try_add_pending("AAPL", Resolution.DAY_1, time_range)

    assert result is None


async def test_try_add_pending_reraises_non_exclusion_error(
    manager: BarCacheManager,
) -> None:
    """Test try_add_pending re-raises non-exclusion IntegrityError.

    Errors other than exclusion_violation (23P01) should propagate.
    """
    time_range = TimeRange(start=1000, end=2000)

    # Create IntegrityError with different SQLSTATE (e.g., unique_violation 23505)
    mock_orig = MagicMock()
    mock_orig.sqlstate = "23505"  # unique_violation
    mock_orig.pgcode = None
    exc = IntegrityError("unique constraint violated", [], mock_orig)

    with patch.object(manager.pending_table, "set", side_effect=exc):
        with pytest.raises(IntegrityError) as exc_info:
            await manager.try_add_pending("AAPL", Resolution.DAY_1, time_range)

    assert exc_info.value is exc


async def test_try_add_pending_expires_after_ttl(manager: BarCacheManager) -> None:
    """Test pending range expires and disappears after TTL.

    After TTL expires, the range should be cleaned up automatically,
    allowing a new try_add_pending for the same range to succeed.
    """
    time_range = TimeRange(start=1000, end=2000)

    # Add with very short TTL
    result1 = await manager.try_add_pending(
        "AAPL", Resolution.DAY_1, time_range, ttl_ms=10
    )
    assert result1 is not None

    # Wait for expiration
    await asyncio.sleep(0.05)

    # Should succeed again (expired entry cleaned up on next access)
    result2 = await manager.try_add_pending("AAPL", Resolution.DAY_1, time_range)
    assert result2 is not None


# ============================================================================
# mark_covered() Tests
# ============================================================================


async def test_mark_covered_creates_entry(manager: BarCacheManager) -> None:
    """Test mark_covered creates a CoveredRange and updates gap detection."""
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

    # Verify through find_missing_ranges - should return empty for covered range
    missing = await manager.find_missing_ranges("AAPL", Resolution.DAY_1, 1000, 2000)
    assert missing == []


async def test_mark_covered_removes_pending(manager: BarCacheManager) -> None:
    """Test mark_covered atomically removes the pending entry.

    This tests the full lifecycle: try_add_pending -> mark_covered.
    After mark_covered, the pending slot should be free for another request.
    """
    time_range = TimeRange(start=1000, end=2000)

    # Step 1: Acquire pending
    pending = await manager.try_add_pending("AAPL", Resolution.DAY_1, time_range)
    assert pending is not None

    # Step 2: Mark covered (should remove pending)
    await manager.mark_covered(
        "AAPL", Resolution.DAY_1, time_range, StorageType.MEMORY, bar_count=10
    )

    # Step 3: Verify pending slot is free - we should be able to add pending again
    # (This would fail if pending wasn't removed, due to exclusion constraint)
    pending2 = await manager.try_add_pending("AAPL", Resolution.DAY_1, time_range)
    assert pending2 is not None


async def test_mark_covered_uses_transaction(manager: BarCacheManager) -> None:
    """Test mark_covered uses transaction for delete+insert atomicity.

    Verifies that when PostgresDatastore is used, mark_covered leverages
    the session_factory for atomic operations.
    """
    time_range = TimeRange(start=5000, end=6000)

    # Add pending first
    pending = await manager.try_add_pending("GOOGL", Resolution.HOUR_1, time_range)
    assert pending is not None

    # Mark covered - should atomically remove pending and add covered
    covered = await manager.mark_covered(
        "GOOGL", Resolution.HOUR_1, time_range, StorageType.DATABASE, bar_count=24
    )
    assert covered is not None

    # Verify both operations completed:
    # 1. Pending should be gone (can add new pending)
    pending2 = await manager.try_add_pending("GOOGL", Resolution.HOUR_1, time_range)
    assert pending2 is not None  # Slot is free

    # 2. Covered should exist
    missing = await manager.find_missing_ranges("GOOGL", Resolution.HOUR_1, 5000, 6000)
    assert missing == []  # Range is covered


async def test_mark_covered_idempotent(manager: BarCacheManager) -> None:
    """Test mark_covered can be called multiple times for same range.

    This is important for retry scenarios - if mark_covered is called
    again for the same range, it should succeed (upsert semantics).
    """
    time_range = TimeRange(start=7000, end=8000)

    # First call
    covered1 = await manager.mark_covered(
        "MSFT", Resolution.DAY_1, time_range, StorageType.MEMORY, bar_count=10
    )
    assert covered1 is not None

    # Second call with different bar_count (upsert should update)
    covered2 = await manager.mark_covered(
        "MSFT", Resolution.DAY_1, time_range, StorageType.DATABASE, bar_count=15
    )
    assert covered2 is not None
    assert covered2.bar_count == 15
    assert covered2.storage_type == StorageType.DATABASE


# ============================================================================
# find_missing_ranges() Tests - Gap Detection
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


async def test_find_missing_internal_gap_detected(manager: BarCacheManager) -> None:
    """Test find_missing_ranges detects internal gap — THE BUG WE'RE FIXING.

    Request:  |-------------------|
    Covered:  |-----|       |-----|
    Missing:        |-------|  ← internal gap

    This was previously undetected by the boundary-only algorithm.
    Now uses PostgreSQL multirange subtraction for accurate detection.
    """
    # Two separate coverage regions with gap in middle
    await manager.mark_covered(
        "AAPL",
        Resolution.DAY_1,
        TimeRange(start=1000, end=1200),
        StorageType.MEMORY,
        2,
    )
    await manager.mark_covered(
        "AAPL",
        Resolution.DAY_1,
        TimeRange(start=1500, end=2000),
        StorageType.MEMORY,
        5,
    )

    missing = await manager.find_missing_ranges("AAPL", Resolution.DAY_1, 1000, 2000)

    # Should detect the internal gap
    assert len(missing) == 1
    assert missing[0].start == 1201
    assert missing[0].end == 1499


async def test_find_missing_multiple_internal_gaps(manager: BarCacheManager) -> None:
    """Test find_missing_ranges detects multiple internal gaps.

    Request:  |--------------------------------|
    Covered:  |---|   |---|   |---|      |-----|
    Missing:      |---|   |---|   |------|  ← 3 internal gaps
    """
    # Four separate coverage regions with gaps
    await manager.mark_covered(
        "AAPL",
        Resolution.DAY_1,
        TimeRange(start=1000, end=1100),
        StorageType.MEMORY,
        1,
    )
    await manager.mark_covered(
        "AAPL",
        Resolution.DAY_1,
        TimeRange(start=1200, end=1300),
        StorageType.MEMORY,
        1,
    )
    await manager.mark_covered(
        "AAPL",
        Resolution.DAY_1,
        TimeRange(start=1400, end=1500),
        StorageType.MEMORY,
        1,
    )
    await manager.mark_covered(
        "AAPL",
        Resolution.DAY_1,
        TimeRange(start=1800, end=2000),
        StorageType.MEMORY,
        2,
    )

    missing = await manager.find_missing_ranges("AAPL", Resolution.DAY_1, 1000, 2000)

    # Should detect 3 internal gaps
    assert len(missing) == 3
    # Gap 1: between [1000-1100] and [1200-1300]
    assert missing[0].start == 1101
    assert missing[0].end == 1199
    # Gap 2: between [1200-1300] and [1400-1500]
    assert missing[1].start == 1301
    assert missing[1].end == 1399
    # Gap 3: between [1400-1500] and [1800-2000]
    assert missing[2].start == 1501
    assert missing[2].end == 1799


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
# clear() Tests
# ============================================================================


async def test_clear_resets_coverage(manager: BarCacheManager) -> None:
    """Test clear() removes all coverage, restoring full-miss behavior."""
    # Add coverage
    await manager.mark_covered(
        "AAPL",
        Resolution.DAY_1,
        TimeRange(start=1000, end=2000),
        StorageType.MEMORY,
        5,
    )
    await manager.mark_covered(
        "GOOGL",
        Resolution.HOUR_1,
        TimeRange(start=3000, end=4000),
        StorageType.MEMORY,
        5,
    )

    # Verify coverage exists
    missing = await manager.find_missing_ranges("AAPL", Resolution.DAY_1, 1000, 2000)
    assert missing == []

    # Clear all
    await manager.clear()

    # Should return full range (no coverage)
    missing = await manager.find_missing_ranges("AAPL", Resolution.DAY_1, 1000, 2000)
    assert len(missing) == 1
    assert missing[0].start == 1000
    assert missing[0].end == 2000

    # GOOGL should also be cleared
    missing = await manager.find_missing_ranges("GOOGL", Resolution.HOUR_1, 3000, 4000)
    assert len(missing) == 1


async def test_clear_by_symbol(manager: BarCacheManager) -> None:
    """Test clear(symbol) only clears entries for that symbol."""
    # Add coverage for both symbols
    await manager.mark_covered(
        "AAPL",
        Resolution.DAY_1,
        TimeRange(start=1000, end=2000),
        StorageType.MEMORY,
        5,
    )
    await manager.mark_covered(
        "GOOGL",
        Resolution.DAY_1,
        TimeRange(start=3000, end=4000),
        StorageType.MEMORY,
        5,
    )

    # Clear only AAPL
    await manager.clear(symbol="AAPL")

    # AAPL should be cleared (full miss)
    missing = await manager.find_missing_ranges("AAPL", Resolution.DAY_1, 1000, 2000)
    assert len(missing) == 1

    # GOOGL should remain covered (no gaps)
    missing = await manager.find_missing_ranges("GOOGL", Resolution.DAY_1, 3000, 4000)
    assert missing == []


async def test_clear_releases_pending_slots(manager: BarCacheManager) -> None:
    """Test clear() also removes pending ranges, freeing up slots."""
    time_range = TimeRange(start=1000, end=2000)

    # Acquire pending
    pending = await manager.try_add_pending("AAPL", Resolution.DAY_1, time_range)
    assert pending is not None

    # Clear all
    await manager.clear()

    # Should be able to acquire the same range again
    pending2 = await manager.try_add_pending("AAPL", Resolution.DAY_1, time_range)
    assert pending2 is not None


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
