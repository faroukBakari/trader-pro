"""
WebSocket and real-time message models for event-driven endpoints
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


# Base WebSocket Message Models
class WebSocketMessage(BaseModel):
    """Base WebSocket message with common fields"""

    type: str = Field(..., description="Message type")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Message timestamp"
    )
    channel: str = Field(..., description="WebSocket channel name")
    request_id: Optional[str] = Field(None, description="Request ID for correlation")


class WebSocketResponse(WebSocketMessage):
    """Base WebSocket response message"""

    success: bool = Field(..., description="Response success status")
    error: Optional[str] = Field(None, description="Error message if failed")


class WebSocketSubscription(BaseModel):
    """WebSocket subscription request"""

    action: Literal["subscribe", "unsubscribe"] = Field(
        ..., description="Subscription action"
    )
    channel: str = Field(..., description="Channel to subscribe/unsubscribe")
    symbol: Optional[str] = Field(None, description="Symbol filter (if applicable)")
    params: Optional[Dict[str, Any]] = Field(None, description="Additional parameters")


# Market Data Models
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


# Portfolio and Account Models
class BalanceUpdate(WebSocketMessage):
    """Account balance update"""

    type: Literal["balance_update"] = "balance_update"
    channel: Literal["account"] = "account"
    asset: str = Field(..., description="Asset symbol (USD, BTC, etc.)")
    available: float = Field(..., description="Available balance")
    locked: float = Field(..., description="Locked balance")
    total: float = Field(..., description="Total balance")


class PositionUpdate(WebSocketMessage):
    """Position update message"""

    type: Literal["position_update"] = "position_update"
    channel: Literal["positions"] = "positions"
    symbol: str = Field(..., description="Symbol name")
    side: Literal["long", "short"] = Field(..., description="Position side")
    size: float = Field(..., description="Position size")
    entry_price: float = Field(..., description="Average entry price")
    mark_price: float = Field(..., description="Current mark price")
    unrealized_pnl: float = Field(..., description="Unrealized P&L")
    realized_pnl: float = Field(..., description="Realized P&L")


# Order Management Models
class OrderUpdate(WebSocketMessage):
    """Order status update"""

    type: Literal["order_update"] = "order_update"
    channel: Literal["orders"] = "orders"
    order_id: str = Field(..., description="Order ID")
    symbol: str = Field(..., description="Symbol name")
    side: Literal["buy", "sell"] = Field(..., description="Order side")
    order_type: Literal["market", "limit", "stop", "stop_limit"] = Field(
        ..., description="Order type"
    )
    status: Literal["pending", "open", "filled", "cancelled", "rejected"] = Field(
        ..., description="Order status"
    )
    quantity: float = Field(..., description="Order quantity")
    filled_quantity: float = Field(..., description="Filled quantity")
    price: Optional[float] = Field(None, description="Order price (for limit orders)")
    average_fill_price: Optional[float] = Field(None, description="Average fill price")


# Notification Models
class TradingNotification(WebSocketMessage):
    """Trading notification message"""

    type: Literal["notification"] = "notification"
    channel: Literal["notifications"] = "notifications"
    category: Literal["info", "warning", "error", "success"] = Field(
        ..., description="Notification category"
    )
    title: str = Field(..., description="Notification title")
    message: str = Field(..., description="Notification message")
    data: Optional[Dict[str, Any]] = Field(
        None, description="Additional notification data"
    )


# Chart Data Models
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


# System Messages
class SystemMessage(WebSocketMessage):
    """System status or maintenance message"""

    type: Literal["system"] = "system"
    channel: Literal["system"] = "system"
    event: Literal["maintenance", "service_update", "market_hours"] = Field(
        ..., description="System event type"
    )
    message: str = Field(..., description="System message")
    data: Optional[Dict[str, Any]] = Field(None, description="Additional system data")


class HeartbeatMessage(WebSocketMessage):
    """Heartbeat/ping message for connection health"""

    type: Literal["heartbeat"] = "heartbeat"
    channel: Literal["heartbeat"] = "heartbeat"
    server_time: datetime = Field(
        default_factory=datetime.now, description="Server timestamp"
    )


# Authentication Models
class AuthenticationMessage(WebSocketMessage):
    """WebSocket authentication message"""

    type: Literal["auth"] = "auth"
    channel: Literal["auth"] = "auth"
    token: str = Field(..., description="JWT authentication token")


class AuthenticationResponse(WebSocketResponse):
    """WebSocket authentication response"""

    type: Literal["auth_response"] = "auth_response"
    channel: Literal["auth"] = "auth"
    user_id: Optional[str] = Field(None, description="Authenticated user ID")
    permissions: Optional[List[str]] = Field(None, description="User permissions")


# Subscription Management
class SubscriptionConfirmation(WebSocketResponse):
    """Subscription confirmation message"""

    type: Literal["subscription_confirmation"] = "subscription_confirmation"
    subscribed_channel: str = Field(..., description="Confirmed subscription channel")
    symbol: Optional[str] = Field(None, description="Symbol filter (if applicable)")


class ChannelStatus(WebSocketMessage):
    """Channel status update"""

    type: Literal["channel_status"] = "channel_status"
    channel: str = Field(..., description="Channel name")
    status: Literal["active", "inactive", "error"] = Field(
        ..., description="Channel status"
    )
    subscriber_count: int = Field(..., description="Number of active subscribers")
    message: Optional[str] = Field(None, description="Status message")


# Union type for all possible WebSocket messages
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


# Channel Configuration
class ChannelConfig(BaseModel):
    """Configuration for WebSocket channels"""

    name: str = Field(..., description="Channel name")
    description: str = Field(..., description="Channel description")
    requires_auth: bool = Field(
        default=False, description="Whether channel requires authentication"
    )
    rate_limit: Optional[int] = Field(None, description="Rate limit per second")
    max_subscribers: Optional[int] = Field(None, description="Maximum subscribers")
    message_types: List[str] = Field(..., description="Supported message types")


# WebSocket Server Configuration
class WebSocketServerConfig(BaseModel):
    """WebSocket server configuration"""

    channels: List[ChannelConfig] = Field(
        default=[
            ChannelConfig(
                name="market_data",
                description="Real-time market price feeds",
                requires_auth=False,
                rate_limit=100,
                max_subscribers=500,
                message_types=["market_tick"],
            ),
            ChannelConfig(
                name="orderbook",
                description="Order book depth updates",
                requires_auth=False,
                rate_limit=50,
                max_subscribers=200,
                message_types=["orderbook_update"],
            ),
            ChannelConfig(
                name="trades",
                description="Recent trade updates",
                requires_auth=False,
                rate_limit=100,
                max_subscribers=300,
                message_types=["trade"],
            ),
            ChannelConfig(
                name="chart_data",
                description="Real-time chart/candlestick data",
                requires_auth=False,
                rate_limit=10,
                max_subscribers=100,
                message_types=["candlestick"],
            ),
            ChannelConfig(
                name="account",
                description="Account balance and status updates",
                requires_auth=True,
                rate_limit=10,
                max_subscribers=50,
                message_types=["balance_update"],
            ),
            ChannelConfig(
                name="positions",
                description="Position updates",
                requires_auth=True,
                rate_limit=20,
                max_subscribers=50,
                message_types=["position_update"],
            ),
            ChannelConfig(
                name="orders",
                description="Order status updates",
                requires_auth=True,
                rate_limit=50,
                max_subscribers=100,
                message_types=["order_update"],
            ),
            ChannelConfig(
                name="notifications",
                description="Trading notifications and alerts",
                requires_auth=True,
                rate_limit=20,
                max_subscribers=200,
                message_types=["notification"],
            ),
            ChannelConfig(
                name="system",
                description="System status and maintenance messages",
                requires_auth=False,
                rate_limit=5,
                max_subscribers=1000,
                message_types=["system"],
            ),
            ChannelConfig(
                name="heartbeat",
                description="Connection health monitoring",
                requires_auth=False,
                rate_limit=1,
                max_subscribers=1000,
                message_types=["heartbeat"],
            ),
        ]
    )

    heartbeat_interval: int = Field(
        default=30, description="Heartbeat interval in seconds"
    )
    max_connections: int = Field(
        default=1000, description="Maximum concurrent connections"
    )
    message_size_limit: int = Field(
        default=1024 * 1024, description="Maximum message size in bytes"
    )
