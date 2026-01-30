"""PostgreSQL bar storage with table-per-combo pattern.

[ARCHITECTURE] Wave 3A: Dynamic table creation per symbol/resolution combination.
Each table has direct typed columns (no JSONB) for optimal query performance.

Table naming: bars_{symbol}_{resolution}
Schema: 7 columns matching Bar model (time, open, high, low, close, volume, count)

Security: Uses validate_identifier() from sql_safe.py for SQL injection prevention.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

from psycopg import sql
from psycopg.rows import dict_row

from trading_api.models.market import Bar, Resolution

from .sql_safe import validate_identifier

if TYPE_CHECKING:
    from psycopg_pool import AsyncConnectionPool

__all__ = ["BAR_TABLE_PREFIX", "bar_table_name", "PostgresBarRepository"]

# Prefix for all bar tables - enables discovery via list_tables(prefix="bars_")
BAR_TABLE_PREFIX = "bars_"


def bar_table_name(symbol: str, resolution: str | Resolution) -> str:
    """Generate table name: bars_{symbol}_{resolution}.

    Normalizes inputs and validates for SQL safety:
    - Lowercase conversion
    - Slash replacement (EUR/USD → eur_usd)
    - Resolution prefix for numeric-leading values (1D → r1d)
    - Identifier validation (alphanumeric + underscore only)

    Args:
        symbol: Trading symbol (e.g., "AAPL", "EUR/USD")
        resolution: Resolution string or enum (e.g., "1D", Resolution.DAY_1)

    Returns:
        Safe table name like "bars_aapl_r1d" or "bars_eur_usd_r60"

    Raises:
        ValueError: If symbol or resolution contains invalid characters
    """
    # Handle Resolution enum
    resolution_str = (
        resolution.value if isinstance(resolution, Resolution) else resolution
    )

    # Normalize: lowercase and replace slashes
    symbol_safe = symbol.lower().replace("/", "_")
    resolution_safe = resolution_str.lower()

    # PostgreSQL identifiers must start with letter or underscore
    # Prefix numeric resolutions with 'r' (e.g., "1d" → "r1d", "60" → "r60")
    if resolution_safe and resolution_safe[0].isdigit():
        resolution_safe = f"r{resolution_safe}"

    # Validate both parts for SQL safety
    validate_identifier(symbol_safe, "symbol")
    validate_identifier(resolution_safe, "resolution")

    return f"{BAR_TABLE_PREFIX}{symbol_safe}_{resolution_safe}"


class PostgresBarRepository:
    """PostgreSQL bar storage with one table per symbol/resolution combination.

    [ARCHITECTURE] Wave 3A: Table-per-combo pattern
    - Dynamic table creation on first write
    - Upsert semantics (ON CONFLICT UPDATE)
    - Range queries with optional time bounds
    - Cleanup via drop_if_empty() for table count management

    Schema per table:
        CREATE TABLE bars_{symbol}_{resolution} (
            time BIGINT PRIMARY KEY,           -- Unix milliseconds
            open DECIMAL(18,8) NOT NULL,
            high DECIMAL(18,8) NOT NULL,
            low DECIMAL(18,8) NOT NULL,
            close DECIMAL(18,8) NOT NULL,
            volume BIGINT NOT NULL,
            count INTEGER                      -- Nullable for providers without trade count
        )
    """

    def __init__(self, pool: "AsyncConnectionPool[Any]") -> None:
        """Initialize repository with connection pool.

        Args:
            pool: psycopg3 AsyncConnectionPool from PostgresDatastore
        """
        self._pool = pool
        self._initialized_tables: set[str] = set()

    async def _ensure_table(self, table_name: str) -> None:
        """Create table if not exists (idempotent).

        Uses CREATE TABLE IF NOT EXISTS for concurrent-safe initialization.
        Tracks initialized tables in memory to avoid repeated DDL.

        Args:
            table_name: Pre-validated table name from bar_table_name()
        """
        if table_name in self._initialized_tables:
            return

        # Defense-in-depth: validate even though bar_table_name() already validates
        validate_identifier(table_name, "table name")

        async with self._pool.connection() as conn:
            await conn.execute(
                sql.SQL(
                    """
                    CREATE TABLE IF NOT EXISTS {} (
                        time BIGINT PRIMARY KEY,
                        open DECIMAL(18,8) NOT NULL,
                        high DECIMAL(18,8) NOT NULL,
                        low DECIMAL(18,8) NOT NULL,
                        close DECIMAL(18,8) NOT NULL,
                        volume BIGINT NOT NULL,
                        count INTEGER
                    )
                    """
                ).format(sql.Identifier(table_name))
            )

        self._initialized_tables.add(table_name)

    async def store_bars(
        self,
        symbol: str,
        resolution: str | Resolution,
        bars: list[Bar],
    ) -> int:
        """Store bars with upsert semantics.

        Uses INSERT ... ON CONFLICT DO UPDATE for idempotent writes.
        Existing bars with matching timestamps are updated with new values.

        Args:
            symbol: Trading symbol
            resolution: Time resolution
            bars: List of Bar models to store

        Returns:
            Number of bars stored (always equals len(bars) due to upsert)
        """
        if not bars:
            return 0

        table = bar_table_name(symbol, resolution)
        await self._ensure_table(table)

        async with self._pool.connection() as conn:
            for bar in bars:
                await conn.execute(
                    sql.SQL(
                        """
                        INSERT INTO {} (time, open, high, low, close, volume, count)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (time) DO UPDATE SET
                            open = EXCLUDED.open,
                            high = EXCLUDED.high,
                            low = EXCLUDED.low,
                            close = EXCLUDED.close,
                            volume = EXCLUDED.volume,
                            count = EXCLUDED.count
                        """
                    ).format(sql.Identifier(table)),
                    (
                        bar.time,
                        Decimal(str(bar.open)),
                        Decimal(str(bar.high)),
                        Decimal(str(bar.low)),
                        Decimal(str(bar.close)),
                        bar.volume,
                        bar.count,
                    ),
                )

        return len(bars)

    async def get_bars(
        self,
        symbol: str,
        resolution: str | Resolution,
        from_time: int | None = None,
        to_time: int | None = None,
    ) -> list[Bar]:
        """Retrieve bars within optional time range.

        Args:
            symbol: Trading symbol
            resolution: Time resolution
            from_time: Optional start timestamp (inclusive, Unix ms)
            to_time: Optional end timestamp (inclusive, Unix ms)

        Returns:
            List of Bar models sorted by time ascending
        """
        table = bar_table_name(symbol, resolution)
        await self._ensure_table(table)

        # Build WHERE clause dynamically
        conditions: list[sql.Composable] = []
        params: list[int] = []

        if from_time is not None:
            conditions.append(sql.SQL("time >= %s"))
            params.append(from_time)
        if to_time is not None:
            conditions.append(sql.SQL("time <= %s"))
            params.append(to_time)

        where_clause = (
            sql.SQL(" AND ").join(conditions) if conditions else sql.SQL("TRUE")
        )

        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    sql.SQL("SELECT * FROM {} WHERE {} ORDER BY time").format(
                        sql.Identifier(table), where_clause
                    ),
                    params,
                )
                rows = await cur.fetchall()

                # Convert Decimal back to float for Bar model
                return [
                    Bar(
                        time=row["time"],
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=row["volume"],
                        count=row["count"],
                    )
                    for row in rows
                ]

    async def drop_if_empty(self, symbol: str, resolution: str | Resolution) -> bool:
        """Drop table if it has zero rows.

        Used by cleanup workers to limit total table count.
        Only drops tables that exist and are empty.

        Args:
            symbol: Trading symbol
            resolution: Time resolution

        Returns:
            True if table was dropped, False if not empty or doesn't exist
        """
        table = bar_table_name(symbol, resolution)
        validate_identifier(table, "table name")

        async with self._pool.connection() as conn:
            # Check if table exists first
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "SELECT EXISTS ("
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name = %s"
                    ")",
                    (table,),
                )
                row = await cur.fetchone()
                if not row or not row["exists"]:
                    return False

                # Check if empty
                await cur.execute(
                    sql.SQL("SELECT COUNT(*) as cnt FROM {} LIMIT 1").format(
                        sql.Identifier(table)
                    )
                )
                count_row = await cur.fetchone()

                if count_row and count_row["cnt"] == 0:
                    await conn.execute(
                        sql.SQL("DROP TABLE IF EXISTS {}").format(sql.Identifier(table))
                    )
                    self._initialized_tables.discard(table)
                    return True

        return False

    async def table_exists(self, symbol: str, resolution: str | Resolution) -> bool:
        """Check if a bar table exists.

        Args:
            symbol: Trading symbol
            resolution: Time resolution

        Returns:
            True if table exists in the database
        """
        table = bar_table_name(symbol, resolution)

        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "SELECT EXISTS ("
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name = %s"
                    ")",
                    (table,),
                )
                row = await cur.fetchone()
                return bool(row and row["exists"])

    async def count_bars(self, symbol: str, resolution: str | Resolution) -> int:
        """Get count of bars in a table.

        Args:
            symbol: Trading symbol
            resolution: Time resolution

        Returns:
            Number of bars, or 0 if table doesn't exist
        """
        table = bar_table_name(symbol, resolution)

        if not await self.table_exists(symbol, resolution):
            return 0

        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    sql.SQL("SELECT COUNT(*) as cnt FROM {}").format(
                        sql.Identifier(table)
                    )
                )
                row = await cur.fetchone()
                return int(row["cnt"]) if row else 0
