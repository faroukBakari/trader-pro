"""
WebSocket API endpoints for real-time trading data
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from ..core.websocket_manager import connection_manager
from ..core.websocket_models import (
    AuthenticationMessage,
    WebSocketServerConfig,
    WebSocketSubscription,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["websocket"])


async def handle_websocket_message(
    websocket: WebSocket, connection_id: str, message_data: Dict[str, Any]
) -> None:
    """Handle incoming WebSocket messages"""

    message_type = message_data.get("type")

    if message_type == "subscribe" or message_type == "unsubscribe":
        # Handle subscription/unsubscription
        try:
            subscription = WebSocketSubscription(
                action=message_type,
                channel=message_data.get("channel", ""),
                symbol=message_data.get("symbol"),
                params=message_data.get("params"),
            )

            response = await connection_manager.subscribe(connection_id, subscription)
            await connection_manager.send_to_connection(connection_id, response)

        except Exception as e:
            logger.error(f"Subscription error for {connection_id}: {e}")
            error_response = {
                "type": "subscription_error",
                "timestamp": datetime.now().isoformat(),
                "channel": message_data.get("channel", "unknown"),
                "error": str(e),
                "success": False,
            }
            await websocket.send_text(json.dumps(error_response, default=str))

    elif message_type == "auth":
        # Handle authentication
        try:
            auth_message = AuthenticationMessage(
                type="auth",
                timestamp=datetime.now(),
                channel="auth",
                request_id=None,
                token=message_data.get("token", ""),
            )

            auth_response = await connection_manager.authenticate(
                connection_id, auth_message
            )
            await connection_manager.send_to_connection(connection_id, auth_response)

        except Exception as e:
            logger.error(f"Authentication error for {connection_id}: {e}")
            error_response = {
                "type": "auth_error",
                "timestamp": datetime.now().isoformat(),
                "channel": "auth",
                "error": str(e),
                "success": False,
            }
            await websocket.send_text(json.dumps(error_response, default=str))

    elif message_type == "ping":
        # Handle ping/pong for custom heartbeat
        pong_response = {
            "type": "pong",
            "timestamp": datetime.now().isoformat(),
            "channel": "heartbeat",
            "success": True,
        }
        await websocket.send_text(json.dumps(pong_response, default=str))

    elif message_type == "channel_status":
        # Handle channel status request
        try:
            channel = message_data.get("channel", "")
            status_response = await connection_manager.get_channel_status(channel)
            await connection_manager.send_to_connection(connection_id, status_response)

        except Exception as e:
            logger.error(f"Channel status error for {connection_id}: {e}")

    else:
        # Unknown message type
        error_response = {
            "type": "error",
            "timestamp": datetime.now().isoformat(),
            "channel": "system",
            "error": f"Unknown message type: {message_type}",
            "success": False,
        }
        await websocket.send_text(json.dumps(error_response, default=str))


@router.websocket("/v1")
async def websocket_endpoint(
    websocket: WebSocket, client_id: Optional[str] = Query(None)
) -> None:
    """
    Main WebSocket endpoint for real-time trading data.

    Supports multiple channels:
    - market_data: Real-time price updates
    - orderbook: Order book depth updates
    - trades: Recent trade updates
    - chart_data: Candlestick/bar updates
    - account: Account balance updates (requires auth)
    - positions: Position updates (requires auth)
    - orders: Order status updates (requires auth)
    - notifications: Trading notifications (requires auth)
    - system: System status messages
    - heartbeat: Connection health monitoring
    """
    connection_id = str(uuid.uuid4())

    try:
        # Accept connection and register with manager
        await connection_manager.connect(websocket, connection_id)

        # Main message handling loop
        while True:
            try:
                data = await websocket.receive_text()
                message_data = json.loads(data)

                # Update last activity
                if connection_id in connection_manager.connection_info:
                    connection_manager.connection_info[connection_id][
                        "last_activity"
                    ] = datetime.now()

                # Route message based on type
                await handle_websocket_message(websocket, connection_id, message_data)

            except json.JSONDecodeError:
                error_response = {
                    "type": "error",
                    "timestamp": datetime.now().isoformat(),
                    "channel": "system",
                    "error": "Invalid JSON message",
                    "success": False,
                }
                await websocket.send_text(json.dumps(error_response, default=str))

            except Exception as e:
                logger.error(f"Error processing message from {connection_id}: {e}")
                error_response = {
                    "type": "error",
                    "timestamp": datetime.now().isoformat(),
                    "channel": "system",
                    "error": "Message processing error",
                    "success": False,
                }
                await websocket.send_text(json.dumps(error_response, default=str))

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {connection_id}")
    except Exception as e:
        logger.error(f"WebSocket error for {connection_id}: {e}")
    finally:
        await connection_manager.disconnect(connection_id)


@router.get(
    "/config",
    summary="Get WebSocket configuration",
    operation_id="getWebSocketConfig",
    response_model=WebSocketServerConfig,
)
async def get_websocket_config() -> WebSocketServerConfig:
    """Get WebSocket server configuration"""
    return connection_manager.config


@router.get(
    "/stats",
    summary="Get WebSocket connection statistics",
    operation_id="getWebSocketStats",
)
async def get_websocket_stats() -> Dict[str, Any]:
    """Get real-time WebSocket connection statistics"""
    stats = connection_manager.get_connection_stats()

    stats.update(
        {
            "server_config": {
                "max_connections": connection_manager.config.max_connections,
                "heartbeat_interval": connection_manager.config.heartbeat_interval,
                "message_size_limit": connection_manager.config.message_size_limit,
            },
            "channels": [
                {
                    "name": channel.name,
                    "description": channel.description,
                    "requires_auth": channel.requires_auth,
                    "rate_limit": channel.rate_limit,
                    "max_subscribers": channel.max_subscribers,
                    "current_subscribers": len(
                        connection_manager.subscriptions.get(channel.name, set())
                    ),
                }
                for channel in connection_manager.config.channels
            ],
        }
    )

    return stats
