"""Google OAuth authentication provider."""

from pathlib import Path
from typing import Any

import httpx

from trading_api.capabilities.auth import AuthCapability
from trading_api.models.common import CapabilitySpec
from trading_api.models.exceptions import ProviderException
from trading_api.models.providers.google_oauth_configs import GoogleProviderConfig
from trading_api.shared import Provider


class GoogleProvider(Provider, AuthCapability):
    """Google OAuth authentication provider.

    Implements AuthCapability using Google's tokeninfo endpoint.
    """

    def __init__(self, config: GoogleProviderConfig | None = None) -> None:
        """Initialize Google provider.

        Args:
            config: Optional config for testing (None = load from env)
        """
        # BaseSettings auto-loads from environment when instantiated without args
        self._config = (
            config
            or GoogleProviderConfig()  # type: ignore[call-arg, unused-ignore] # pyright: ignore[reportCallIssue]
        )

    @classmethod
    def provider_dir(cls) -> Path:
        """Return provider directory."""
        return Path(__file__).parent

    @classmethod
    def capabilities(cls) -> list[CapabilitySpec]:
        """Capabilities provided."""
        return [CapabilitySpec(name="auth")]

    @property
    def config(self) -> GoogleProviderConfig:  # type: ignore[override]
        """Provider configuration."""
        return self._config

    async def verify_token(self, token: str) -> dict[str, Any]:
        """Verify Google ID token.

        [SECURITY]: Validates audience and email verification.
        """
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://www.googleapis.com/oauth2/v3/tokeninfo",
                params={"id_token": token},
            )

            if resp.status_code != 200:
                raise ProviderException(
                    code="PROVIDER_AUTH_TOKEN_INVALID",
                    message=f"Invalid Google token: {resp.text}",
                    provider="google",
                    capability="auth",
                )

            claims: dict[str, Any] = resp.json()

            # Validate audience
            if claims.get("aud") != self.config.client_id:
                raise ProviderException(
                    code="PROVIDER_AUTH_AUDIENCE_INVALID",
                    message="Invalid token audience",
                    provider="google",
                    capability="auth",
                )

            # Validate email verified
            if claims.get("email_verified") not in (True, "true"):
                raise ProviderException(
                    code="PROVIDER_AUTH_EMAIL_NOT_VERIFIED",
                    message="Email not verified",
                    provider="google",
                    capability="auth",
                )

            return claims


__all__ = ["GoogleProvider", "GoogleProviderConfig"]
