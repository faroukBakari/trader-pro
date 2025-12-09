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
from trading_api.shared.ws.ws_router import WsRouterBase, WsRouteService

# Module logger for app_factory
logger = logging.getLogger(__name__)


class OrderRouter(WsRouter[OrderSubscriptionRequest, PlacedOrder]):
    pass


class PositionRouter(WsRouter[PositionSubscriptionRequest, Position]):
    pass


class ExecutionRouter(WsRouter[ExecutionSubscriptionRequest, Execution]):
    pass


class EquityRouter(WsRouter[EquitySubscriptionRequest, EquityData]):
    pass


class BrokerConnectionRouter(
    WsRouter[BrokerConnectionSubscriptionRequest, BrokerConnectionStatus]
):
    pass


class BrokerWsRouters(WsRouterBase):
    def __init__(self, service: WsRouteService):
        # Generate WebSocket routers for module
        module_name = Path(__file__).parent.parent.parent.name

        # Instantiate routers
        order_router = OrderRouter(route="orders", tags=[module_name], service=service)
        position_router = PositionRouter(
            route="positions", tags=[module_name], service=service
        )
        execution_router = ExecutionRouter(
            route="executions", tags=[module_name], service=service
        )
        equity_router = EquityRouter(
            route="equity", tags=[module_name], service=service
        )
        broker_connection_router = BrokerConnectionRouter(
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
