"""Auth module repositories using DatastoreInterface abstraction.

[ARCHITECTURE] Wave 2B: SQLModel integration
- PostgresDatastore: Uses sqlmodel_table() for typed column storage
- InMemoryDatastore: Falls back to table() with JSONB-like dict storage
"""

import uuid
from datetime import datetime, timezone
from typing import Any, TypeVar

from pydantic import BaseModel

from trading_api.models.auth import DeviceInfo, RefreshTokenData, User, UserCreate
from trading_api.shared import DatastoreInterface, TableInterface

T = TypeVar("T", bound=BaseModel)


def _to_model(result: Any, model_class: type[T]) -> T | None:
    """Convert table result to Pydantic model.

    Handles both:
    - InMemoryDatastore: returns BaseModel directly
    - PostgresDatastore: returns dict (needs model_validate)

    Args:
        result: Value from table.get() - either BaseModel or dict
        model_class: Pydantic model class to convert to

    Returns:
        Model instance or None if result is None
    """
    if result is None:
        return None
    if isinstance(result, model_class):
        return result
    if isinstance(result, dict):
        return model_class.model_validate(result)
    return None


class UserRepository:
    """User repository using DatastoreInterface abstraction.

    [ARCHITECTURE] Wave 2B: Uses SQLModelTable when available
    - PostgresDatastore: sqlmodel_table() with typed columns
    - InMemoryDatastore: table() fallback with dict storage
    """

    TABLE_NAME = "users"

    def __init__(self, datastore: DatastoreInterface) -> None:
        # Use SQLModel table for typed storage (Wave 2B)
        if datastore.is_relational:
            # PostgresDatastore has sqlmodel_table() for typed columns
            self._table: TableInterface[Any] = datastore.sqlmodel_table(
                User, primary_key="id"
            )
        else:
            # Fallback for InMemory/other datastores
            self._table = datastore.table(
                self.TABLE_NAME,
                unique_indexes=["email", "google_id"],
            )

    async def get_by_id(self, user_id: str) -> User | None:
        """Retrieve user by ID"""
        result = await self._table.get(user_id)
        return _to_model(result, User)

    async def get_by_email(self, email: str) -> User | None:
        """Retrieve user by email address"""
        result = await self._table.get(email, index="email")
        return _to_model(result, User)

    async def get_by_google_id(self, google_id: str) -> User | None:
        """Retrieve user by Google ID"""
        result = await self._table.get(google_id, index="google_id")
        return _to_model(result, User)

    async def create(self, user_data: UserCreate) -> User:
        """Create a new user.

        Raises:
            ValueError: If email or google_id already exists (unique constraint)
        """
        user_id = f"USER-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)

        user = User(
            id=user_id,
            email=user_data.email,
            google_id=user_data.google_id,
            full_name=user_data.full_name,
            picture=user_data.picture,
            created_at=now,
            last_login=now,
            is_active=True,
        )

        await self._table.set(user_id, user)
        return user

    async def update_last_login(self, user_id: str) -> None:
        """Update user's last login timestamp"""
        user = await self.get_by_id(user_id)
        if user is not None:
            updated_user = user.model_copy(
                update={"last_login": datetime.now(timezone.utc)}
            )
            await self._table.set(user_id, updated_user)


class RefreshTokenRepository:
    """Refresh token repository using DatastoreInterface abstraction.

    [ARCHITECTURE] Wave 2B: Uses SQLModelTable when available
    - PostgresDatastore: sqlmodel_table() with typed columns
    - InMemoryDatastore: table() fallback with dict storage
    """

    TABLE_NAME = "refresh_tokens"

    def __init__(self, datastore: DatastoreInterface) -> None:
        # Use SQLModel table for typed storage (Wave 2B)
        if datastore.is_relational:
            # PostgresDatastore has sqlmodel_table() for typed columns
            self._table: TableInterface[Any] = datastore.sqlmodel_table(
                RefreshTokenData, primary_key="token_hash"
            )
        else:
            # Fallback for InMemory/other datastores
            self._table = datastore.table(
                self.TABLE_NAME,
                indexes=["user_id"],  # 1:N - user can have multiple tokens
            )

    async def store_token(
        self,
        token_id: str,
        user_id: str,
        token_hash: str,
        device_info: DeviceInfo,
        created_at: datetime,
    ) -> None:
        """Store a refresh token with device information"""
        token_data = RefreshTokenData(
            token_id=token_id,
            user_id=user_id,
            token_hash=token_hash,
            fingerprint=device_info.fingerprint,
            ip_address=device_info.ip_address,
            user_agent=device_info.user_agent,
            created_at=created_at,
        )
        await self._table.set(token_hash, token_data)

    async def get_token(
        self, token_hash: str, fingerprint: str
    ) -> dict[str, str] | None:
        """
        Retrieve token data by hash and validate device fingerprint.
        Returns dict with token_id, user_id if valid, None otherwise.
        """
        result = await self._table.get(token_hash)
        token_data = _to_model(result, RefreshTokenData)
        if token_data is None:
            return None

        if token_data.fingerprint != fingerprint:
            return None

        return {
            "token_id": token_data.token_id,
            "user_id": token_data.user_id,
        }

    async def revoke_token(self, token_hash: str) -> None:
        """Revoke a specific refresh token"""
        await self._table.delete(token_hash)

    async def revoke_all_user_tokens(self, user_id: str) -> None:
        """Revoke all refresh tokens for a user"""
        results = await self._table.get_all(user_id, index="user_id")
        for result in results:
            token = _to_model(result, RefreshTokenData)
            if token is not None:
                await self._table.delete(token.token_hash)
