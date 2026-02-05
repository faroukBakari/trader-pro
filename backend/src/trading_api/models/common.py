"""
Base models and common utilities for the trading API.

This module contains shared base classes and utilities
that are used across multiple domains.

IMPORTANT: Models are pure data - no trading_api imports allowed.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Generic, Literal, Optional, Protocol, TypeVar

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class ExceptionLike(Protocol):
    """Protocol for exception-like objects with to_dict() method.

    Used by ErrorPayload.from_exception() to avoid circular imports.
    TradingApiException implements this protocol.
    """

    def to_dict(self) -> dict[str, Any]:
        ...


class BaseApiResponse(BaseModel):
    """Base response model with common fields."""

    success: bool = Field(..., description="Response success status")
    message: str = Field(..., description="Response message")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Response timestamp"
    )


class ErrorApiResponse(BaseModel):
    """Error response model"""

    error: str = Field(..., description="Error message")
    details: Optional[str] = Field(None, description="Error details")


class SubscriptionResponse(BaseModel):
    """Generic subscription response"""

    status: Literal["ok", "error"] = Field(..., description="Status")
    sub_id: str = Field(..., description="Request identifier")
    topic: str = Field(..., description="Subscription topic")
    error: Optional[str] = Field(default=None, description="Error details")


T = TypeVar("T", bound=BaseModel)


class SubscriptionRequest(BaseModel, Generic[T]):
    """Generic subscription update with typed payload"""

    sub_id: str = Field(..., description="Request identifier")
    sub_params: T = Field(..., description="Update payload")


class SubscriptionUpdate(BaseModel, Generic[T]):
    """Generic subscription update with typed payload"""

    topic: str = Field(..., description="Update type")
    payload: T = Field(..., description="Update payload")


class ErrorPayload(BaseModel):
    """Pydantic-serializable representation of TradingApiException.

    Bridges Python exceptions (Exception inheritance) and Pydantic models
    (BaseModel inheritance) - these are mutually exclusive hierarchies.

    Constructor accepts a TradingApiException directly and uses its
    existing to_dict() method for field extraction.

    Fields:
    - code, message, timestamp: Mandatory (from base TradingApiException)
    - details: Optional dict for extra metadata (module, provider, capability)
    - backtrace: Intentionally omitted (backend-only concern)
    """

    code: str = Field(..., description="Error code (e.g., PROVIDER_TIMEOUT)")
    message: str = Field(..., description="Human-readable error description")
    timestamp: float = Field(..., description="Unix timestamp when error occurred")
    details: dict[str, Any] | None = Field(
        default=None,
        description="Additional error context (module, provider, capability, etc.)",
    )

    @classmethod
    def from_exception(cls, exc: ExceptionLike) -> "ErrorPayload":
        """Construct ErrorPayload from a TradingApiException.

        Args:
            exc: Exception with to_dict() method (TradingApiException implements ExceptionLike)

        Returns:
            ErrorPayload instance with exception data
        """
        exc_dict = exc.to_dict()

        code = exc_dict.pop("code")
        message = exc_dict.pop("message")
        timestamp = exc_dict.pop("timestamp")
        exc_dict.pop("backtrace", None)  # Remove backend-only field

        details = exc_dict if exc_dict else None

        return cls(
            code=code,
            message=message,
            timestamp=timestamp,
            details=details,
        )


class SubscriptionError(BaseModel):
    """Error notification for an active subscription.

    Sent when a subscription encounters an error but connection remains open.
    Client can decide to unsubscribe, retry, or wait for recovery.

    Part of the WebSocket pub/sub protocol:
    - {route}.subscribe → {route}.subscribe.response
    - {route}.unsubscribe → {route}.unsubscribe.response
    - {route}.update (data)
    - {route}.error (this message type)
    """

    topic: str = Field(..., description="Affected subscription topic")
    error: ErrorPayload = Field(..., description="Serialized exception details")
    recoverable: bool = Field(
        default=True,
        description="If True, client should expect automatic recovery",
    )
    retry_after_ms: int | None = Field(
        default=None,
        description="Suggested retry delay in milliseconds",
    )


__all__ = [
    "BaseApiResponse",
    "ErrorApiResponse",
    "ErrorPayload",
    "SubscriptionError",
    "SubscriptionResponse",
    "SubscriptionUpdate",
    "ProviderCapabilityName",
    "ProviderCapabilitySpec",
    "ProviderConfig",
]


# ==============================================================================
# Provider/Capability System Models
# ==============================================================================

# Capability name for auth, broker, datafeed
ProviderCapabilityName = Literal["auth", "broker", "datafeed"]


@dataclass(frozen=True)
class ProviderCapabilitySpec:
    """Type-safe provider capability specification.

    Used by both services (to declare requirements) and providers
    (to declare what they provide).

    [IMMUTABLE]: Frozen dataclass ensures specs cannot be mutated after creation.
    """

    name: ProviderCapabilityName
    version: str | None = None  # None = any version

    def matches(self, provider_capability: "ProviderCapabilitySpec") -> bool:
        """Check if provider capability satisfies this requirement.

        Args:
            provider_capability: Capability offered by provider

        Returns:
            True if provider can satisfy this requirement

        Examples:
            >>> # Service requires auth (any version)
            >>> req = ProviderCapabilitySpec(name="auth")
            >>> prov = ProviderCapabilitySpec(name="auth", version="v1")
            >>> req.matches(prov)  # True

            >>> # Service requires specific version
            >>> req = ProviderCapabilitySpec(name="auth", version="v1")
            >>> prov = ProviderCapabilitySpec(name="auth", version="v2")
            >>> req.matches(prov)  # False
        """
        # Name must match exactly
        if self.name != provider_capability.name:
            return False

        # If no version specified, accept any provider version
        if self.version is None:
            return True

        # If version specified, must match exactly
        return provider_capability.version == self.version

    def __str__(self) -> str:
        """String representation for logging."""
        return f"{self.name}:{self.version}" if self.version else self.name


# Backward compatibility alias (deprecated)
CapabilitySpec = ProviderCapabilitySpec


# ==============================================================================
# Datastore Capability System Models
# ==============================================================================

# Capability names for datastores
DatastoreCapabilityName = Literal[
    "persistence",  # Data survives process restarts
    "transactions",  # ACID transaction support
    "timeseries",  # Time-range queries and batch operations
    "rangequery",  # Gap detection via multirange operations
    "exclusion",  # Range exclusion constraints
]


@dataclass(frozen=True)
class DatastoreCapabilitySpec:
    """Type-safe datastore capability specification.

    Used by services (to declare requirements) and datastores
    (to declare what they provide).

    [IMMUTABLE]: Frozen dataclass ensures specs cannot be mutated after creation.
    """

    name: DatastoreCapabilityName
    optional: bool = False  # True = prefer if available, False = fail if missing

    def matches(self, provided_capability: "DatastoreCapabilitySpec") -> bool:
        """Check if provided capability satisfies this requirement.

        Args:
            provided_capability: Capability offered by datastore

        Returns:
            True if datastore can satisfy this requirement
        """
        return self.name == provided_capability.name

    def __str__(self) -> str:
        """String representation for logging."""
        suffix = " (optional)" if self.optional else ""
        return f"{self.name}{suffix}"


class ProviderConfig(BaseSettings):
    """Base configuration for all providers.

    [EXTENSIBLE]: Each provider subclasses to add specific config fields.
    """

    enabled: bool = True
