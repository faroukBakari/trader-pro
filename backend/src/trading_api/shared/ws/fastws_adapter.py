"""
Generic FastWS adapter with built-in WebSocket endpoint
"""

import asyncio
import logging
from typing import Any, Callable

from fastapi import FastAPI

from external_packages.fastws import FastWS, Message, OperationRouter
from trading_api.shared.ws.ws_route_interface import WsRouteInterface

logger = logging.getLogger(__name__)


class FastWSAdapter(FastWS):
    """
    Self-contained WebSocket adapter with embedded endpoint

    Creates a FastWS service with subscribe/unsubscribe operations
    and registers its own WebSocket endpoint.

    Type parameter T: The business model type (e.g., Bar)
    """

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._pending_routers: list[Callable] = []
        self._broadcast_tasks: list[asyncio.Task] = []

    def include_router(
        self,
        router: OperationRouter,
        *,
        prefix: str = "",
    ) -> None:
        super().include_router(router, prefix=prefix)

        if not isinstance(router, WsRouteInterface):
            logger.warning(
                f"Router {router} is not a WsRouteInterface, skipping broadcasting setup"
            )
            return

        async def broadcast_router_messages() -> None:
            logger.info(f"Started broadcasting task for router: {router.route}")
            while True:
                try:
                    # Get message from queue (non-blocking)
                    update = await router.updates_queue.get()

                    # Get all clients subscribed to this topic
                    topics = set().union(
                        *[client.topics for client in self.connections.values()]
                    )

                    if not topics:
                        logger.info("No topic subscriptions found, continuing")
                        await asyncio.sleep(1)
                        continue

                    # Skip broadcast if no clients are subscribed
                    if update.topic not in topics:
                        logger.info(f"No clients subscribed to topic: {update.topic}")
                        await asyncio.sleep(1)
                        continue

                    try:
                        # Send message to all subscribed clients
                        await self.server_send(
                            Message(
                                type=f"{router.route}.update",
                                payload=update.model_dump(),
                            ),
                            topic=update.topic,
                        )
                        if router.route == "executions":
                            logger.info(
                                f"Broadcasted execution update on topic: {update.topic}"
                            )
                        else:
                            logger.debug(
                                f"Broadcasted message from router: {update.topic}"
                            )
                    except* Exception:
                        # Handle ExceptionGroup from TaskGroup (e.g., closed connections)
                        logger.warning(
                            f"Some clients disconnected during {router.route}.update broadcast, continuing"
                        )
                        await asyncio.sleep(1)

                except asyncio.QueueEmpty:
                    logger.warning("No messages in router queue, continuing")
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.error(f"Error broadcasting {router.route}.update: {e}")
                    await asyncio.sleep(1)

        self._pending_routers.append(broadcast_router_messages)

    def setup(self, app: FastAPI) -> None:
        """Setup FastWS with FastAPI app and start broadcasting tasks"""
        super().setup(app)

        for broadcast_coro in self._pending_routers:
            task = asyncio.create_task(
                broadcast_coro(), name=f"broadcast_{broadcast_coro.__name__}"
            )
            self._broadcast_tasks.append(task)

        self._pending_routers.clear()

    def __del__(self) -> None:
        """Cleanup broadcasting tasks on instance deletion"""
        for task in self._broadcast_tasks:
            if not task.done():
                task.cancel()
                logger.info(f"Cancelled broadcasting task: {task.get_name()}")
                logger.info(f"Cancelled broadcasting task: {task.get_name()}")
