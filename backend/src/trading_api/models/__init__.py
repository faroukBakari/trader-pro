"""
Trading API models package

This package contains all Pydantic models used throughout the trading API,
organized by functionality:
- common/: Shared base models and utilities
- market/: Market data, instruments, quotes, and bars
- broker/: Orders, positions, executions, and account operations
"""

# Import from broker domain
from .broker import (
    AccountMetainfo,
    BrokerConnectionStatus,
    BrokerConnectionSubscriptionRequest,
    EquityData,
    EquitySubscriptionRequest,
    Execution,
    ExecutionSubscriptionRequest,
    OrderStatus,
    OrderSubscriptionRequest,
    OrderType,
    PlacedOrder,
    PlaceOrderResult,
    Position,
    PositionSubscriptionRequest,
    PreOrder,
    Side,
    StopType,
)

# Import from common utilities
from .common import (
    BaseApiResponse,
    ErrorApiResponse,
    SubscriptionResponse,
    SubscriptionUpdate,
)
from .health import HealthResponse

# Import from market data domain
from .market import (
    Bar,
    BarsSubscriptionRequest,
    DatafeedConfiguration,
    DatafeedHealthResponse,
    DatafeedSymbolType,
    Exchange,
    GetBarsRequest,
    GetBarsResponse,
    GetQuotesRequest,
    QuoteData,
    QuoteDataSubscriptionRequest,
    QuoteValues,
    SearchSymbolResultItem,
    SearchSymbolsRequest,
    SymbolInfo,
)

# Import versioning models
from .versioning import VERSION_CONFIG, APIMetadata, APIVersion, VersionInfo

__all__ = [
    # Common utilities
    "BaseApiResponse",
    "SubscriptionUpdate",
    "ErrorApiResponse",
    "SubscriptionResponse",
    "BarsSubscriptionRequest",
    # Market data models
    "Bar",
    "DatafeedConfiguration",
    "DatafeedHealthResponse",
    "DatafeedSymbolType",
    "Exchange",
    "GetBarsRequest",
    "GetBarsResponse",
    "GetQuotesRequest",
    "QuoteData",
    "QuoteValues",
    "SearchSymbolResultItem",
    "SearchSymbolsRequest",
    "SymbolInfo",
    "QuoteDataSubscriptionRequest",
    # Broker models
    "OrderStatus",
    "OrderType",
    "Side",
    "StopType",
    "PreOrder",
    "PlacedOrder",
    "PlaceOrderResult",
    "Position",
    "Execution",
    "AccountMetainfo",
    # Broker WebSocket models
    "OrderSubscriptionRequest",
    "PositionSubscriptionRequest",
    "ExecutionSubscriptionRequest",
    "EquityData",
    "EquitySubscriptionRequest",
    "BrokerConnectionStatus",
    "BrokerConnectionSubscriptionRequest",
    # Health model
    "HealthResponse",
    # Versioning models
    "APIMetadata",
    "APIVersion",
    "VERSION_CONFIG",
    "VersionInfo",
    # WebSocket Router models
    "WsRouteService",
]
