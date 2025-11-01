"""
WebSocket routers for real-time broker updates

Provides real-time push notifications for:
- Orders: Order status changes (placed, filled, canceled, modified)
- Positions: Position updates (opened, closed, modified)
- Executions: Trade execution notifications
- Equity: Account balance and equity changes
- Broker Connection: Connection status to real broker
"""

import logging
import os
from typing import TYPE_CHECKING, TypeAlias

from trading_api.models.broker import (
    BrokerConnectionStatus,
    BrokerConnectionSubscriptionRequest,
    EquityData,
    EquitySubscriptionRequest,
    Execution,
    ExecutionSubscriptionRequest,
    OrderSubscriptionRequest,
    PlacedOrder,
    Position,
    PositionSubscriptionRequest,
)
from trading_api.shared.ws.generic_route import WsRouter
from trading_api.shared.ws.module_router_generator import generate_module_routers
from trading_api.shared.ws.router_interface import WsRouterInterface, WsRouteService

# Type aliases for code generation
if TYPE_CHECKING:
    OrderWsRouter: TypeAlias = WsRouter[OrderSubscriptionRequest, PlacedOrder]
    PositionWsRouter: TypeAlias = WsRouter[PositionSubscriptionRequest, Position]
    ExecutionWsRouter: TypeAlias = WsRouter[ExecutionSubscriptionRequest, Execution]
    EquityWsRouter: TypeAlias = WsRouter[EquitySubscriptionRequest, EquityData]
    BrokerConnectionWsRouter: TypeAlias = WsRouter[
        BrokerConnectionSubscriptionRequest, BrokerConnectionStatus
    ]

# Module logger for app_factory
logger = logging.getLogger(__name__)


class BrokerWsRouters(list[WsRouterInterface]):
    def __init__(self, broker_service: WsRouteService):
        # Generate WebSocket routers for module
        module_name = os.path.basename(os.path.dirname(__file__))
        try:
            generated = generate_module_routers(module_name)
            if generated:
                logger.info(f"Generated WS routers for module '{module_name}'")
        except RuntimeError as e:
            # Fail loudly with module context
            logger.error(
                f"WebSocket router generation failed for module '{module_name}'!"
            )
            logger.error(str(e))
            raise
        if not TYPE_CHECKING:
            from .ws_generated import (
                BrokerConnectionWsRouter,
                EquityWsRouter,
                ExecutionWsRouter,
                OrderWsRouter,
                PositionWsRouter,
            )

        # Instantiate routers
        order_router = OrderWsRouter(
            route="orders", tags=[module_name], service=broker_service
        )
        position_router = PositionWsRouter(
            route="positions", tags=[module_name], service=broker_service
        )
        execution_router = ExecutionWsRouter(
            route="executions", tags=[module_name], service=broker_service
        )
        equity_router = EquityWsRouter(
            route="equity", tags=[module_name], service=broker_service
        )
        broker_connection_router = BrokerConnectionWsRouter(
            route="broker-connection", tags=[module_name], service=broker_service
        )
        super().__init__(
            [
                order_router,
                position_router,
                execution_router,
                equity_router,
                broker_connection_router,
            ]
        )
