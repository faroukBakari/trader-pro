"""
Market data streaming models.

This module contains real-time market data models for
live price feeds, order books, trades, and chart data.
"""

from typing import List, Literal, Optional

from pydantic import Field

from ..common import WebSocketMessage


class MarketDataTick(WebSocketMessage):
    """Real-time market data tick"""

    type: Literal["market_tick"] = "market_tick"
    channel: Literal["market_data"] = "market_data"
    symbol: str = Field(..., description="Symbol name")
    price: float = Field(..., description="Current price")
    volume: Optional[int] = Field(None, description="Volume")
    bid: Optional[float] = Field(None, description="Bid price")
    ask: Optional[float] = Field(None, description="Ask price")
    change: Optional[float] = Field(None, description="Price change")
    change_percent: Optional[float] = Field(None, description="Price change percentage")


class OrderBookUpdate(WebSocketMessage):
    """Order book update message"""

    type: Literal["orderbook_update"] = "orderbook_update"
    channel: Literal["orderbook"] = "orderbook"
    symbol: str = Field(..., description="Symbol name")
    bids: List[List[float]] = Field(..., description="Bid orders [price, quantity]")
    asks: List[List[float]] = Field(..., description="Ask orders [price, quantity]")
    sequence: int = Field(..., description="Sequence number for ordering")


class TradeUpdate(WebSocketMessage):
    """Individual trade update"""

    type: Literal["trade"] = "trade"
    channel: Literal["trades"] = "trades"
    symbol: str = Field(..., description="Symbol name")
    price: float = Field(..., description="Trade price")
    quantity: float = Field(..., description="Trade quantity")
    side: Literal["buy", "sell"] = Field(..., description="Trade side")
    trade_id: str = Field(..., description="Unique trade ID")


class CandlestickUpdate(WebSocketMessage):
    """Real-time candlestick/bar update"""

    type: Literal["candlestick"] = "candlestick"
    channel: Literal["chart_data"] = "chart_data"
    symbol: str = Field(..., description="Symbol name")
    resolution: str = Field(..., description="Time resolution")
    time: int = Field(..., description="Bar timestamp (milliseconds)")
    open: float = Field(..., description="Open price")
    high: float = Field(..., description="High price")
    low: float = Field(..., description="Low price")
    close: float = Field(..., description="Close price")
    volume: Optional[int] = Field(None, description="Volume")
    is_final: bool = Field(..., description="Whether this bar is final or updating")


__all__ = [
    "MarketDataTick",
    "OrderBookUpdate",
    "TradeUpdate",
    "CandlestickUpdate",
]
