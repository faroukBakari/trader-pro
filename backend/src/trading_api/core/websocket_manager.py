"""
WebSocket connection manager for real-time trading data
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set

from fastapi import WebSocket

from .websocket_models import (
    AuthenticationMessage,
    AuthenticationResponse,
    ChannelStatus,
    HeartbeatMessage,
    SubscriptionConfirmation,
    WebSocketMessage,
    WebSocketServerConfig,
    WebSocketSubscription,
)

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and message routing"""

    def __init__(self, config: WebSocketServerConfig):
        self.config = config
        # Active connections: connection_id -> WebSocket
        self.active_connections: Dict[str, WebSocket] = {}
        # Connection metadata: connection_id -> ConnectionInfo
        self.connection_info: Dict[str, dict] = {}
        # Channel subscriptions: channel -> set of connection_ids
        self.subscriptions: Dict[str, Set[str]] = {}
        # Symbol-specific subscriptions: channel:symbol -> set of connection_ids
        self.symbol_subscriptions: Dict[str, Set[str]] = {}
        # Authenticated connections
        self.authenticated_connections: Set[str] = set()
        # Rate limiting: connection_id -> {channel: last_message_times}
        self.rate_limits: Dict[str, Dict[str, List[float]]] = {}

    async def connect(self, websocket: WebSocket, connection_id: str) -> None:
        """Accept a new WebSocket connection"""
        await websocket.accept()
        self.active_connections[connection_id] = websocket
        self.connection_info[connection_id] = {
            "connected_at": datetime.now(),
            "last_activity": datetime.now(),
            "user_agent": websocket.headers.get("user-agent", "unknown"),
            "ip": websocket.client.host if websocket.client else "unknown",
        }
        self.rate_limits[connection_id] = {}

        logger.info(f"WebSocket connection established: {connection_id}")

        # Send initial configuration or welcome message
        await self._send_welcome_message(websocket, connection_id)

    async def disconnect(self, connection_id: str) -> None:
        """Handle WebSocket disconnection"""
        if connection_id in self.active_connections:
            # Remove from all subscriptions
            for channel in list(self.subscriptions.keys()):
                self.subscriptions[channel].discard(connection_id)
                if not self.subscriptions[channel]:
                    del self.subscriptions[channel]

            # Remove symbol subscriptions
            for symbol_channel in list(self.symbol_subscriptions.keys()):
                self.symbol_subscriptions[symbol_channel].discard(connection_id)
                if not self.symbol_subscriptions[symbol_channel]:
                    del self.symbol_subscriptions[symbol_channel]

            # Clean up connection data
            del self.active_connections[connection_id]
            del self.connection_info[connection_id]
            self.authenticated_connections.discard(connection_id)
            self.rate_limits.pop(connection_id, None)

            logger.info(f"WebSocket connection closed: {connection_id}")

    async def subscribe(
        self, connection_id: str, subscription: WebSocketSubscription
    ) -> SubscriptionConfirmation:
        """Handle subscription request"""
        channel = subscription.channel
        symbol = subscription.symbol

        # Check if channel exists in configuration
        channel_config = next(
            (c for c in self.config.channels if c.name == channel), None
        )
        if not channel_config:
            return SubscriptionConfirmation(
                type="subscription_confirmation",
                timestamp=datetime.now(),
                channel=channel,
                request_id=None,
                subscribed_channel=channel,
                symbol=symbol,
                success=False,
                error=f"Channel '{channel}' not found",
            )

        # Check authentication requirement
        if (
            channel_config.requires_auth
            and connection_id not in self.authenticated_connections
        ):
            return SubscriptionConfirmation(
                type="subscription_confirmation",
                timestamp=datetime.now(),
                channel=channel,
                request_id=None,
                subscribed_channel=channel,
                symbol=symbol,
                success=False,
                error=f"Channel '{channel}' requires authentication",
            )

        # Check subscriber limits
        current_subscribers = len(self.subscriptions.get(channel, set()))
        if (
            channel_config.max_subscribers
            and current_subscribers >= channel_config.max_subscribers
        ):
            return SubscriptionConfirmation(
                type="subscription_confirmation",
                timestamp=datetime.now(),
                channel=channel,
                request_id=None,
                subscribed_channel=channel,
                symbol=symbol,
                success=False,
                error=f"Channel '{channel}' has reached maximum subscribers",
            )

        # Handle subscription
        if subscription.action == "subscribe":
            # Add to channel subscriptions
            if channel not in self.subscriptions:
                self.subscriptions[channel] = set()
            self.subscriptions[channel].add(connection_id)

            # Add to symbol-specific subscriptions if symbol specified
            if symbol:
                symbol_key = f"{channel}:{symbol}"
                if symbol_key not in self.symbol_subscriptions:
                    self.symbol_subscriptions[symbol_key] = set()
                self.symbol_subscriptions[symbol_key].add(connection_id)

            logger.info(
                f"Connection {connection_id} subscribed to {channel}"
                + (f":{symbol}" if symbol else "")
            )

        elif subscription.action == "unsubscribe":
            # Remove from channel subscriptions
            if channel in self.subscriptions:
                self.subscriptions[channel].discard(connection_id)
                if not self.subscriptions[channel]:
                    del self.subscriptions[channel]

            # Remove from symbol-specific subscriptions
            if symbol:
                symbol_key = f"{channel}:{symbol}"
                if symbol_key in self.symbol_subscriptions:
                    self.symbol_subscriptions[symbol_key].discard(connection_id)
                    if not self.symbol_subscriptions[symbol_key]:
                        del self.symbol_subscriptions[symbol_key]

            logger.info(
                f"Connection {connection_id} unsubscribed from {channel}"
                + (f":{symbol}" if symbol else "")
            )

        return SubscriptionConfirmation(
            type="subscription_confirmation",
            timestamp=datetime.now(),
            channel=channel,
            request_id=None,
            subscribed_channel=channel,
            symbol=symbol,
            success=True,
            error=None,
        )

    async def authenticate(
        self, connection_id: str, auth_message: AuthenticationMessage
    ) -> AuthenticationResponse:
        """Handle WebSocket authentication"""
        # TODO: Implement proper JWT token validation
        # For now, we'll do a simple mock validation

        try:
            # Mock validation - in production, validate JWT token
            if auth_message.token and len(auth_message.token) > 10:
                self.authenticated_connections.add(connection_id)
                logger.info(f"Connection {connection_id} authenticated successfully")

                return AuthenticationResponse(
                    type="auth_response",
                    timestamp=datetime.now(),
                    channel="auth",
                    request_id=None,
                    success=True,
                    error=None,
                    user_id="user_123",  # Extract from JWT in production
                    permissions=["read", "trade"],  # Extract from JWT in production
                )
            else:
                return AuthenticationResponse(
                    type="auth_response",
                    timestamp=datetime.now(),
                    channel="auth",
                    request_id=None,
                    success=False,
                    error="Invalid token",
                    user_id=None,
                    permissions=None,
                )
        except Exception as e:
            logger.error(f"Authentication error for {connection_id}: {e}")
            return AuthenticationResponse(
                type="auth_response",
                timestamp=datetime.now(),
                channel="auth",
                request_id=None,
                success=False,
                error="Authentication failed",
                user_id=None,
                permissions=None,
            )

    async def broadcast_to_channel(
        self, channel: str, message: WebSocketMessage, symbol: Optional[str] = None
    ) -> int:
        """Broadcast message to all subscribers of a channel"""
        sent_count = 0

        # Determine target connections
        if symbol:
            symbol_key = f"{channel}:{symbol}"
            target_connections = self.symbol_subscriptions.get(symbol_key, set())
        else:
            target_connections = self.subscriptions.get(channel, set())

        # Send to all target connections
        disconnected = []
        for connection_id in target_connections:
            if connection_id in self.active_connections:
                try:
                    websocket = self.active_connections[connection_id]
                    await websocket.send_text(message.model_dump_json())
                    sent_count += 1

                    # Update last activity
                    if connection_id in self.connection_info:
                        self.connection_info[connection_id][
                            "last_activity"
                        ] = datetime.now()

                except Exception as e:
                    logger.error(f"Failed to send message to {connection_id}: {e}")
                    disconnected.append(connection_id)

        # Clean up disconnected connections
        for connection_id in disconnected:
            await self.disconnect(connection_id)

        return sent_count

    async def send_to_connection(
        self, connection_id: str, message: WebSocketMessage
    ) -> bool:
        """Send message to a specific connection"""
        if connection_id not in self.active_connections:
            return False

        try:
            websocket = self.active_connections[connection_id]
            await websocket.send_text(message.model_dump_json())

            # Update last activity
            if connection_id in self.connection_info:
                self.connection_info[connection_id]["last_activity"] = datetime.now()

            return True
        except Exception as e:
            logger.error(f"Failed to send message to {connection_id}: {e}")
            await self.disconnect(connection_id)
            return False

    async def start_heartbeat(self) -> None:
        """Start heartbeat task for connection health monitoring"""

        async def heartbeat_task() -> None:
            while True:
                try:
                    await asyncio.sleep(self.config.heartbeat_interval)

                    # Send heartbeat to all connections
                    heartbeat = HeartbeatMessage(
                        timestamp=datetime.now(),
                        channel="heartbeat",
                        request_id=None,
                        server_time=datetime.now(),
                    )

                    await self.broadcast_to_channel("heartbeat", heartbeat)

                    # Check for stale connections (optional)
                    await self._cleanup_stale_connections()

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Heartbeat task error: {e}")

        # Start the heartbeat task
        asyncio.create_task(heartbeat_task())

    async def get_channel_status(self, channel: str) -> ChannelStatus:
        """Get status information for a channel"""
        subscriber_count = len(self.subscriptions.get(channel, set()))

        # Determine channel status
        if channel in [c.name for c in self.config.channels]:
            status = "active" if subscriber_count > 0 else "inactive"
        else:
            status = "error"

        # Ensure status is the correct literal type
        if status not in ["active", "inactive", "error"]:
            status = "error"

        return ChannelStatus(
            type="channel_status",
            timestamp=datetime.now(),
            channel=channel,
            request_id=None,
            status=status,  # type: ignore
            subscriber_count=subscriber_count,
            message=f"Channel has {subscriber_count} subscribers",
        )

    def get_connection_stats(self) -> dict:
        """Get connection statistics"""
        return {
            "total_connections": len(self.active_connections),
            "authenticated_connections": len(self.authenticated_connections),
            "total_subscriptions": sum(
                len(subs) for subs in self.subscriptions.values()
            ),
            "channels_with_subscribers": len(self.subscriptions),
            "symbol_subscriptions": len(self.symbol_subscriptions),
        }

    async def _send_welcome_message(
        self, websocket: WebSocket, connection_id: str
    ) -> None:
        """Send welcome message with available channels"""
        welcome_data = {
            "type": "welcome",
            "timestamp": datetime.now().isoformat(),
            "connection_id": connection_id,
            "available_channels": [
                {
                    "name": channel.name,
                    "description": channel.description,
                    "requires_auth": channel.requires_auth,
                    "rate_limit": channel.rate_limit,
                }
                for channel in self.config.channels
            ],
            "heartbeat_interval": self.config.heartbeat_interval,
        }

        try:
            await websocket.send_text(json.dumps(welcome_data, default=str))
        except Exception as e:
            logger.error(f"Failed to send welcome message to {connection_id}: {e}")

    async def _cleanup_stale_connections(self) -> None:
        """Clean up connections that haven't been active"""
        # This is optional - implement based on your requirements
        # For example, disconnect connections that haven't sent any message in X minutes
        pass

    def _check_rate_limit(self, connection_id: str, channel: str) -> bool:
        """Check if connection is within rate limits for channel"""
        # Implement rate limiting logic
        # This is a simplified version - you might want more sophisticated rate limiting
        return True


# Global connection manager instance
websocket_config = WebSocketServerConfig()
connection_manager = ConnectionManager(websocket_config)
