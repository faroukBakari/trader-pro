"""
Pydantic models for datafeed API
"""

from typing import List, Literal, Optional, Union

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


class Bar(BaseModel):
    """OHLC bar model matching Bar interface"""

    time: int = Field(..., description="Bar timestamp in milliseconds")
    open: float = Field(..., description="Open price")
    high: float = Field(..., description="High price")
    low: float = Field(..., description="Low price")
    close: float = Field(..., description="Close price")
    volume: Optional[int] = Field(None, description="Volume")


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


class QuoteValues(BaseModel):
    """Quote values model matching DatafeedQuoteValues interface"""

    lp: float = Field(..., description="Last price")
    ask: float = Field(..., description="Ask price")
    bid: float = Field(..., description="Bid price")
    spread: float = Field(..., description="Spread")
    open_price: float = Field(..., description="Open price")
    high_price: float = Field(..., description="High price")
    low_price: float = Field(..., description="Low price")
    prev_close_price: float = Field(..., description="Previous close price")
    volume: int = Field(..., description="Volume")
    ch: float = Field(..., description="Change")
    chp: float = Field(..., description="Change percent")
    short_name: str = Field(..., description="Short name")
    exchange: str = Field(..., description="Exchange")
    description: str = Field(..., description="Description")
    original_name: str = Field(..., description="Original name")


class QuoteData(BaseModel):
    """Quote data model matching QuoteData interface"""

    s: Literal["ok", "error"] = Field(..., description="Status")
    n: str = Field(..., description="Symbol name")
    v: Union[QuoteValues, dict] = Field(..., description="Quote values or error")


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


class SearchSymbolsRequest(BaseModel):
    """Request model for searchSymbols endpoint"""

    user_input: str = Field(..., description="User search input")
    exchange: str = Field(default="", description="Exchange filter")
    symbol_type: str = Field(default="", description="Symbol type filter")
    max_results: int = Field(default=50, description="Maximum results")


class GetQuotesRequest(BaseModel):
    """Request model for getQuotes endpoint"""

    symbols: List[str] = Field(..., description="Symbol names")


class ErrorResponse(BaseModel):
    """Error response model"""

    error: str = Field(..., description="Error message")
    details: Optional[str] = Field(None, description="Error details")


class DatafeedHealthResponse(BaseModel):
    """Datafeed health check response model"""

    status: str = Field(..., description="Health status")
    message: str = Field(..., description="Health message")
    symbols_loaded: int = Field(..., description="Number of symbols loaded")
    bars_count: int = Field(..., description="Number of sample bars generated")
    timestamp: str = Field(..., description="Timestamp of health check")
