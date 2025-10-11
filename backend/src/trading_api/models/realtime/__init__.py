"""
Real-time streaming models for the trading API.

This package contains models related to WebSocket messages,
real-time data streams, and channel management.
"""

from ..common import WebSocketMessage, WebSocketResponse, WebSocketSubscription
from .channels import (
    ChannelConfig,
    ChannelStatus,
    SubscriptionConfirmation,
    WebSocketServerConfig,
)
from .market_streams import (
    CandlestickUpdate,
    MarketDataTick,
    OrderBookUpdate,
    TradeUpdate,
)
from .system import HeartbeatMessage, SystemMessage, TradingNotification

__all__: list[str] = [
    # Base WebSocket types
    "WebSocketMessage",
    "WebSocketResponse",
    "WebSocketSubscription",
    # Channel management
    "ChannelConfig",
    "ChannelStatus",
    "SubscriptionConfirmation",
    "WebSocketServerConfig",
    # Market data streams
    "MarketDataTick",
    "OrderBookUpdate",
    "TradeUpdate",
    "CandlestickUpdate",
    # System messages
    "HeartbeatMessage",
    "SystemMessage",
    "TradingNotification",
    # Union types
]
