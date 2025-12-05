"""
Market data bars and historical data models.

This module contains models related to OHLC bars,
historical data requests, and responses.
"""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class TimeFrame(str, Enum):
    """Timeframe enum for bars and historical data.

    Values use format: <count><unit> where unit is S(econds), m(inutes), H(ours), D(ays), W(eeks), M(onths)
    This ensures unique values to avoid Python enum aliasing.
    """

    SEC_5 = "5S"
    SEC_10 = "10S"
    MIN_1 = "1m"
    MIN_5 = "5m"
    MIN_15 = "15m"
    MIN_30 = "30m"
    HOUR_1 = "1H"
    DAY_1 = "1D"
    WEEK_1 = "1W"
    MONTH_1 = "1M"


class Bar(BaseModel):
    """OHLC bar model matching Bar interface"""

    time: int = Field(..., description="Bar timestamp in milliseconds")
    open: float = Field(..., description="Open price")
    high: float = Field(..., description="High price")
    low: float = Field(..., description="Low price")
    close: float = Field(..., description="Close price")
    volume: int = Field(default=0, description="Volume")
    count: Optional[int] = Field(None, description="Trades count (if available)")


class GetBarsRequest(BaseModel):
    """Request model for getBars endpoint"""

    symbol: str = Field(..., description="Symbol name")
    resolution: str = Field(..., description="Resolution")
    from_time: int = Field(..., description="From timestamp (seconds)")
    to_time: int = Field(..., description="To timestamp (seconds)")
    count_back: Optional[int] = Field(None, description="Count back")


class GetBarsResponse(BaseModel):
    """Response model for getBars endpoint"""

    bars: List[Bar] = Field(..., description="Historical bars")
    no_data: bool = Field(default=False, description="No data flag")


# Type alias for bars subscription request
class BarsSubscriptionRequest(BaseModel):
    symbol: str = Field(..., description="Symbol to subscribe to")
    resolution: str = Field(
        ...,
        description="Time resolution: '1', '5', '15', '30', '60' (minutes),"
        + " 'D' (day), 'W' (week), 'M' (month)",
    )


__all__ = [
    "TimeFrame",
    "Bar",
    "GetBarsRequest",
    "GetBarsResponse",
    "BarsSubscriptionRequest",
]
