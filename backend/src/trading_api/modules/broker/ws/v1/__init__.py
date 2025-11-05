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
from pathlib import Path
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
from trading_api.shared.ws.ws_route_interface import WsRouterInterface, WsRouteService

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


class BrokerWsRouters(WsRouterInterface):
    def __init__(self, service: WsRouteService):
        # Generate WebSocket routers for module
        module_name = Path(__file__).parent.parent.parent.name

        self.generate_routers(__file__)
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
            route="orders", tags=[module_name], service=service
        )
        position_router = PositionWsRouter(
            route="positions", tags=[module_name], service=service
        )
        execution_router = ExecutionWsRouter(
            route="executions", tags=[module_name], service=service
        )
        equity_router = EquityWsRouter(
            route="equity", tags=[module_name], service=service
        )
        broker_connection_router = BrokerConnectionWsRouter(
            route="broker-connection", tags=[module_name], service=service
        )
        super().__init__(
            [
                order_router,
                position_router,
                execution_router,
                equity_router,
                broker_connection_router,
            ],
            service=service,
        )
