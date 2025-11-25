"""
Base models and common utilities for the trading API.

This module contains shared base classes and utilities
that are used across multiple domains.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Generic, Literal, Optional, TypeVar

from pydantic import BaseModel, Field


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
    message: str = Field(..., description="Status message")
    topic: str = Field(..., description="Subscription topic")


T = TypeVar("T", bound=BaseModel)


class SubscriptionUpdate(BaseModel, Generic[T]):
    """Generic subscription update with typed payload"""

    topic: str = Field(..., description="Update type")
    payload: T = Field(..., description="Update payload")


__all__ = [
    "BaseApiResponse",
    "ErrorApiResponse",
    "SubscriptionResponse",
    "SubscriptionUpdate",
    "CapabilityName",
    "CapabilitySpec",
    "ProviderConfig",
    "ProviderError",
    "AuthenticationError",
    "ProviderNotFoundError",
    "CapabilityNotFoundError",
    "DatafeedError",
]


# ==============================================================================
# Provider/Capability System Models
# ==============================================================================

# Capability name for auth, datafeed (future: "broker", etc.)
CapabilityName = Literal["auth", "datafeed"]


@dataclass(frozen=True)
class CapabilitySpec:
    """Type-safe capability specification.

    Used by both services (to declare requirements) and providers
    (to declare what they provide).

    [IMMUTABLE]: Frozen dataclass ensures specs cannot be mutated after creation.
    """

    name: CapabilityName
    version: str | None = None  # None = any version

    def matches(self, provider_capability: "CapabilitySpec") -> bool:
        """Check if provider capability satisfies this requirement.

        Args:
            provider_capability: Capability offered by provider

        Returns:
            True if provider can satisfy this requirement

        Examples:
            >>> # Service requires auth (any version)
            >>> req = CapabilitySpec(name="auth")
            >>> prov = CapabilitySpec(name="auth", version="v1")
            >>> req.matches(prov)  # True

            >>> # Service requires specific version
            >>> req = CapabilitySpec(name="auth", version="v1")
            >>> prov = CapabilitySpec(name="auth", version="v2")
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


class ProviderConfig(BaseModel):
    """Base configuration for all providers.

    [EXTENSIBLE]: Each provider subclasses to add specific config fields.
    """

    enabled: bool = True


# Provider-specific exceptions
class ProviderError(Exception):
    """Base exception for all provider errors."""


class AuthenticationError(ProviderError):
    """Authentication verification failed."""


class ProviderNotFoundError(ProviderError):
    """Required provider not found."""


class CapabilityNotFoundError(ProviderError):
    """Required capability not satisfied by any provider."""


class DatafeedError(ProviderError):
    """Datafeed operation failed.

    Raised by datafeed providers when:
    - Symbol search fails
    - Symbol not found
    - Historical data request fails
    - Subscription fails
    - Invalid parameters
    """
