"""
WebSocket routers for real-time broker updates

Provides real-time push notifications for:
- Orders: Order status changes (placed, filled, canceled, modified)
- Positions: Position updates (opened, closed, modified)
- Executions: Trade execution notifications
- Equity: Account balance and equity changes
- Broker Connection: Connection status to real broker
"""

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
else:
    from .ws_generated import (
        BrokerConnectionWsRouter,
        EquityWsRouter,
        ExecutionWsRouter,
        OrderWsRouter,
        PositionWsRouter,
    )


class BrokerWsRouters(list[WsRouterInterface]):
    def __init__(self, broker_service: WsRouteService):
        # Instantiate routers
        order_router = OrderWsRouter(
            route="orders", tags=["broker"], service=broker_service
        )
        position_router = PositionWsRouter(
            route="positions", tags=["broker"], service=broker_service
        )
        execution_router = ExecutionWsRouter(
            route="executions", tags=["broker"], service=broker_service
        )
        equity_router = EquityWsRouter(
            route="equity", tags=["broker"], service=broker_service
        )
        broker_connection_router = BrokerConnectionWsRouter(
            route="broker-connection", tags=["broker"], service=broker_service
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
