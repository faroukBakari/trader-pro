"""
Trading API models package

This package contains all Pydantic models used throughout the trading API,
organized by functionality:
- common/: Shared base models and utilities
- market/: Market data, instruments, quotes, and bars
- trading/: Orders, positions, and trading operations
- account/: User accounts, authentication, and balances
"""

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
]
