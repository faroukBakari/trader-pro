"""
Market data quotes and real-time pricing models.

This module contains models related to real-time quotes,
quote values, and quote requests.
"""

from typing import List, Literal, Union

from pydantic import BaseModel, Field


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


class GetQuotesRequest(BaseModel):
    """Request model for getQuotes endpoint"""

    symbols: List[str] = Field(..., description="Symbol names")


class QuoteDataSubscriptionRequest(BaseModel):
    """
    Request model for quote data subscription.

    Matches TradingView's subscribeQuotes interface.
    Supports subscribing to multiple symbols with different update frequencies.
    """

    symbols: List[str] = Field(
        ...,
        description="Symbols requiring slow updates (once per minute) - "
        "e.g., watchlist items not currently visible",
    )
    fast_symbols: List[str] = Field(
        ...,
        description="Symbols requiring fast updates (at least every 10 seconds) - "
        "e.g., currently visible or active symbols",
    )


__all__ = [
    "QuoteValues",
    "QuoteData",
    "GetQuotesRequest",
    "QuoteDataSubscriptionRequest",
]
