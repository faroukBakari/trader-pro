"""
Datafeed repository interfaces and implementations.

This module defines the repository pattern for bar storage,
enabling pluggable storage backends (in-memory, PostgreSQL, etc.).
"""

from trading_api.models.market import Bar, Resolution
from trading_api.shared import DatastoreInterface, TableInterface


class BarRepository:
    """Bar repository using DatastoreInterface.

    Creates a separate table per symbol/resolution combination.
    Tables are named: bars_{symbol}_{resolution} (e.g., bars_aapl_1d)
    Bars are keyed by timestamp (milliseconds).
    """

    def __init__(self, datastore: DatastoreInterface) -> None:
        self._datastore = datastore
        # Cache dynamic Bar subclasses to avoid recreating them
        self._table_classes: dict[str, type[Bar]] = {}

    def _get_table_name(self, symbol: str, resolution: Resolution) -> str:
        """Generate table name for symbol/resolution combo."""
        safe_symbol = symbol.replace("/", "_").replace("-", "_").lower()
        return f"bars_{safe_symbol}_{resolution.value.lower()}"

    def _get_bar_table(
        self, symbol: str, resolution: Resolution
    ) -> TableInterface[Bar]:
        """Get or create a table for the symbol/resolution combination."""
        table_name = self._get_table_name(symbol, resolution)

        if table_name not in self._table_classes:
            # Create dynamic Bar subclass with custom class name
            # InMemoryDatastore uses class name as table name
            # PostgresDatastore uses __tablename__ for JSONB storage
            self._table_classes[table_name] = type(
                table_name,
                (Bar,),
                {"__tablename__": table_name},
            )

        return self._datastore.table(self._table_classes[table_name])

    async def store_bars(
        self,
        symbol: str,
        resolution: Resolution,
        bars: list[Bar],
    ) -> int:
        """Store bars, deduplicating by timestamp.

        Bars are keyed by timestamp - new bars with same timestamp
        replace existing ones (upsert semantics).
        """
        if not bars:
            return 0

        table = self._get_bar_table(symbol, resolution)
        stored_count = 0

        for bar in bars:
            key = str(bar.time)
            # Count as stored only if it's a new timestamp
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
        """Retrieve bars within time range, sorted by time ascending."""
        table = self._get_bar_table(symbol, resolution)

        # Get all bars and filter by time range
        all_bars = await table.values()

        # Filter bars within time range
        filtered_bars = [bar for bar in all_bars if from_time <= bar.time <= to_time]

        # Sort by time ascending
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
                # Clean up cached class
                self._table_classes.pop(table_name, None)
            return dropped

        return False


__all__ = [
    "BarRepository",
]
