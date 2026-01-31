"""PostgreSQL range type support verification.

[ARCHITECTURE] Wave 3B: Range support utilities for coordination layer.

This module verifies that psycopg3's range type adapters are properly
registered with asyncpg/SQLAlchemy. psycopg3 auto-registers range types
by default, but explicit verification ensures early failure detection.

Usage:
    # At datastore startup
    await verify_range_support(engine)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from psycopg.types.range import TimestamptzRange
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

__all__ = ["verify_range_support", "ensure_btree_gist_extension"]

logger = logging.getLogger(__name__)


async def verify_range_support(engine: AsyncEngine) -> bool:
    """Verify PostgreSQL range type support is working.

    Tests round-trip of TSTZRANGE value through SQLAlchemy connection.
    This catches adapter registration issues early.

    Args:
        engine: SQLAlchemy async engine

    Returns:
        True if range support is verified

    Raises:
        RuntimeError: If range support verification fails
    """
    test_range = TimestamptzRange(
        datetime(2024, 1, 1, tzinfo=timezone.utc),
        datetime(2024, 1, 2, tzinfo=timezone.utc),
        "[)",
    )

    try:
        async with engine.connect() as conn:
            # Test round-trip: bind Python range → PostgreSQL → Python
            result = await conn.execute(
                text("SELECT :range::tstzrange"),
                {"range": test_range},
            )
            row = result.fetchone()
            if row is None:
                raise RuntimeError("No result from range test query")

            # psycopg3 returns TimestamptzRange
            parsed = row[0]
            if not isinstance(parsed, TimestamptzRange):
                raise RuntimeError(
                    f"Expected TimestamptzRange, got {type(parsed).__name__}. "
                    "psycopg3 range adapter may not be registered."
                )

            # Verify round-trip equality
            if parsed != test_range:
                raise RuntimeError(
                    f"Range round-trip mismatch: sent {test_range}, got {parsed}"
                )

            logger.debug("PostgreSQL TSTZRANGE round-trip verified: %s", parsed)
            return True

    except Exception as e:
        raise RuntimeError(
            f"PostgreSQL range support verification failed: {e}. "
            "Ensure psycopg3 is installed and PostgreSQL supports TSTZRANGE."
        ) from e


async def ensure_btree_gist_extension(engine: AsyncEngine) -> None:
    """Ensure btree_gist extension is enabled.

    Required for EXCLUDE constraints that combine range (&&) and
    equality (=) operators on the same index.

    Should be called before SQLModel.metadata.create_all().

    Args:
        engine: SQLAlchemy async engine
    """
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
        logger.info("btree_gist extension enabled for EXCLUDE constraint support")


async def ensure_exclusion_constraint(
    engine: AsyncEngine,
    table_name: str,
    constraint_name: str,
    symbol_column: str = "symbol",
    resolution_column: str = "resolution",
    range_column: str = "time_range",
) -> None:
    """Create EXCLUDE constraint to prevent overlapping ranges.

    Creates a constraint that prevents two rows from having:
    - Same symbol AND
    - Same resolution AND
    - Overlapping time_range (using && operator)

    This is critical for data integrity — ensures no duplicate
    coverage records exist for the same symbol/resolution.

    Requires btree_gist extension for the equality (=) operator
    on text columns in GiST indexes.

    Args:
        engine: SQLAlchemy async engine
        table_name: Table to add constraint to
        constraint_name: Name for the constraint
        symbol_column: Column name for symbol (default "symbol")
        resolution_column: Column name for resolution (default "resolution")
        range_column: Column name for time range (default "time_range")
    """
    # Use raw SQL since SQLAlchemy doesn't support EXCLUDE declaratively
    # The constraint only applies where time_range IS NOT NULL (hybrid migration)
    sql = f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = '{constraint_name}'
            ) THEN
                ALTER TABLE {table_name}
                ADD CONSTRAINT {constraint_name}
                EXCLUDE USING gist (
                    {symbol_column} WITH =,
                    {resolution_column} WITH =,
                    {range_column} WITH &&
                )
                WHERE ({range_column} IS NOT NULL);
            END IF;
        END $$;
    """

    async with engine.begin() as conn:
        await conn.execute(text(sql))
        logger.info(
            "EXCLUDE constraint '%s' ensured on table '%s'", constraint_name, table_name
        )
