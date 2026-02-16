"""
Exception models for the Trading API.

This module defines serializable exception classes used throughout
the application for structured error handling and root cause analysis.

Exception Hierarchy:
    TradingApiException (base)
    ├── CommonException        # Infrastructure/shared/auth errors
    ├── ServiceException       # Service layer errors (+module)
    └── ProviderException      # Provider errors (+provider, +capability)

Usage:
    Exceptions bubble up through layers WITHOUT being caught until they
    reach the API/WS endpoint boundary, where they are:
    1. Logged with full context
    2. Translated to appropriate HTTP/WebSocket error format
"""

import sys
import traceback
from datetime import datetime
from types import TracebackType
from typing import Any


class TradingApiException(Exception):
    """Base exception for all Trading API errors.

    Serializable exception with structured error information
    for debugging and root cause analysis.

    Attributes:
        code: Machine-readable error code (e.g., "PROVIDER_DATAFEED_SYMBOL_NOT_FOUND")
        message: Human-readable error description
        backtrace: Full stack trace for debugging
    """

    def __init__(
        self,
        code: str,
        message: str,
        backtrace: list[traceback.FrameSummary] | TracebackType | None = None,
        timestamp: int | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.timestamp = timestamp or int(datetime.now().timestamp())

        # Convert backtrace to List[FrameSummary]
        if backtrace is None:
            # User-raised: capture from sys.exc_info() or current stack
            _, _, tb = sys.exc_info()
            if tb:
                self.backtrace = list(traceback.extract_tb(tb))
            else:
                # No active exception - capture current call stack
                self.backtrace = list(traceback.extract_stack()[:-1])
        elif isinstance(backtrace, list):
            # Already List[FrameSummary]
            self.backtrace = backtrace
        else:
            # TracebackType object - extract frames
            self.backtrace = list(traceback.extract_tb(backtrace))

        super().__init__(f"[{code}] {message}")

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"

    def __repr__(self) -> str:
        timestamp_str = datetime.fromtimestamp(self.timestamp).isoformat()
        return f"{self.__class__.__name__}(code={self.code!r}, message={self.message!r}, timestamp={timestamp_str!r})"

    def to_dict(self) -> dict[str, Any]:
        """Serialize exception to dictionary for JSON responses."""
        return {
            "code": self.code,
            "message": self.message,
            "timestamp": self.timestamp,
            "backtrace": self.backtrace,
        }


class CommonException(TradingApiException):
    """Exception for infrastructure/shared/generic errors.

    Used for errors originating from:
    - Authentication middleware
    - Configuration issues
    - Shared utilities
    - Infrastructure components

    Error code convention: COMMON_{DOMAIN}_{ERROR_TYPE}
    Examples:
    - COMMON_AUTH_TOKEN_EXPIRED
    - COMMON_CONFIG_MISSING
    - COMMON_CAPABILITY_NOT_FOUND
    """


class ServiceException(TradingApiException):
    """Exception for service layer errors.

    Used for errors generated within module services (business logic).

    Attributes:
        module: Name of the module where error originated (e.g., "datafeed", "broker")

    Error code convention: SERVICE_{MODULE}_{ERROR_TYPE}
    Examples:
    - SERVICE_DATAFEED_INVALID_TOPIC
    - SERVICE_BROKER_ORDER_VALIDATION_FAILED
    - SERVICE_AUTH_USER_NOT_FOUND
    """

    def __init__(self, module: str, *args: Any, **kwargs: Any) -> None:
        self.module = module
        super().__init__(*args, **kwargs)

    def __repr__(self) -> str:
        timestamp_str = datetime.fromtimestamp(self.timestamp).isoformat()
        return (
            f"{self.__class__.__name__}(code={self.code!r}, message={self.message!r}"
            + f", module={self.module!r}, timestamp={timestamp_str!r})"
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize exception to dictionary for JSON responses."""
        base = super().to_dict()
        base["module"] = self.module
        return base


class DatastoreException(TradingApiException):
    """Exception for datastore layer errors.

    Used for errors originating from datastore operations:
    - Schema/constraint creation failures
    - Invalid configuration
    - Connection issues

    Attributes:
        datastore: Datastore type (e.g., "postgres", "duckdb")
        table: Table name where error occurred (optional)

    Error code convention: DATASTORE_{OPERATION}_{ERROR_TYPE}
    Examples:
    - DATASTORE_EXCLUSION_INVALID_COLUMN
    - DATASTORE_EXCLUSION_INVALID_BOUNDS
    - DATASTORE_EXTENSION_FAILED
    """

    def __init__(
        self,
        datastore: str,
        table: str | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        self.datastore = datastore
        self.table = table
        super().__init__(*args, **kwargs)

    def __repr__(self) -> str:
        timestamp_str = datetime.fromtimestamp(self.timestamp).isoformat()
        table_part = f", table={self.table!r}" if self.table else ""
        return (
            f"{self.__class__.__name__}(code={self.code!r}, message={self.message!r}"
            + f", datastore={self.datastore!r}{table_part}, timestamp={timestamp_str!r})"
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize exception to dictionary for JSON responses."""
        base = super().to_dict()
        base["datastore"] = self.datastore
        if self.table:
            base["table"] = self.table
        return base


class ProviderException(TradingApiException):
    """Exception for provider layer errors.

    Used for errors originating from external provider integrations.

    Attributes:
        provider: Provider name (e.g., "tws", "google")
        capability: Capability type (e.g., "datafeed", "auth")

    Error code convention: PROVIDER_{CAPABILITY}_{ERROR_TYPE}
    Examples:
    - PROVIDER_DATAFEED_CONNECTION_FAILED
    - PROVIDER_DATAFEED_SYMBOL_NOT_FOUND
    - PROVIDER_AUTH_TOKEN_INVALID
    """

    def __init__(
        self,
        provider: str,
        capability: str,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        self.provider = provider
        self.capability = capability
        super().__init__(*args, **kwargs)

    def __repr__(self) -> str:
        timestamp_str = datetime.fromtimestamp(self.timestamp).isoformat()
        return (
            f"{self.__class__.__name__}(code={self.code!r}, message={self.message!r}, "
            + f"provider={self.provider!r}, capability={self.capability!r}, timestamp={timestamp_str!r})"
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize exception to dictionary for JSON responses."""
        base = super().to_dict()
        base["provider"] = self.provider
        base["capability"] = self.capability
        return base


__all__ = [
    "TradingApiException",
    "CommonException",
    "DatastoreException",
    "ServiceException",
    "ProviderException",
]
