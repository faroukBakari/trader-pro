"""Authentication capability interface."""

from abc import ABC, abstractmethod
from typing import Any


class AuthCapability(ABC):
    """Authentication capability interface.

    Providers implementing this capability can verify authentication tokens
    and return user claims.

    [STATELESS]: Implementations must be stateless (no request state).
    """

    @abstractmethod
    async def verify_token(self, token: str) -> dict[str, Any]:
        """Verify authentication token and return user claims.

        Args:
            token: Provider-specific token (ID token, OAuth token, API key, etc.)

        Returns:
            dict with standardized user claims:
                - sub: Subject (user ID)
                - email: User email
                - name: Full name (optional)
                - picture: Profile picture URL (optional)
                - email_verified: Email verification status

        Raises:
            ProviderException: If token invalid or verification fails

        [SECURITY]: Must validate token signature, audience, expiration.
        """
        ...
