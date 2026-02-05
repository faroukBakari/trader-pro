from datetime import datetime

import pytest

from trading_api.datastores import InMemoryDatastore
from trading_api.modules.auth.repository import RefreshTokenRepository, UserRepository
from trading_api.modules.auth.tests.conftest import DeviceInfoFactory, UserCreateFactory


class TestUserRepository:
    """Test suite for UserRepository implementation"""

    @pytest.fixture
    def repository(self) -> UserRepository:
        """Fixture providing repository instance with indexes configured at construction."""
        from trading_api.modules.auth.repository import UserRepository

        return UserRepository(datastore=InMemoryDatastore())

    @pytest.mark.asyncio
    async def test_create_user(self, repository: UserRepository) -> None:
        """Test creating a new user"""
        user_data = UserCreateFactory.build()
        user = await repository.create(user_data)

        assert user.id is not None
        assert user.email == user_data.email
        assert user.google_id == user_data.google_id
        assert user.full_name == user_data.full_name
        assert user.picture == user_data.picture
        assert user.is_active is True
        assert isinstance(user.created_at, datetime)
        assert isinstance(user.last_login, datetime)

    @pytest.mark.asyncio
    async def test_get_by_id_existing_user(self, repository: UserRepository) -> None:
        """Test retrieving an existing user by ID"""
        user_data = UserCreateFactory.build()
        created_user = await repository.create(user_data)

        retrieved_user = await repository.get_by_id(created_user.id)

        assert retrieved_user is not None
        assert retrieved_user.id == created_user.id
        assert retrieved_user.email == created_user.email
        assert retrieved_user.google_id == created_user.google_id

    @pytest.mark.asyncio
    async def test_get_by_id_nonexistent_user(self, repository: UserRepository) -> None:
        """Test retrieving a non-existent user by ID returns None"""
        user = await repository.get_by_id("USER-999999")

        assert user is None

    @pytest.mark.asyncio
    async def test_get_by_email_existing_user(self, repository: UserRepository) -> None:
        """Test retrieving an existing user by email"""
        user_data = UserCreateFactory.build()
        created_user = await repository.create(user_data)

        retrieved_user = await repository.get_by_email(created_user.email)

        assert retrieved_user is not None
        assert retrieved_user.email == created_user.email
        assert retrieved_user.id == created_user.id

    @pytest.mark.asyncio
    async def test_get_by_email_nonexistent_user(
        self, repository: UserRepository
    ) -> None:
        """Test retrieving a non-existent user by email returns None"""
        user = await repository.get_by_email("nonexistent@example.com")

        assert user is None

    @pytest.mark.asyncio
    async def test_get_by_google_id_existing_user(
        self, repository: UserRepository
    ) -> None:
        """Test retrieving an existing user by Google ID"""
        user_data = UserCreateFactory.build()
        created_user = await repository.create(user_data)

        retrieved_user = await repository.get_by_google_id(created_user.google_id)

        assert retrieved_user is not None
        assert retrieved_user.google_id == created_user.google_id
        assert retrieved_user.id == created_user.id

    @pytest.mark.asyncio
    async def test_get_by_google_id_nonexistent_user(
        self, repository: UserRepository
    ) -> None:
        """Test retrieving a non-existent user by Google ID returns None"""
        user = await repository.get_by_google_id("google-id-999999")

        assert user is None

    @pytest.mark.asyncio
    async def test_update_last_login(self, repository: UserRepository) -> None:
        """Test updating user's last login timestamp"""
        user_data = UserCreateFactory.build()
        created_user = await repository.create(user_data)
        original_last_login = created_user.last_login

        await repository.update_last_login(created_user.id)

        updated_user = await repository.get_by_id(created_user.id)
        assert updated_user is not None
        assert updated_user.last_login > original_last_login

    @pytest.mark.asyncio
    async def test_user_id_generation_unique(self, repository: UserRepository) -> None:
        """Test that user IDs are unique (UUID-based)"""
        user1_data = UserCreateFactory.build()
        user2_data = UserCreateFactory.build()

        user1 = await repository.create(user1_data)
        user2 = await repository.create(user2_data)

        assert user1.id.startswith("USER-")
        assert user2.id.startswith("USER-")
        assert user1.id != user2.id
        # UUID-based IDs are 12 hex chars after "USER-"
        assert len(user1.id) == 17  # "USER-" + 12 chars

    @pytest.mark.asyncio
    async def test_create_user_with_duplicate_email_raises(
        self, repository: UserRepository
    ) -> None:
        """Test creating users with duplicate email raises ValueError (unique constraint)"""
        email = "duplicate@example.com"
        user1_data = UserCreateFactory.build(email=email)
        user2_data = UserCreateFactory.build(
            email=email, google_id="different-google-id"
        )

        await repository.create(user1_data)

        with pytest.raises(ValueError, match="Duplicate value.*email"):
            await repository.create(user2_data)

    @pytest.mark.asyncio
    async def test_create_user_with_duplicate_google_id_raises(
        self, repository: UserRepository
    ) -> None:
        """Test creating users with duplicate google_id raises ValueError (unique constraint)"""
        google_id = "same-google-id"
        user1_data = UserCreateFactory.build(google_id=google_id)
        user2_data = UserCreateFactory.build(
            email="different@example.com", google_id=google_id
        )

        await repository.create(user1_data)

        with pytest.raises(ValueError, match="Duplicate value.*google_id"):
            await repository.create(user2_data)

    @pytest.mark.asyncio
    async def test_secondary_indexes_consistency(
        self, repository: UserRepository
    ) -> None:
        """Test that secondary indexes remain consistent"""
        user_data = UserCreateFactory.build()
        created_user = await repository.create(user_data)

        by_id = await repository.get_by_id(created_user.id)
        by_email = await repository.get_by_email(created_user.email)
        by_google_id = await repository.get_by_google_id(created_user.google_id)

        assert by_id is not None
        assert by_email is not None
        assert by_google_id is not None
        assert by_id.id == by_email.id == by_google_id.id


class TestRefreshTokenRepository:
    """Test suite for RefreshTokenRepository implementation"""

    @pytest.fixture
    def repository(self) -> RefreshTokenRepository:
        """Fixture providing repository instance with indexes configured at construction."""
        from trading_api.modules.auth.repository import RefreshTokenRepository

        return RefreshTokenRepository(datastore=InMemoryDatastore())

    @pytest.mark.asyncio
    async def test_store_token(self, repository: RefreshTokenRepository) -> None:
        """Test storing a refresh token"""
        device_info = DeviceInfoFactory.build()
        token_id = "TOKEN-1"
        user_id = "USER-1"
        token_hash = "hashed_token_value"
        created_at = datetime.now()

        await repository.store_token(
            token_id=token_id,
            user_id=user_id,
            token_hash=token_hash,
            device_info=device_info,
            created_at=created_at,
        )

        result = await repository.get_token(token_hash, device_info.fingerprint)
        assert result is not None
        assert result["token_id"] == token_id
        assert result["user_id"] == user_id

    @pytest.mark.asyncio
    async def test_get_token_nonexistent(
        self, repository: RefreshTokenRepository
    ) -> None:
        """Test getting a non-existent token returns None"""
        result = await repository.get_token("nonexistent_hash", "any_fingerprint")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_token_wrong_fingerprint(
        self, repository: RefreshTokenRepository
    ) -> None:
        """Test getting token with wrong device fingerprint returns None"""
        device_info = DeviceInfoFactory.build()
        token_id = "TOKEN-1"
        user_id = "USER-1"
        token_hash = "hashed_token_value"
        created_at = datetime.now()

        await repository.store_token(
            token_id=token_id,
            user_id=user_id,
            token_hash=token_hash,
            device_info=device_info,
            created_at=created_at,
        )

        wrong_fingerprint = "wrong_fingerprint_hash"
        result = await repository.get_token(token_hash, wrong_fingerprint)
        assert result is None

    @pytest.mark.asyncio
    async def test_revoke_token(self, repository: RefreshTokenRepository) -> None:
        """Test revoking a specific refresh token"""
        device_info = DeviceInfoFactory.build()
        token_id = "TOKEN-1"
        user_id = "USER-1"
        token_hash = "hashed_token_value"
        created_at = datetime.now()

        await repository.store_token(
            token_id=token_id,
            user_id=user_id,
            token_hash=token_hash,
            device_info=device_info,
            created_at=created_at,
        )

        await repository.revoke_token(token_hash)

        result = await repository.get_token(token_hash, device_info.fingerprint)
        assert result is None

    @pytest.mark.asyncio
    async def test_revoke_all_user_tokens(
        self, repository: RefreshTokenRepository
    ) -> None:
        """Test revoking all tokens for a specific user"""
        user_id = "USER-1"
        device_info1 = DeviceInfoFactory.build()
        device_info2 = DeviceInfoFactory.build()

        token_hash1 = "hashed_token_1"
        token_hash2 = "hashed_token_2"

        await repository.store_token(
            token_id="TOKEN-1",
            user_id=user_id,
            token_hash=token_hash1,
            device_info=device_info1,
            created_at=datetime.now(),
        )
        await repository.store_token(
            token_id="TOKEN-2",
            user_id=user_id,
            token_hash=token_hash2,
            device_info=device_info2,
            created_at=datetime.now(),
        )

        await repository.revoke_all_user_tokens(user_id)

        result1 = await repository.get_token(token_hash1, device_info1.fingerprint)
        result2 = await repository.get_token(token_hash2, device_info2.fingerprint)
        assert result1 is None
        assert result2 is None

    @pytest.mark.asyncio
    async def test_revoke_all_user_tokens_leaves_other_users(
        self, repository: RefreshTokenRepository
    ) -> None:
        """Test that revoking all tokens for one user doesn't affect other users"""
        user1_id = "USER-1"
        user2_id = "USER-2"
        device_info1 = DeviceInfoFactory.build()
        device_info2 = DeviceInfoFactory.build()

        token_hash1 = "hashed_token_1"
        token_hash2 = "hashed_token_2"

        await repository.store_token(
            token_id="TOKEN-1",
            user_id=user1_id,
            token_hash=token_hash1,
            device_info=device_info1,
            created_at=datetime.now(),
        )
        await repository.store_token(
            token_id="TOKEN-2",
            user_id=user2_id,
            token_hash=token_hash2,
            device_info=device_info2,
            created_at=datetime.now(),
        )

        await repository.revoke_all_user_tokens(user1_id)

        result1 = await repository.get_token(token_hash1, device_info1.fingerprint)
        result2 = await repository.get_token(token_hash2, device_info2.fingerprint)
        assert result1 is None
        assert result2 is not None
        assert result2["user_id"] == user2_id

    @pytest.mark.asyncio
    async def test_multiple_tokens_per_user(
        self, repository: RefreshTokenRepository
    ) -> None:
        """Test storing multiple tokens for same user (different devices)"""
        user_id = "USER-1"
        device_info1 = DeviceInfoFactory.build()
        device_info2 = DeviceInfoFactory.build()

        token_hash1 = "hashed_token_1"
        token_hash2 = "hashed_token_2"

        await repository.store_token(
            token_id="TOKEN-1",
            user_id=user_id,
            token_hash=token_hash1,
            device_info=device_info1,
            created_at=datetime.now(),
        )
        await repository.store_token(
            token_id="TOKEN-2",
            user_id=user_id,
            token_hash=token_hash2,
            device_info=device_info2,
            created_at=datetime.now(),
        )

        result1 = await repository.get_token(token_hash1, device_info1.fingerprint)
        result2 = await repository.get_token(token_hash2, device_info2.fingerprint)

        assert result1 is not None
        assert result2 is not None
        assert result1["user_id"] == user_id
        assert result2["user_id"] == user_id
        assert result1["token_id"] != result2["token_id"]

    @pytest.mark.asyncio
    async def test_token_rotation_scenario(
        self, repository: RefreshTokenRepository
    ) -> None:
        """Test token rotation: store new token, verify it works, revoke old token"""
        user_id = "USER-1"
        device_info = DeviceInfoFactory.build()

        old_token_hash = "old_hashed_token"
        new_token_hash = "new_hashed_token"

        await repository.store_token(
            token_id="TOKEN-1",
            user_id=user_id,
            token_hash=old_token_hash,
            device_info=device_info,
            created_at=datetime.now(),
        )

        await repository.store_token(
            token_id="TOKEN-2",
            user_id=user_id,
            token_hash=new_token_hash,
            device_info=device_info,
            created_at=datetime.now(),
        )

        new_result = await repository.get_token(new_token_hash, device_info.fingerprint)
        assert new_result is not None

        await repository.revoke_token(old_token_hash)

        old_result = await repository.get_token(old_token_hash, device_info.fingerprint)
        assert old_result is None

        new_result_after = await repository.get_token(
            new_token_hash, device_info.fingerprint
        )
        assert new_result_after is not None
