"""Coordination repository for gap detection and coverage tracking.

[ARCHITECTURE] Wave 3B: Coordination Layer Repository
Provides gap detection via native PostgreSQL range operations (range_agg, multirange).

Usage:
    repo = CoordinationRepository(session_factory)
    gaps = await repo.find_gaps("AAPL", "1D", requested_range)
    is_done = await repo.is_covered("AAPL", "1D", requested_range)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from psycopg.types.range import TimestamptzRange
from sqlalchemy import asc, text
from sqlmodel import select

from trading_api.models.coordination import CoveredRange

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

__all__ = ["CoordinationRepository"]


class CoordinationRepository:
    """Repository for coordination layer operations.

    Provides:
    - Gap detection: Find uncovered time ranges that need fetching
    - Coverage checks: Verify if a requested range is fully covered
    - Coverage recording: Track ranges where data is available

    [PERFORMANCE] Uses native PostgreSQL range operations:
    - range_agg(): Aggregates coverage into a multirange
    - tstzmultirange - tstzrange: Computes gaps via set subtraction
    - GiST indexes for efficient overlap queries
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        """Initialize with SQLAlchemy async session factory.

        Args:
            session_factory: Async session factory from PostgresDatastore
        """
        self._session_factory = session_factory

    async def find_gaps(
        self,
        symbol: str,
        resolution: str,
        requested: TimestamptzRange,
    ) -> list[TimestamptzRange]:
        """Find uncovered time ranges within the requested range.

        Uses PostgreSQL's native range operations:
        1. Aggregate all covered ranges for symbol/resolution into multirange
        2. Subtract coverage from requested range to get gaps
        3. Return list of gap ranges that need fetching

        Args:
            symbol: Trading symbol (e.g., "AAPL")
            resolution: Resolution string (e.g., "1D", "60")
            requested: Time range being requested

        Returns:
            List of TimestamptzRange objects representing uncovered gaps.
            Empty list if fully covered.

        Example:
            # Request [Jan 1, Jan 30)
            # Coverage: [Jan 5-10), [Jan 15-20)
            # Returns: [Jan 1-5), [Jan 10-15), [Jan 20-30)
        """
        if requested.isempty:
            return []

        # Build SQL for gap detection using multirange subtraction
        # PostgreSQL 14+ required for tstzmultirange and range_agg
        sql = text(
            """
            WITH coverage AS (
                SELECT range_agg(time_range) as covered
                FROM covered_ranges
                WHERE symbol = :symbol
                  AND resolution = :resolution
                  AND time_range IS NOT NULL
                  AND time_range && :requested
            )
            SELECT unnest(
                tstzmultirange(:requested) - COALESCE(covered, tstzmultirange())
            ) as gap
            FROM coverage
        """
        )

        async with self._session_factory() as session:
            result = await session.execute(
                sql,
                {
                    "symbol": symbol,
                    "resolution": resolution,
                    "requested": requested,
                },
            )
            rows = result.fetchall()

            # Convert to list of TimestamptzRange
            gaps = [row[0] for row in rows if row[0] is not None]

            logger.debug(
                "find_gaps(%s, %s, %s): found %d gaps",
                symbol,
                resolution,
                requested,
                len(gaps),
            )
            return gaps

    async def is_covered(
        self,
        symbol: str,
        resolution: str,
        requested: TimestamptzRange,
    ) -> bool:
        """Check if the requested range is fully covered by existing data.

        Optimized query that returns early without computing all gaps.
        Uses containment operator (@>) with aggregated multirange.

        Args:
            symbol: Trading symbol
            resolution: Resolution string
            requested: Time range to check

        Returns:
            True if fully covered, False if any gaps exist
        """
        if requested.isempty:
            return True

        # Check if aggregated coverage contains the entire requested range
        sql = text(
            """
            SELECT COALESCE(
                range_agg(time_range) @> :requested,
                false
            ) as is_covered
            FROM covered_ranges
            WHERE symbol = :symbol
              AND resolution = :resolution
              AND time_range IS NOT NULL
              AND time_range && :requested
        """
        )

        async with self._session_factory() as session:
            result = await session.execute(
                sql,
                {
                    "symbol": symbol,
                    "resolution": resolution,
                    "requested": requested,
                },
            )
            row = result.fetchone()
            is_covered = row[0] if row else False

            logger.debug(
                "is_covered(%s, %s, %s): %s", symbol, resolution, requested, is_covered
            )
            return bool(is_covered)

    async def record_coverage(
        self,
        symbol: str,
        resolution: str,
        time_range: TimestamptzRange,
        storage: str = "buffer",
        file_path: str | None = None,
        row_count: int | None = None,
    ) -> CoveredRange:
        """Record a new covered range after successful data fetch.

        Creates a CoveredRange record with both legacy columns (range_start/end)
        and the new time_range column for hybrid compatibility.

        Args:
            symbol: Trading symbol
            resolution: Resolution string
            time_range: The covered time range
            storage: Storage type ("buffer" or "parquet")
            file_path: Parquet file path if storage="parquet"
            row_count: Number of bars in the range

        Returns:
            Created CoveredRange record
        """
        async with self._session_factory() as session:
            # TimestamptzRange.lower/upper are typed as datetime | None,
            # but non-empty ranges always have both bounds set
            assert time_range.lower is not None and time_range.upper is not None

            covered = CoveredRange(
                symbol=symbol,
                resolution=resolution,
                # Legacy columns (backwards compatible)
                range_start=time_range.lower,
                range_end=time_range.upper,
                # New column (for gap detection)
                time_range=time_range,
                storage=storage,
                file_path=file_path,
                row_count=row_count,
            )
            session.add(covered)
            await session.commit()
            await session.refresh(covered)

            logger.info(
                "Recorded coverage: %s/%s %s (id=%d)",
                symbol,
                resolution,
                time_range,
                covered.id,
            )
            return covered

    async def get_coverage(
        self,
        symbol: str,
        resolution: str,
        requested: TimestamptzRange | None = None,
    ) -> list[CoveredRange]:
        """Get coverage records for a symbol/resolution.

        Args:
            symbol: Trading symbol
            resolution: Resolution string
            requested: Optional range filter (returns overlapping records)

        Returns:
            List of CoveredRange records, ordered by time_range
        """
        async with self._session_factory() as session:
            stmt = select(CoveredRange).where(
                CoveredRange.symbol == symbol,
                CoveredRange.resolution == resolution,
            )

            if requested is not None:
                # Filter to overlapping ranges only
                # Note: Using raw SQL for range operator since SQLModel
                # doesn't support native range operators in select()
                stmt = stmt.where(text("time_range && :requested")).params(
                    requested=requested
                )

            stmt = stmt.order_by(asc("range_start"))

            result = await session.execute(stmt)
            return list(result.scalars().all())
