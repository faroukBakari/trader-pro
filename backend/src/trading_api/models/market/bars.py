"""
Market data bars and historical data models.

This module contains models related to OHLC bars,
historical data requests, and responses.

[ARCHITECTURE] Wave X: Bar upgraded to SQLModel table=True for PostgreSQL
typed column storage. Supports dynamic table names via __tablename__ override.
"""

from enum import Enum
from typing import Any, List, Optional, cast

from pydantic import BaseModel
from sqlalchemy import BigInteger
from sqlmodel import Field, SQLModel


class Resolution(str, Enum):
    """Resolution enum matching TradingView's ResolutionString format.

    TradingView uses:
    - Minutes: "1", "5", "15", "30", "60", "120", "240" (plain numbers)
    - Days: "1D"
    - Weeks: "1W"
    - Months: "1M", "3M", "6M", "12M"

    This enum uses the canonical TradingView format for type-safe resolution handling.
    """

    MIN_1 = "1"
    MIN_5 = "5"
    MIN_15 = "15"
    MIN_30 = "30"
    HOUR_1 = "60"
    HOUR_2 = "120"
    HOUR_4 = "240"
    DAY_1 = "1D"
    WEEK_1 = "1W"
    MONTH_1 = "1M"
    MONTH_3 = "3M"
    MONTH_6 = "6M"
    YEAR_1 = "12M"


class Bar(SQLModel, table=True):
    """OHLC bar model with PostgreSQL typed column storage.

    [ARCHITECTURE] SQLModel table=True enables:
    - B-tree index on time (primary key) for efficient range queries
    - Typed columns for open/high/low/close/volume
    - Batch upsert via INSERT...ON CONFLICT

    __tablename__ is dynamically overridden per symbol/resolution combo
    by BarRepository._create_bar_model(). Template name prevents conflicts.
    """

    __tablename__ = cast(Any, "bar_template")  # Overridden dynamically

    time: int = Field(
        sa_type=BigInteger,
        primary_key=True,
        description="Bar timestamp in milliseconds",
    )
    open: float = Field(description="Open price")
    high: float = Field(description="High price")
    low: float = Field(description="Low price")
    close: float = Field(description="Close price")
    volume: int = Field(default=0, description="Volume")
    count: int | None = Field(default=None, description="Trades count (if available)")


class GetBarsRequest(BaseModel):
    """Request model for getBars endpoint"""

    symbol: str = Field(..., description="Symbol name")
    resolution: Resolution = Field(..., description="Resolution (TradingView format)")
    from_time: int = Field(..., description="From timestamp (seconds)")
    to_time: int = Field(..., description="To timestamp (seconds)")
    count_back: Optional[int] = Field(None, description="Count back")


class GetBarsResult(BaseModel):
    """Internal result from service get_bars() with gap-bridging metadata."""

    bars: List[Bar] = Field(default_factory=list)
    next_time: Optional[int] = Field(
        None, description="Nearest previous bar timestamp (ms) for gap bridging"
    )


class GetBarsResponse(BaseModel):
    """Response model for getBars endpoint"""

    bars: List[Bar] = Field(..., description="Historical bars")
    no_data: bool = Field(default=False, description="No data flag")
    next_time: Optional[int] = Field(
        None, description="Nearest previous bar timestamp (ms) for gap bridging"
    )


# Type alias for bars subscription request
class BarsSubscriptionRequest(BaseModel):
    symbol: str = Field(..., description="Symbol to subscribe to")
    resolution: Resolution = Field(
        ...,
        description="Time resolution in TradingView format: '1', '5', '15', '30', '60' (minutes),"
        + " '1D' (day), '1W' (week), '1M' (month)",
    )


__all__ = [
    "Resolution",
    "Bar",
    "GetBarsRequest",
    "GetBarsResult",
    "GetBarsResponse",
    "BarsSubscriptionRequest",
]
