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
    JWTPayload,
    LogoutRequest,
    RefreshRequest,
    RefreshTokenData,
    TokenData,
    TokenIntrospectResponse,
    TokenResponse,
    User,
    UserCreate,
    UserData,
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
    "BarsSubscriptionRequest",
    "ErrorApiResponse",
    "SubscriptionResponse",
    "SubscriptionUpdate",
    # Auth models
    "DeviceInfo",
    "GoogleLoginRequest",
    "JWTPayload",
    "LogoutRequest",
    "RefreshRequest",
    "RefreshTokenData",
    "TokenData",
    "TokenIntrospectResponse",
    "TokenResponse",
    "User",
    "UserCreate",
    "UserData",
    "UserInDB",
    # Market data models
    "Bar",
    "DatafeedConfiguration",
    "DatafeedSymbolType",
    "Exchange",
    "GetBarsRequest",
    "GetBarsResponse",
    "GetQuotesRequest",
    "QuoteData",
    "QuoteDataSubscriptionRequest",
    "QuoteValues",
    "SearchSymbolResultItem",
    "SearchSymbolsRequest",
    "SymbolInfo",
    # Broker models
    "AccountMetainfo",
    "Brackets",
    "Execution",
    "LeverageInfo",
    "LeverageInfoParams",
    "LeveragePreviewResult",
    "LeverageSetParams",
    "LeverageSetResult",
    "OrderPreviewResult",
    "OrderPreviewSection",
    "OrderPreviewSectionRow",
    "OrderStatus",
    "OrderType",
    "PlaceOrderResult",
    "PlacedOrder",
    "Position",
    "PreOrder",
    "Side",
    "StopType",
    "SuccessResponse",
    # Broker WebSocket models
    "BrokerConnectionStatus",
    "BrokerConnectionSubscriptionRequest",
    "EquityData",
    "EquitySubscriptionRequest",
    "ExecutionSubscriptionRequest",
    "OrderSubscriptionRequest",
    "PositionSubscriptionRequest",
    # Health model
    "HealthResponse",
    # Versioning models
    "APIMetadata",
    "VersionInfo",
]
