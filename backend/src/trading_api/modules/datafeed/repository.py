"""
Datafeed repository interfaces and implementations.

This module defines the repository pattern for bar storage,
enabling pluggable storage backends (in-memory, PostgreSQL, etc.).
"""

from trading_api.models.market import Bar, Resolution
from trading_api.shared import DatastoreInterface


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


__all__ = [
    "BarRepository",
]
