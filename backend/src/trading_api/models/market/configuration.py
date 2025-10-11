"""
Market data configuration and health models.

This module contains models related to datafeed configuration,
health checks, and system status.
"""

from typing import List, Optional

from pydantic import BaseModel, Field

from .instruments import DatafeedSymbolType, Exchange


class DatafeedConfiguration(BaseModel):
    """Datafeed configuration model matching DatafeedConfiguration interface"""

    supported_resolutions: Optional[List[str]] = Field(
        default=["5", "1D", "1W"], description="Supported resolutions"
    )
    supports_marks: Optional[bool] = Field(default=False, description="Supports marks")
    supports_timescale_marks: Optional[bool] = Field(
        default=False, description="Supports timescale marks"
    )
    supports_time: Optional[bool] = Field(default=False, description="Supports time")

    exchanges: Optional[List[Exchange]] = Field(
        default=[
            Exchange(value="", name="All Exchanges", desc=""),
            Exchange(value="NASDAQ", name="NASDAQ", desc="NASDAQ"),
            Exchange(value="NYSE", name="NYSE", desc="NYSE"),
        ],
        description="Available exchanges",
    )
    symbols_types: Optional[List[DatafeedSymbolType]] = Field(
        default=[
            DatafeedSymbolType(name="All types", value=""),
            DatafeedSymbolType(name="Stock", value="stock"),
            DatafeedSymbolType(name="Crypto", value="crypto"),
            DatafeedSymbolType(name="Forex", value="forex"),
        ],
        description="Available symbol types",
    )


class DatafeedHealthResponse(BaseModel):
    """Datafeed health check response model"""

    status: str = Field(..., description="Health status")
    message: str = Field(..., description="Health message")
    symbols_loaded: int = Field(..., description="Number of symbols loaded")
    bars_count: int = Field(..., description="Number of sample bars generated")
    timestamp: str = Field(..., description="Timestamp of health check")


__all__ = [
    "DatafeedConfiguration",
    "DatafeedHealthResponse",
]
