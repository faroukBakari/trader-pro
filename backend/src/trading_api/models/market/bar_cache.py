"""
Bar cache models for tracking cached and pending data ranges.

These models support the read-through cache pattern in DatafeedService,
enabling gap detection and preventing duplicate provider requests.

[ARCHITECTURE] Wave 2B: SQLModel tables with native PostgreSQL range types
- time_range uses int8range for efficient overlap queries
- GiST indexes auto-created via Int8RangeType marker
"""

import uuid
from typing import Any, cast

from sqlalchemy import BigInteger
from sqlmodel import Field, SQLModel
from sqlmodel._compat import SQLModelConfig

from trading_api.models.market.bars import Resolution
from trading_api.types import Int8RangeType, Range, StorageType


def _generate_id() -> str:
    """Generate a unique ID for cache entries."""
    return str(uuid.uuid4())


class TimeRange(Range[int]):
    """Millisecond timestamp range for bar data.

    Specializes Range[int] for time-based operations.
    Start/end are Unix timestamps in milliseconds.
    """


class PendingRange(SQLModel, table=True):
    """Tracks an in-flight provider request to prevent duplicate fetches.

    When a request is made to the provider, a PendingRange is created.
    If another request comes in for overlapping data, it can wait or
    merge rather than issuing a duplicate provider call.

    [EXPIRATION]: expires_at enables automatic cleanup of stale entries
    (e.g., if provider call failed silently or took too long).

    [EXCLUSION]: __table_args__["info"]["exclusion"] declares intent for
    non-overlapping ranges within same lookup_key. PostgresDatastore creates
    the actual EXCLUDE USING GIST constraint via exclusion_listener.
    """

    __tablename__ = cast(Any, "pending_ranges")
    __table_args__ = {
        "info": {"exclusion": {"range_field": "time_range", "group": "lookup_key"}}
    }

    id: str = Field(default_factory=_generate_id, primary_key=True)
    symbol: str = Field(..., description="Trading symbol (e.g., 'AAPL')")
    resolution: Resolution = Field(..., description="Bar resolution")
    time_range: TimeRange = Field(
        ..., sa_type=Int8RangeType, description="Requested time range"
    )
    expires_at: int = Field(
        ...,
        sa_type=BigInteger,
        index=True,
        description="Unix timestamp (ms) when this pending entry expires",
    )
    lookup_key: str = Field(
        default="",
        index=True,
        description="Composite key for symbol+resolution lookup (auto-computed)",
    )

    model_config = cast(SQLModelConfig, {"from_attributes": True})

    def model_post_init(self, __context: object) -> None:
        """Compute lookup_key after initialization."""
        if not self.lookup_key:
            object.__setattr__(
                self, "lookup_key", f"{self.symbol}_{self.resolution.value}"
            )


class CoveredRange(SQLModel, table=True):
    """Tracks a range of bars that has been successfully cached.

    Used for gap detection: when a request comes in, compare against
    covered ranges to determine what data is missing.

    [STORAGE-AWARE]: storage_type indicates where data resides,
    enabling tiered cache strategies (memory → db → datalake).

    [EXCLUSION]: __table_args__["info"]["exclusion"] declares intent for
    non-overlapping ranges within same lookup_key. PostgresDatastore creates
    the actual EXCLUDE USING GIST constraint via exclusion_listener.
    """

    __tablename__ = cast(Any, "covered_ranges")
    __table_args__ = {
        "info": {"exclusion": {"range_field": "time_range", "group": "lookup_key"}}
    }

    id: str = Field(default_factory=_generate_id, primary_key=True)
    symbol: str = Field(..., description="Trading symbol (e.g., 'AAPL')")
    resolution: Resolution = Field(..., description="Bar resolution")
    time_range: TimeRange = Field(
        ..., sa_type=Int8RangeType, description="Cached time range"
    )
    storage_type: StorageType = Field(..., description="Where bars are stored")
    bar_count: int = Field(..., ge=0, description="Number of bars in this range")
    lookup_key: str = Field(
        default="",
        index=True,
        description="Composite key for symbol+resolution lookup (auto-computed)",
    )

    model_config = cast(SQLModelConfig, {"from_attributes": True})

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
