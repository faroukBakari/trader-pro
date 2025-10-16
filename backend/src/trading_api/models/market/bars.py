"""
Market data bars and historical data models.

This module contains models related to OHLC bars,
historical data requests, and responses.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class Bar(BaseModel):
    """OHLC bar model matching Bar interface"""

    time: int = Field(..., description="Bar timestamp in milliseconds")
    open: float = Field(..., description="Open price")
    high: float = Field(..., description="High price")
    low: float = Field(..., description="Low price")
    close: float = Field(..., description="Close price")
    volume: int = Field(default=0, description="Volume")


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
        default="1",
        description="Time resolution: '1', '5', '15', '30', '60' (minutes),"
        + " 'D' (day), 'W' (week), 'M' (month)",
    )


__all__ = [
    "Bar",
    "GetBarsRequest",
    "GetBarsResponse",
]
