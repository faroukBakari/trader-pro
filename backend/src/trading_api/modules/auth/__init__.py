"""Auth module - Authentication and authorization.

Provides JWT-based authentication with Google OAuth integration,
token refresh, and device fingerprinting.
"""

from pathlib import Path

from trading_api.shared import Module


class AuthModule(Module):
    """Auth module implementation.

    Implements the Module Protocol for authentication functionality.
    Provides Google OAuth integration, JWT token management,
    and refresh token rotation with device fingerprinting.

    Attributes:
        _service: AuthService instance
        _api_routers: List of FastAPI routers
    """

    @property
    def module_dir(self) -> Path:
        """Return the directory path for this module.

        Returns:
            Path: Module directory path
        """
        return Path(__file__).parent

    @property
    def tags(self) -> list[dict[str, str]]:
        """Get OpenAPI tags for auth module.

        Returns:
            list[dict[str, str]]: OpenAPI tags describing auth operations
        """
        return [
            {
                "name": "auth",
                "description": "Authentication operations (login, logout, token refresh)",
            }
        ]


__all__ = ["AuthModule"]
