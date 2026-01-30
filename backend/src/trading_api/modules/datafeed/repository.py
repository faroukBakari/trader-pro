"""
Datafeed repository interfaces and implementations.

This module defines the repository pattern for bar storage,
enabling pluggable storage backends (in-memory, PostgreSQL, etc.).
"""

from typing import TYPE_CHECKING, Union

from trading_api.models.market import Bar, Resolution
from trading_api.shared import DatastoreInterface

if TYPE_CHECKING:
    from trading_api.datastores.postgres.bars import PostgresBarRepository


class BarRepository:
    """In-memory implementation of bar repository.

    Uses nested dict structure: {symbol: {resolution: {time_ms: Bar}}}
    """

    def __init__(self, datastore: DatastoreInterface) -> None:
        # Structure: {symbol: {resolution_value: {time_ms: Bar}}}
        self._bars: dict[str, dict[str, dict[int, Bar]]] = {}
        self.__datastore = datastore

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

        # Initialize nested dicts if needed
        if symbol not in self._bars:
            self._bars[symbol] = {}
        if resolution.value not in self._bars[symbol]:
            self._bars[symbol][resolution.value] = {}

        symbol_resolution_bars = self._bars[symbol][resolution.value]
        stored_count = 0

        for bar in bars:
            # Count as stored only if it's a new timestamp
            if bar.time not in symbol_resolution_bars:
                stored_count += 1
            symbol_resolution_bars[bar.time] = bar

        return stored_count

    async def get_bars(
        self,
        symbol: str,
        resolution: Resolution,
        from_time: int,
        to_time: int,
    ) -> list[Bar]:
        """Retrieve bars within time range, sorted by time ascending."""
        symbol_bars = self._bars.get(symbol)
        if symbol_bars is None:
            return []

        resolution_bars = symbol_bars.get(resolution.value)
        if resolution_bars is None:
            return []

        # Filter bars within time range
        filtered_bars = [
            bar
            for time_ms, bar in resolution_bars.items()
            if from_time <= time_ms <= to_time
        ]

        # Sort by time ascending
        return sorted(filtered_bars, key=lambda b: b.time)

    async def drop_if_empty(self, symbol: str, resolution: Resolution) -> bool:
        """Drop in-memory table if it has zero bars.

        Used by cleanup workers to limit memory usage.
        Removes the resolution dict and optionally the symbol dict if empty.

        Args:
            symbol: Trading symbol
            resolution: Time resolution

        Returns:
            True if table was dropped, False if not empty or doesn't exist
        """
        if symbol not in self._bars:
            return False

        if resolution.value not in self._bars[symbol]:
            return False

        if len(self._bars[symbol][resolution.value]) == 0:
            del self._bars[symbol][resolution.value]
            # Clean up symbol dict if no more resolutions
            if not self._bars[symbol]:
                del self._bars[symbol]
            return True

        return False


# Type alias for bar repository implementations
# Used by DatafeedService for type hints supporting both backends
BarRepositoryType = Union["BarRepository", "PostgresBarRepository"]


__all__ = [
    "BarRepository",
    "BarRepositoryType",
]
