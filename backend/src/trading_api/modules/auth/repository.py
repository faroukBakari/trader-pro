from datetime import datetime
from typing import Optional

from trading_api.models.auth import DeviceInfo, User, UserCreate
from trading_api.shared import DatastoreInterface, RWLock


class UserRepository:
    """In-memory implementation of user repository for MVP"""

    def __init__(self, datastore: DatastoreInterface) -> None:
        self._users: dict[str, User] = {}
        self._email_to_id: dict[str, str] = {}
        self._google_id_to_id: dict[str, str] = {}
        self._counter = 0
        # Use per-table RWLock from datastore if provided
        self._lock = datastore.table("users").lock

    async def get_by_id(self, user_id: str) -> Optional[User]:
        """Retrieve user by ID"""
        async with self._lock.read():
            return self._users.get(user_id)

    async def get_by_email(self, email: str) -> Optional[User]:
        """Retrieve user by email address"""
        async with self._lock.read():
            user_id = self._email_to_id.get(email)
            if user_id is None:
                return None
            return self._users.get(user_id)

    async def get_by_google_id(self, google_id: str) -> Optional[User]:
        """Retrieve user by Google ID"""
        async with self._lock.read():
            user_id = self._google_id_to_id.get(google_id)
            if user_id is None:
                return None
            return self._users.get(user_id)

    async def create(self, user_data: UserCreate) -> User:
        """Create a new user"""
        async with self._lock.write():
            self._counter += 1
            user_id = f"USER-{self._counter}"
            now = datetime.now()

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

            self._users[user_id] = user
            self._email_to_id[user_data.email] = user_id
            self._google_id_to_id[user_data.google_id] = user_id

            return user

    async def update_last_login(self, user_id: str) -> None:
        """Update user's last login timestamp"""
        async with self._lock.write():
            user = self._users.get(user_id)
            if user is not None:
                updated_user = user.model_copy(update={"last_login": datetime.now()})
                self._users[user_id] = updated_user


class RefreshTokenRepository:
    """In-memory implementation of refresh token repository for MVP"""

    def __init__(self, datastore: DatastoreInterface | None = None) -> None:
        self._tokens: dict[str, dict[str, str]] = {}
        self._user_to_tokens: dict[str, list[str]] = {}
        # Use per-table RWLock from datastore if provided
        self._lock = datastore.table("tokens").lock if datastore else RWLock()

    async def store_token(
        self,
        token_id: str,
        user_id: str,
        token_hash: str,
        device_info: DeviceInfo,
        created_at: datetime,
    ) -> None:
        """Store a refresh token with device information"""
        async with self._lock.write():
            self._tokens[token_hash] = {
                "token_id": token_id,
                "user_id": user_id,
                "fingerprint": device_info.fingerprint,
                "ip_address": device_info.ip_address,
                "user_agent": device_info.user_agent,
                "created_at": created_at.isoformat(),
            }

            if user_id not in self._user_to_tokens:
                self._user_to_tokens[user_id] = []
            self._user_to_tokens[user_id].append(token_hash)

    async def get_token(
        self, token_hash: str, fingerprint: str
    ) -> Optional[dict[str, str]]:
        """
        Retrieve token data by hash and validate device fingerprint.
        Returns dict with token_id, user_id if valid, None otherwise.
        """
        async with self._lock.read():
            token_data = self._tokens.get(token_hash)
            if token_data is None:
                return None

            if token_data["fingerprint"] != fingerprint:
                return None

            return {
                "token_id": token_data["token_id"],
                "user_id": token_data["user_id"],
            }

    async def revoke_token(self, token_hash: str) -> None:
        """Revoke a specific refresh token"""
        async with self._lock.write():
            token_data = self._tokens.get(token_hash)
            if token_data is not None:
                user_id = token_data["user_id"]
                del self._tokens[token_hash]

                if user_id in self._user_to_tokens:
                    self._user_to_tokens[user_id] = [
                        h for h in self._user_to_tokens[user_id] if h != token_hash
                    ]
                    if not self._user_to_tokens[user_id]:
                        del self._user_to_tokens[user_id]

    async def revoke_all_user_tokens(self, user_id: str) -> None:
        """Revoke all refresh tokens for a user"""
        async with self._lock.write():
            token_hashes = self._user_to_tokens.get(user_id, [])
            for token_hash in token_hashes:
                if token_hash in self._tokens:
                    del self._tokens[token_hash]

            if user_id in self._user_to_tokens:
                del self._user_to_tokens[user_id]
