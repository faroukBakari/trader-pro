"""
Auth API endpoints for authentication and authorization.

This module provides REST API endpoints for:
- Google OAuth login
- Token refresh
- Logout
- User info retrieval
"""

from typing import Annotated, Any, cast

from fastapi import Depends, HTTPException

from trading_api.models.auth import (
    DeviceInfo,
    GoogleLoginRequest,
    LogoutRequest,
    RefreshRequest,
    TokenResponse,
    User,
)
from trading_api.shared.api import APIRouterInterface
from trading_api.shared.middleware.auth import get_current_user

from ..service import AuthService


class AuthApi(APIRouterInterface):
    """Auth API implementation"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        @self.post(
            "/login",
            response_model=TokenResponse,
            summary="Authenticate with Google OAuth",
            operation_id="login",
        )
        async def login(
            request: GoogleLoginRequest,
        ) -> TokenResponse:
            """
            Authenticate user with Google ID token.

            Verifies the Google ID token, creates or updates user,
            and returns access token + refresh token.

            Args:
                request: Login request containing Google ID token

            Returns:
                TokenResponse: Access token, refresh token, and metadata
            """
            # Get device info from request context
            # Note: In production, this should be extracted from actual request
            device_info = DeviceInfo(
                ip_address="unknown",
                user_agent="unknown",
                fingerprint="unknown",
            )

            auth_service = cast(AuthService, self.service)

            try:
                return await auth_service.authenticate_google_user(
                    request.google_token, device_info
                )
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.post(
            "/refresh-token",
            response_model=TokenResponse,
            summary="Refresh access token",
            operation_id="refreshToken",
        )
        async def refresh_token(
            request: RefreshRequest,
        ) -> TokenResponse:
            """
            Refresh access token using refresh token.

            Implements token rotation: issues new tokens and revokes old refresh token.

            Args:
                request: Refresh request containing refresh token

            Returns:
                TokenResponse: New access token and refresh token
            """
            # Get device info from request context
            device_info = DeviceInfo(
                ip_address="unknown",
                user_agent="unknown",
                fingerprint="unknown",
            )

            auth_service = cast(AuthService, self.service)

            try:
                return await auth_service.refresh_access_token(
                    request.refresh_token, device_info
                )
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.post(
            "/logout",
            response_model=dict[str, str],
            summary="Logout (revoke refresh token)",
            operation_id="logout",
        )
        async def logout(
            request: LogoutRequest,
        ) -> dict[str, str]:
            """
            Logout by revoking refresh token.

            Args:
                request: Logout request containing refresh token

            Returns:
                Success message
            """
            auth_service = cast(AuthService, self.service)

            try:
                await auth_service.logout(request.refresh_token)
                return {"message": "Logged out successfully"}
            except Exception:
                # Silent failure - logout always succeeds
                return {"message": "Logged out successfully"}

        @self.get(
            "/me",
            response_model=User,
            summary="Get current user info",
            operation_id="getCurrentUser",
        )
        async def get_me(
            user_data: Annotated[dict[str, str], Depends(get_current_user)],
        ) -> User:
            """
            Get current authenticated user information.

            Requires valid JWT token in Authorization header.

            Args:
                user_data: User data from JWT token (injected by middleware)

            Returns:
                User: Current user information
            """
            user_id = user_data["user_id"]

            auth_service = cast(AuthService, self.service)

            try:
                user = await auth_service.user_repository.get_by_id(user_id)
                if user is None:
                    raise HTTPException(status_code=404, detail="User not found")
                return user
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))


__all__ = ["AuthApi"]
