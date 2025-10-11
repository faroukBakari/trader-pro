"""
Market data instruments and symbol information models.

This module contains models related to financial instruments,
symbols, exchanges, and symbol metadata.
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class SymbolInfo(BaseModel):
    """Symbol information model matching LibrarySymbolInfo interface"""

    name: str = Field(..., description="Symbol name")
    description: str = Field(..., description="Symbol description")
    type: str = Field(..., description="Symbol type (stock, crypto, forex, etc.)")
    session: str = Field(..., description="Trading session hours")
    timezone: str = Field(..., description="Symbol timezone")
    ticker: Optional[str] = Field(None, description="Symbol ticker")
    exchange: str = Field(..., description="Exchange name")
    listed_exchange: str = Field(..., description="Listed exchange")
    format: str = Field(..., description="Price format")
    pricescale: int = Field(..., description="Price scale")
    minmov: int = Field(..., description="Minimum movement")
    has_intraday: bool = Field(..., description="Has intraday data")
    has_daily: bool = Field(..., description="Has daily data")
    supported_resolutions: List[str] = Field(..., description="Supported resolutions")
    volume_precision: int = Field(..., description="Volume precision")
    data_status: Literal["streaming", "endofday", "delayed_streaming"] = Field(
        ..., description="Data status"
    )


class SearchSymbolResultItem(BaseModel):
    """Search result item model matching SearchSymbolResultItem interface"""

    symbol: str = Field(..., description="Symbol name")
    description: str = Field(..., description="Symbol description")
    exchange: str = Field(..., description="Exchange name")
    ticker: Optional[str] = Field(None, description="Symbol ticker")
    type: str = Field(..., description="Symbol type")


class Exchange(BaseModel):
    """Exchange descriptor model matching Exchange interface"""

    value: str = Field(
        ..., description="Value to be passed as exchange argument to searchSymbols"
    )
    name: str = Field(..., description="Name of the exchange")
    desc: str = Field(..., description="Description of the exchange")


class DatafeedSymbolType(BaseModel):
    """Symbol type descriptor model matching DatafeedSymbolType interface"""

    name: str = Field(..., description="Name of the symbol type")
    value: str = Field(
        ..., description="Value to be passed as symbolType argument to searchSymbols"
    )


__all__ = [
    "SymbolInfo",
    "SearchSymbolResultItem",
    "Exchange",
    "DatafeedSymbolType",
]
