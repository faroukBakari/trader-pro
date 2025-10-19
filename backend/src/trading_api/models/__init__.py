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
    Execution,
    OrderStatus,
    OrderType,
    PlacedOrder,
    PlaceOrderResult,
    Position,
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
]
