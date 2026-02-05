"""
Datafeed repository interfaces and implementations.

This module defines the repository pattern for bar storage,
enabling pluggable storage backends (in-memory, PostgreSQL, etc.).

[ARCHITECTURE] Bar storage uses:
- Dynamic SQLModel tables per symbol/resolution (bars_{symbol}_{resolution})
- B-tree index on time column via primary key
- Bulk operations (get_time_range/set_batch) for efficient time-range queries
"""

from trading_api.models.market import Bar, Resolution
from trading_api.shared import (
    DatastoreInterface,
    TableInterface,
    TimeSeriesTableInterface,
    create_dynamic_table_model,
)


class BarRepository:
    """Bar repository using DatastoreInterface.

    Creates a separate table per symbol/resolution combination.
    Tables are named: bars_{symbol}_{resolution} (e.g., bars_aapl_1d)
    Bars are keyed by timestamp (milliseconds).

    [PERFORMANCE] Uses TimeSeriesTableInterface for optimized
    time-range queries (get_time_range) and batch inserts (set_batch).
    Falls back to TableInterface for datastores without time-series support.
    """

    def __init__(self, datastore: DatastoreInterface) -> None:
        self._datastore = datastore
        # Cache dynamic Bar subclasses to avoid recreating them
        self._model_cache: dict[str, type[Bar]] = {}
        # Cache table interfaces for direct reuse
        self._table_cache: dict[str, TableInterface[Bar]] = {}
        # Cache timeseries interfaces (preferred for bar storage)
        self._timeseries_cache: dict[str, TimeSeriesTableInterface[Bar]] = {}

    def _get_table_name(self, symbol: str, resolution: Resolution) -> str:
        """Generate table name for symbol/resolution combo."""
        safe_symbol = symbol.replace("/", "_").replace("-", "_").lower()
        return f"bars_{safe_symbol}_{resolution.value.lower()}"

    def _create_bar_model(self, table_name: str) -> type[Bar]:
        """Dynamically create a SQLModel Bar subclass for the given table name."""
        return create_dynamic_table_model(Bar, table_name)

    def _get_bar_table(
        self, symbol: str, resolution: Resolution
    ) -> TableInterface[Bar]:
        """Get or create a cached table interface for symbol/resolution.

        Used as fallback when timeseries interface is not available.
        """
        table_name = self._get_table_name(symbol, resolution)

        # Return cached timeseries interface if available
        if table_name in self._timeseries_cache:
            return self._timeseries_cache[table_name]

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

    def _get_timeseries_table(
        self, symbol: str, resolution: Resolution
    ) -> TimeSeriesTableInterface[Bar]:
        """Get or create a cached timeseries table interface.
        Used for efficient time-range queries and batch inserts.
        """

        table_name = self._get_table_name(symbol, resolution)

        # Return cached interface if available
        if table_name in self._timeseries_cache:
            return self._timeseries_cache[table_name]

        # Create model class if not cached
        if table_name not in self._model_cache:
            self._model_cache[table_name] = self._create_bar_model(table_name)

        ts_table = self._datastore.timeseries_table(self._model_cache[table_name])
        self._timeseries_cache[table_name] = ts_table
        return ts_table

    async def store_bars(
        self,
        symbol: str,
        resolution: Resolution,
        bars: list[Bar],
    ) -> int:
        """Store bars using bulk upsert.

        Uses set_batch() for efficient batch INSERT...ON CONFLICT when available.
        Falls back to individual set() calls for datastores without bulk support.

        Bars are keyed by timestamp - newer bars with same timestamp
        replace existing ones (upsert semantics).

        Returns:
            Count of NEW bars inserted (not updates to existing timestamps).
        """
        if not bars:
            return 0

        # Try timeseries interface first (preferred for PostgreSQL)
        if self._datastore.has_capability("timeseries"):
            ts_table = self._get_timeseries_table(symbol, resolution)
            return await ts_table.set_batch(bars)

        # Fallback for InMemoryDatastore - count only new inserts
        table = self._get_bar_table(symbol, resolution)
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

        Uses get_time_range() for efficient B-tree range scan when available.
        Falls back to filtering all values for datastores without range support.

        Returns bars sorted by time ascending.
        """
        # Try timeseries interface first (preferred for PostgreSQL)
        if self._datastore.has_capability("timeseries"):
            ts_table = self._get_timeseries_table(symbol, resolution)
            return await ts_table.get_time_range(from_time, to_time)

        # Fallback for InMemoryDatastore - load and filter
        table = self._get_bar_table(symbol, resolution)
        all_bars = await table.values()
        filtered_bars = [bar for bar in all_bars if from_time <= bar.time <= to_time]
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
                # Clean up all caches
                self._model_cache.pop(table_name, None)
                self._table_cache.pop(table_name, None)
                self._timeseries_cache.pop(table_name, None)
            return dropped

        return False


__all__ = [
    "BarRepository",
]
