"""
Trading API models package

This package contains all Pydantic models used throughout the trading API,
organized by functionality:
- common/: Shared base models and utilities
- market/: Market data, instruments, quotes, and bars
- broker/: Orders, positions, executions, and account operations
- auth/: Authentication and user models
"""

# Import from auth domain
from .auth import (
    DeviceInfo,
    GoogleLoginRequest,
    LogoutRequest,
    RefreshRequest,
    RefreshTokenData,
    TokenData,
    TokenResponse,
    User,
    UserCreate,
    UserInDB,
)

# Import from broker domain
from .broker import (
    AccountMetainfo,
    Brackets,
    BrokerConnectionStatus,
    BrokerConnectionSubscriptionRequest,
    EquityData,
    EquitySubscriptionRequest,
    Execution,
    ExecutionSubscriptionRequest,
    LeverageInfo,
    LeverageInfoParams,
    LeveragePreviewResult,
    LeverageSetParams,
    LeverageSetResult,
    OrderPreviewResult,
    OrderPreviewSection,
    OrderPreviewSectionRow,
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
    SuccessResponse,
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
from .versioning import APIMetadata, VersionInfo

__all__ = [
    # Common utilities
    "BaseApiResponse",
    "SubscriptionUpdate",
    "ErrorApiResponse",
    "SubscriptionResponse",
    "BarsSubscriptionRequest",
    # Auth models
    "User",
    "UserCreate",
    "UserInDB",
    "TokenResponse",
    "RefreshRequest",
    "LogoutRequest",
    "DeviceInfo",
    "GoogleLoginRequest",
    "TokenData",
    "RefreshTokenData",
    # Market data models
    "Bar",
    "DatafeedConfiguration",
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
    "OrderPreviewResult",
    "OrderPreviewSection",
    "OrderPreviewSectionRow",
    "Position",
    "Execution",
    "AccountMetainfo",
    "Brackets",
    "LeverageInfo",
    "LeverageInfoParams",
    "LeverageSetParams",
    "LeverageSetResult",
    "LeveragePreviewResult",
    "SuccessResponse",
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
    "VersionInfo",
]
