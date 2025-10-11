"""
Channel management and subscription models.

This module contains models related to WebSocket channel
configuration, subscriptions, and channel status management.
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from ..common import WebSocketMessage, WebSocketResponse


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


class ChannelStatus(WebSocketMessage):
    """Channel status update"""

    type: Literal["channel_status"] = "channel_status"
    channel: str = Field(..., description="Channel name")
    status: Literal["active", "inactive", "error"] = Field(
        ..., description="Channel status"
    )
    subscriber_count: int = Field(..., description="Number of active subscribers")
    message: Optional[str] = Field(None, description="Status message")


class SubscriptionConfirmation(WebSocketResponse):
    """Subscription confirmation message"""

    type: Literal["subscription_confirmation"] = "subscription_confirmation"
    subscribed_channel: str = Field(..., description="Confirmed subscription channel")
    symbol: Optional[str] = Field(None, description="Symbol filter (if applicable)")


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


__all__ = [
    "ChannelConfig",
    "ChannelStatus",
    "SubscriptionConfirmation",
    "WebSocketServerConfig",
]
