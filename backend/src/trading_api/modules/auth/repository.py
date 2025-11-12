from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from trading_api.models.auth import DeviceInfo, User, UserCreate


class UserRepositoryInterface(ABC):
    """Abstract interface for user repository operations"""

    @abstractmethod
    async def get_by_id(self, user_id: str) -> Optional[User]:
        """Retrieve user by ID"""

    @abstractmethod
    async def get_by_email(self, email: str) -> Optional[User]:
        """Retrieve user by email address"""

    @abstractmethod
    async def get_by_google_id(self, google_id: str) -> Optional[User]:
        """Retrieve user by Google ID"""

    @abstractmethod
    async def create(self, user_data: UserCreate) -> User:
        """Create a new user"""

    @abstractmethod
    async def update_last_login(self, user_id: str) -> None:
        """Update user's last login timestamp"""


class RefreshTokenRepositoryInterface(ABC):
    """Abstract interface for refresh token repository operations"""

    @abstractmethod
    async def store_token(
        self,
        token_id: str,
        user_id: str,
        token_hash: str,
        device_info: DeviceInfo,
        created_at: datetime,
    ) -> None:
        """Store a refresh token with device information"""

    @abstractmethod
    async def get_token(
        self, token_hash: str, fingerprint: str
    ) -> Optional[dict[str, str]]:
        """
        Retrieve token data by hash and validate device fingerprint.
        Returns dict with token_id, user_id if valid, None otherwise.
        """

    @abstractmethod
    async def revoke_token(self, token_hash: str) -> None:
        """Revoke a specific refresh token"""

    @abstractmethod
    async def revoke_all_user_tokens(self, user_id: str) -> None:
        """Revoke all refresh tokens for a user"""
