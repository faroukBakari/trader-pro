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

from .generic import WsRouter
from .router_interface import WsRouterInterface

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
    from .generated import (
        BrokerConnectionWsRouter,
        EquityWsRouter,
        ExecutionWsRouter,
        OrderWsRouter,
        PositionWsRouter,
    )

# Instantiate routers
order_router = OrderWsRouter(route="orders", tags=["broker"])
orders_topic_builder = order_router.topic_builder

position_router = PositionWsRouter(route="positions", tags=["broker"])
positions_topic_builder = position_router.topic_builder

execution_router = ExecutionWsRouter(route="executions", tags=["broker"])
executions_topic_builder = execution_router.topic_builder

equity_router = EquityWsRouter(route="equity", tags=["broker"])
equity_topic_builder = equity_router.topic_builder

broker_connection_router = BrokerConnectionWsRouter(
    route="broker-connection", tags=["broker"]
)
broker_connection_topic_builder = broker_connection_router.topic_builder

# Export all routers for main app registration
ws_routers: list[WsRouterInterface] = [
    order_router,
    position_router,
    execution_router,
    equity_router,
    broker_connection_router,
]
