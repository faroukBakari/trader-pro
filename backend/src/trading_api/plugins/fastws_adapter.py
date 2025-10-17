"""
Generic FastWS adapter with built-in WebSocket endpoint
"""

import logging

from pydantic import BaseModel

from external_packages.fastws import FastWS, Message
from trading_api.models.common import SubscriptionUpdate

logger = logging.getLogger(__name__)


class FastWSAdapter(FastWS):
    """
    Self-contained WebSocket adapter with embedded endpoint

    Creates a FastWS service with subscribe/unsubscribe operations
    and registers its own WebSocket endpoint.

    Type parameter T: The business model type (e.g., Bar)
    """

    async def publish(
        self,
        topic: str,
        data: BaseModel,
        message_type: str,
    ) -> None:
        """
        Publish data update to all subscribed clients

        Args:
            topic: Topic identifier (e.g., "bars:AAPL:1")
            data: Business model instance (e.g., Bar)
            message_type: Message type for the update (e.g., "bars.update")
        """
        # Create message with data model directly as payload
        message = Message(
            type=message_type,
            payload=SubscriptionUpdate(
                topic=topic,
                payload=data,
            ).model_dump(),
        )

        await self.server_send(message, topic=topic)
        logger.debug(f"Published {message_type} to topic: {topic}")
