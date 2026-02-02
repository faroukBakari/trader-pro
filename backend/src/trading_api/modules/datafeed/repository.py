"""
Datafeed repository interfaces and implementations.

This module defines the repository pattern for bar storage,
enabling pluggable storage backends (in-memory, PostgreSQL, etc.).

[ARCHITECTURE] Bar storage uses:
- Dynamic SQLModel tables per symbol/resolution (bars_{symbol}_{resolution})
- B-tree index on time column via primary key
- Bulk operations (get_many/set_many) for efficient time-range queries
"""

from typing import Any, cast

from trading_api.models.market import Bar, Resolution
from trading_api.shared import DatastoreInterface, TableInterface


class BarRepository:
    """Bar repository using DatastoreInterface.

    Creates a separate table per symbol/resolution combination.
    Tables are named: bars_{symbol}_{resolution} (e.g., bars_aapl_1d)
    Bars are keyed by timestamp (milliseconds).

    [PERFORMANCE] Caches both model classes and table interfaces to avoid
    repeated table() calls and dynamic class creation.
    """

    def __init__(self, datastore: DatastoreInterface) -> None:
        self._datastore = datastore
        # Cache dynamic Bar subclasses to avoid recreating them
        self._model_cache: dict[str, type[Bar]] = {}
        # Cache table interfaces for direct reuse
        self._table_cache: dict[str, TableInterface[Bar]] = {}

    def _get_table_name(self, symbol: str, resolution: Resolution) -> str:
        """Generate table name for symbol/resolution combo."""
        safe_symbol = symbol.replace("/", "_").replace("-", "_").lower()
        return f"bars_{safe_symbol}_{resolution.value.lower()}"

    def _create_bar_model(self, table_name: str) -> type[Bar]:
        """Create dynamic Bar subclass with custom __tablename__.

        SQLModel requires table=True classes to have unique __tablename__.
        We create subclasses dynamically to support per-symbol/resolution tables.
        """
        return cast(
            type[Bar],
            type(
                table_name,
                (Bar,),
                {"__tablename__": cast(Any, table_name)},
            ),
        )

    def _get_bar_table(
        self, symbol: str, resolution: Resolution
    ) -> TableInterface[Bar]:
        """Get or create a cached table interface for symbol/resolution.

        Caches both the model class and the table interface for performance.
        The table interface caching avoids repeated datastore.table() calls.
        """
        table_name = self._get_table_name(symbol, resolution)

        # Return cached interface if available
        if table_name in self._table_cache:
            return self._table_cache[table_name]

        # Create model class if not cached
        if table_name not in self._model_cache:
            self._model_cache[table_name] = self._create_bar_model(table_name)

        # Create and cache table interface
        table = self._datastore.table(self._model_cache[table_name])
        self._table_cache[table_name] = table

        return table

    async def store_bars(
        self,
        symbol: str,
        resolution: Resolution,
        bars: list[Bar],
    ) -> int:
        """Store bars using bulk upsert.

        Uses set_many() for efficient batch INSERT...ON CONFLICT when available.
        Falls back to individual set() calls for datastores without bulk support.

        Bars are keyed by timestamp - newer bars with same timestamp
        replace existing ones (upsert semantics).

        Returns:
            Count of NEW bars inserted (not updates to existing timestamps).
        """
        if not bars:
            return 0

        table = self._get_bar_table(symbol, resolution)

        # Try bulk operation first (PostgreSQL)
        try:
            return await table.set_many(bars)
        except NotImplementedError:
            # Fallback for InMemoryDatastore - count only new inserts
            stored_count = 0
            for bar in bars:
                key = str(bar.time)
                if not await table.exists(key):
                    stored_count += 1
                await table.set(key, bar)
            return stored_count

    async def get_bars(
        self,
        symbol: str,
        resolution: Resolution,
        from_time: int,
        to_time: int,
    ) -> list[Bar]:
        """Retrieve bars within time range using indexed query.

        Uses get_many() for efficient B-tree range scan when available.
        Falls back to filtering all values for datastores without range support.

        Returns bars sorted by time ascending.
        """
        table = self._get_bar_table(symbol, resolution)

        # Try indexed range query first (PostgreSQL)
        try:
            return await table.get_many(from_time, to_time)
        except NotImplementedError:
            # Fallback for InMemoryDatastore - load and filter
            all_bars = await table.values()
            filtered_bars = [
                bar for bar in all_bars if from_time <= bar.time <= to_time
            ]
            return sorted(filtered_bars, key=lambda b: b.time)

    async def drop_if_empty(self, symbol: str, resolution: Resolution) -> bool:
        """Drop table if it has zero bars.

        Used by cleanup workers to limit memory/storage usage.

        Args:
            symbol: Trading symbol
            resolution: Time resolution

        Returns:
            True if table was dropped, False if not empty or doesn't exist
        """
        table_name = self._get_table_name(symbol, resolution)
        table = self._get_bar_table(symbol, resolution)

        if await table.is_empty:
            # Drop the table from datastore
            dropped = await self._datastore.drop_table(table_name)
            if dropped:
                # Clean up both caches
                self._model_cache.pop(table_name, None)
                self._table_cache.pop(table_name, None)
            return dropped

        return False


__all__ = [
    "BarRepository",
]
