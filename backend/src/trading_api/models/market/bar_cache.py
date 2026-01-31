"""
Bar cache models for tracking cached and pending data ranges.

These models support the read-through cache pattern in DatafeedService,
enabling gap detection and preventing duplicate provider requests.
"""

from pydantic import BaseModel, Field

from trading_api.models.market.bars import Resolution
from trading_api.types import Range, StorageType


class TimeRange(Range[int]):
    """Millisecond timestamp range for bar data.

    Specializes Range[int] for time-based operations.
    Start/end are Unix timestamps in milliseconds.
    """


class PendingRange(BaseModel):
    """Tracks an in-flight provider request to prevent duplicate fetches.

    When a request is made to the provider, a PendingRange is created.
    If another request comes in for overlapping data, it can wait or
    merge rather than issuing a duplicate provider call.

    [EXPIRATION]: expires_at enables automatic cleanup of stale entries
    (e.g., if provider call failed silently or took too long).
    """

    symbol: str = Field(..., description="Trading symbol (e.g., 'AAPL')")
    resolution: Resolution = Field(..., description="Bar resolution")
    time_range: TimeRange = Field(..., description="Requested time range")
    expires_at: int = Field(
        ...,
        description="Unix timestamp (ms) when this pending entry expires",
    )
    lookup_key: str = Field(
        default="",
        description="Composite key for symbol+resolution lookup (auto-computed)",
    )

    def model_post_init(self, __context: object) -> None:
        """Compute lookup_key after initialization."""
        if not self.lookup_key:
            object.__setattr__(
                self, "lookup_key", f"{self.symbol}_{self.resolution.value}"
            )


class CoveredRange(BaseModel):
    """Tracks a range of bars that has been successfully cached.

    Used for gap detection: when a request comes in, compare against
    covered ranges to determine what data is missing.

    [STORAGE-AWARE]: storage_type indicates where data resides,
    enabling tiered cache strategies (memory → db → datalake).
    """

    symbol: str = Field(..., description="Trading symbol (e.g., 'AAPL')")
    resolution: Resolution = Field(..., description="Bar resolution")
    time_range: TimeRange = Field(..., description="Cached time range")
    storage_type: StorageType = Field(..., description="Where bars are stored")
    bar_count: int = Field(..., ge=0, description="Number of bars in this range")
    lookup_key: str = Field(
        default="",
        description="Composite key for symbol+resolution lookup (auto-computed)",
    )

    def model_post_init(self, __context: object) -> None:
        """Compute lookup_key after initialization."""
        if not self.lookup_key:
            object.__setattr__(
                self, "lookup_key", f"{self.symbol}_{self.resolution.value}"
            )


__all__ = [
    "TimeRange",
    "PendingRange",
    "CoveredRange",
]
