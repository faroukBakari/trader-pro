"""
Trading API models package

This package contains all Pydantic models used throughout the trading API,
organized by functionality:
- common/: Shared base models and utilities
- market/: Market data, instruments, quotes, and bars
- trading/: Orders, positions, and trading operations
- account/: User accounts, authentication, and balances
- realtime/: WebSocket messages and real-time streams
"""

from typing import Union

# Import from account domain
from .account import AuthenticationMessage, AuthenticationResponse, BalanceUpdate

# Import from common utilities
from .common import (
    ErrorResponse,
    WebSocketMessage,
    WebSocketResponse,
    WebSocketSubscription,
)

# Import from market data domain
from .market import (
    Bar,
    DatafeedConfiguration,
    DatafeedHealthResponse,
    DatafeedSymbolType,
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

# Import from realtime domain
from .realtime import (
    CandlestickUpdate,
    ChannelConfig,
    ChannelStatus,
    HeartbeatMessage,
    MarketDataTick,
    OrderBookUpdate,
    SubscriptionConfirmation,
    SystemMessage,
    TradeUpdate,
    TradingNotification,
    WebSocketServerConfig,
)

# Import from trading domain
from .trading import OrderUpdate, PositionUpdate

WebSocketMessageUnion = Union[
    MarketDataTick,
    OrderBookUpdate,
    TradeUpdate,
    BalanceUpdate,
    PositionUpdate,
    OrderUpdate,
    TradingNotification,
    CandlestickUpdate,
    SystemMessage,
    HeartbeatMessage,
    AuthenticationMessage,
    AuthenticationResponse,
    SubscriptionConfirmation,
    ChannelStatus,
]

__all__ = [
    # Common utilities
    "ErrorResponse",
    "WebSocketMessage",
    "WebSocketResponse",
    "WebSocketSubscription",
    # Market data models
    "Bar",
    "DatafeedConfiguration",
    "DatafeedHealthResponse",
    "DatafeedSymbolType",
    "Exchange",
    "GetBarsRequest",
    "GetBarsResponse",
    "GetQuotesRequest",
    "QuoteData",
    "QuoteValues",
    "SearchSymbolResultItem",
    "SearchSymbolsRequest",
    "SymbolInfo",
    # Trading models
    "OrderUpdate",
    "PositionUpdate",
    # Account models
    "AuthenticationMessage",
    "AuthenticationResponse",
    "BalanceUpdate",
    # Real-time models
    "CandlestickUpdate",
    "ChannelConfig",
    "ChannelStatus",
    "HeartbeatMessage",
    "MarketDataTick",
    "OrderBookUpdate",
    "SubscriptionConfirmation",
    "SystemMessage",
    "TradeUpdate",
    "TradingNotification",
    "WebSocketMessageUnion",
    "WebSocketServerConfig",
]
