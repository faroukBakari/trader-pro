"""
Trading API broker models package

This package contains Pydantic models for broker operations:
- Orders: PreOrder, PlacedOrder, OrderStatus, OrderType, OrderSubscriptionRequest
- Positions: Position, Side, PositionSubscriptionRequest
- Executions: Execution, ExecutionSubscriptionRequest
- Account: AccountMetainfo, PlaceOrderResult, EquityData, EquitySubscriptionRequest
- Leverage: LeverageInfo, LeverageSetParams, LeverageSetResult, LeveragePreviewResult
- Brackets: Brackets
- Connection: BrokerConnectionStatus, BrokerConnectionSubscriptionRequest
"""

from .account import AccountMetainfo, EquityData, EquitySubscriptionRequest
from .common import SuccessResponse
from .connection import BrokerConnectionStatus, BrokerConnectionSubscriptionRequest
from .executions import Execution, ExecutionSubscriptionRequest
from .leverage import (
    Brackets,
    LeverageInfo,
    LeverageInfoParams,
    LeveragePreviewResult,
    LeverageSetParams,
    LeverageSetResult,
)
from .orders import (
    OrderPreviewResult,
    OrderPreviewSection,
    OrderPreviewSectionRow,
    OrderStatus,
    OrderSubscriptionRequest,
    OrderType,
    PlacedOrder,
    PlaceOrderResult,
    PreOrder,
    Side,
    StopType,
)
from .positions import Position, PositionSubscriptionRequest

__all__ = [
    # Enums
    "OrderStatus",
    "OrderType",
    "Side",
    "StopType",
    # Order models
    "PreOrder",
    "PlacedOrder",
    "PlaceOrderResult",
    "OrderPreviewResult",
    "OrderPreviewSection",
    "OrderPreviewSectionRow",
    # Position models
    "Position",
    # Execution models
    "Execution",
    # Account models
    "AccountMetainfo",
    # Leverage models
    "Brackets",
    "LeverageInfo",
    "LeverageInfoParams",
    "LeverageSetParams",
    "LeverageSetResult",
    "LeveragePreviewResult",
    # WebSocket models
    "OrderSubscriptionRequest",
    "PositionSubscriptionRequest",
    "ExecutionSubscriptionRequest",
    "EquitySubscriptionRequest",
    "BrokerConnectionSubscriptionRequest",
    "EquityData",
    "BrokerConnectionStatus",
    # Common models
    "SuccessResponse",
]
