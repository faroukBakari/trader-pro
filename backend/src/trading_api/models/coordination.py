"""Coordination models for bar data fetching.

[ARCHITECTURE] Wave 3B: Coordination Layer
Tables auto-created by SQLModel.metadata.create_all in PostgresDatastore.create().
No Alembic migration needed — data is ephemeral/rebuildable.

Models:
- PendingRange: Active fetch claims for duplicate prevention
- CoveredRange: Tracks available data for gap detection

[STORAGE] Hybrid time range approach:
- KEEP: range_start/range_end columns for backwards compatibility
- NEW: time_range TSTZRANGE column for native PostgreSQL range operations

The time_range column enables:
- Gap detection via range_agg() and multirange operations
- Overlap prevention via EXCLUDE USING GiST constraints
- Efficient queries via GiST indexes

[MIGRATION] time_range is nullable during transition. Once all code uses
the new column, range_start/range_end can be removed in Phase 6.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Index
from sqlalchemy.dialects.postgresql import TSTZRANGE
from sqlmodel import Field, SQLModel

from trading_api.shared.types import TstzRange


class PendingRange(SQLModel, table=True):
    """Active fetch claim for a symbol/resolution time range.

    Prevents duplicate fetches by tracking in-progress requests.
    Claims expire after TTL (default 5 min) for crash recovery.

    Statuses:
    - 'pending': Claim created, fetch not yet started
    - 'fetching': Data fetch in progress
    - 'writing': Writing to buffer/parquet
    - 'failed': Fetch or write failed (cleanup candidate)

    [MIGRATION] time_range is nullable during hybrid transition.
    Use time_range for EXCLUDE constraints to prevent overlapping claims.

    [INDEX] GiST index on (symbol, resolution, time_range) enables:
    - Overlap detection for concurrent fetch prevention
    - Support for EXCLUDE constraints
    """

    __tablename__ = "pending_ranges"  # pyright: ignore[reportAssignmentType]

    # GiST index for range operations (requires btree_gist extension)
    __table_args__ = (
        Index(
            "ix_pending_ranges_gist",
            "symbol",
            "resolution",
            "time_range",
            postgresql_using="gist",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    symbol: str = Field(index=True, description="Trading symbol (e.g., 'AAPL')")
    resolution: str = Field(
        index=True, description="Resolution string (e.g., '1D', '60')"
    )
    range_start: datetime = Field(
        description="Range start (inclusive) — DEPRECATED: use time_range",
        sa_column=Column(DateTime(timezone=True)),
    )
    range_end: datetime = Field(
        description="Range end (exclusive) — DEPRECATED: use time_range",
        sa_column=Column(DateTime(timezone=True)),
    )
    # NEW: Native PostgreSQL tstzrange for range operations
    time_range: TstzRange | None = Field(
        default=None,
        description="Native TSTZRANGE for overlap prevention",
        sa_column=Column(TSTZRANGE, nullable=True),
    )
    status: str = Field(
        index=True,
        description="Claim status: 'pending', 'fetching', 'writing', 'failed'",
    )
    owner_id: str = Field(description="Process/request identifier (UUID)")
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Claim creation timestamp",
        sa_column=Column(DateTime(timezone=True)),
    )
    expires_at: datetime = Field(
        description="Claim expiration timestamp",
        sa_column=Column(DateTime(timezone=True), index=True),
    )


class CoveredRange(SQLModel, table=True):
    """Tracks time ranges where bar data is available.

    Used for gap detection — find uncovered ranges that need fetching.

    Storage types:
    - 'buffer': Data in PostgreSQL buffer tables (hot data)
    - 'parquet': Data flushed to Parquet files (cold data)

    [MIGRATION] time_range is nullable during hybrid transition.
    Use time_range for new PostgreSQL range operations (gap detection).

    [INDEX] GiST index on (symbol, resolution, time_range) enables:
    - Efficient overlap queries (time_range && requested_range)
    - Fast containment checks (time_range @> timestamp)
    - Support for EXCLUDE constraints on overlapping ranges
    """

    __tablename__ = "covered_ranges"  # pyright: ignore[reportAssignmentType]

    # GiST index for range operations (requires btree_gist extension)
    __table_args__ = (
        Index(
            "ix_covered_ranges_gist",
            "symbol",
            "resolution",
            "time_range",
            postgresql_using="gist",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    symbol: str = Field(index=True, description="Trading symbol (e.g., 'AAPL')")
    resolution: str = Field(
        index=True, description="Resolution string (e.g., '1D', '60')"
    )
    range_start: datetime = Field(
        description="Range start (inclusive) — DEPRECATED: use time_range",
        sa_column=Column(DateTime(timezone=True)),
    )
    range_end: datetime = Field(
        description="Range end (exclusive) — DEPRECATED: use time_range",
        sa_column=Column(DateTime(timezone=True)),
    )
    # NEW: Native PostgreSQL tstzrange for range operations
    time_range: TstzRange | None = Field(
        default=None,
        description="Native TSTZRANGE for gap detection and overlap queries",
        sa_column=Column(TSTZRANGE, nullable=True),
    )
    storage: str = Field(description="Storage type: 'buffer' or 'parquet'")
    file_path: str | None = Field(
        default=None,
        description="Parquet file path (NULL for buffer storage)",
    )
    row_count: int | None = Field(
        default=None,
        description="Number of bars in this range",
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Record creation timestamp",
        sa_column=Column(DateTime(timezone=True)),
    )
