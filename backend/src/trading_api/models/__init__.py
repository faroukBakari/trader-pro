"""
Trading API models package

This package contains all Pydantic models used throughout the trading API,
organized by functionality:
- models.py: Core datafeed and market data models
- websocket_models.py: WebSocket and real-time message models
"""

# Datafeed and market data models
from .models import (
    Bar,
    DatafeedConfiguration,
    DatafeedHealthResponse,
    DatafeedSymbolType,
    ErrorResponse,
    Exchange,
    GetBarsRequest,
    GetBarsResponse,
    GetQuotesRequest,
    QuoteData,
    QuoteValues,
    SearchSymbolResultItem,
    SearchSymbolsRequest,
    SymbolInfo,
)

# WebSocket and real-time models
from .websocket_models import (
    AuthenticationMessage,
    AuthenticationResponse,
    BalanceUpdate,
    CandlestickUpdate,
    ChannelConfig,
    ChannelStatus,
    HeartbeatMessage,
    MarketDataTick,
    OrderBookUpdate,
    OrderUpdate,
    PositionUpdate,
    SubscriptionConfirmation,
    SystemMessage,
    TradeUpdate,
    TradingNotification,
    WebSocketMessage,
    WebSocketMessageUnion,
    WebSocketResponse,
    WebSocketServerConfig,
    WebSocketSubscription,
)

__all__ = [
    # Datafeed models
    "Bar",
    "DatafeedConfiguration",
    "DatafeedHealthResponse",
    "DatafeedSymbolType",
    "ErrorResponse",
    "Exchange",
    "GetBarsRequest",
    "GetBarsResponse",
    "GetQuotesRequest",
    "QuoteData",
    "QuoteValues",
    "SearchSymbolResultItem",
    "SearchSymbolsRequest",
    "SymbolInfo",
    # WebSocket models
    "AuthenticationMessage",
    "AuthenticationResponse",
    "BalanceUpdate",
    "CandlestickUpdate",
    "ChannelConfig",
    "ChannelStatus",
    "HeartbeatMessage",
    "MarketDataTick",
    "OrderBookUpdate",
    "OrderUpdate",
    "PositionUpdate",
    "SubscriptionConfirmation",
    "SystemMessage",
    "TradeUpdate",
    "TradingNotification",
    "WebSocketMessage",
    "WebSocketMessageUnion",
    "WebSocketResponse",
    "WebSocketServerConfig",
    "WebSocketSubscription",
]
