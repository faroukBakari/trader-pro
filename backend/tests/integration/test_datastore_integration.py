"""Datastore integration tests - validates both InMemory and Postgres implementations.

These tests run the same test cases against multiple datastore implementations
to ensure interface conformance and behavioral consistency.

Test organization:
- InMemory tests: Run always, no external dependencies
- PostgreSQL tests: Marked with @pytest.mark.postgres, require test_database fixture

PostgreSQL tests require the test_database fixture which:
- Creates an ephemeral trader_bars_test database
- Runs migrations automatically
- Cleans up after the test session

Run with:
- All tests: make -C backend test-integration
- InMemory only: pytest tests/integration/test_datastore_integration.py -v -m "not postgres"
- PostgreSQL only: pytest tests/integration/test_datastore_integration.py -v -m postgres
"""

from datetime import datetime, timezone
from typing import AsyncIterator

import pytest

from trading_api.datastores import InMemoryDatastore
from trading_api.modules.auth.repository import RefreshTokenRepository, UserRepository
from trading_api.modules.auth.tests.conftest import DeviceInfoFactory, UserCreateFactory
from trading_api.shared.config import Settings
from trading_api.shared.datastore_interface import DatastoreInterface


@pytest.fixture
async def inmemory_datastore() -> AsyncIterator[DatastoreInterface]:
    """InMemoryDatastore fixture - no external dependencies."""
    yield InMemoryDatastore()


@pytest.fixture
async def postgres_datastore(
    test_settings: Settings,
) -> AsyncIterator[DatastoreInterface]:
    """PostgresDatastore fixture with cleanup.

    Uses test_settings which has DATASTORE_POSTGRES_DSN configured.
    PostgresDatastore.create() auto-detects test mode and uses NullConnectionPool.
    """
    from trading_api.datastores import PostgresDatastore
    from trading_api.models.auth import RefreshTokenData, User

    # test_settings has DATASTORE_POSTGRES_DSN configured
    # create() uses config, validates DSN, auto-detects pytest for NullConnectionPool
    ds = await PostgresDatastore.create(config=test_settings)

    # Clear test tables before use (Wave 2B: unified table() API)
    users_table = ds.table(User)
    tokens_table = ds.table(RefreshTokenData)
    await users_table.clear()
    await tokens_table.clear()

    yield ds

    # Cleanup
    await users_table.clear()
    await tokens_table.clear()
    await ds.close()


@pytest.mark.integration
class TestUserRepositoryInMemory:
    """Test UserRepository with InMemoryDatastore."""

    @pytest.fixture
    def user_repository(self, inmemory_datastore: DatastoreInterface) -> UserRepository:
        """Create UserRepository with InMemoryDatastore."""
        return UserRepository(datastore=inmemory_datastore)

    @pytest.mark.asyncio
    async def test_create_user(self, user_repository: UserRepository) -> None:
        """Creating a user works with any datastore."""
        user_data = UserCreateFactory.build()
        user = await user_repository.create(user_data)

        assert user.id is not None
        assert user.email == user_data.email
        assert user.google_id == user_data.google_id

    @pytest.mark.asyncio
    async def test_get_by_id(self, user_repository: UserRepository) -> None:
        """Getting user by ID works with any datastore."""
        user_data = UserCreateFactory.build()
        created = await user_repository.create(user_data)

        retrieved = await user_repository.get_by_id(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.email == created.email

    @pytest.mark.asyncio
    async def test_get_by_email(self, user_repository: UserRepository) -> None:
        """Getting user by email works with any datastore."""
        user_data = UserCreateFactory.build()
        created = await user_repository.create(user_data)

        retrieved = await user_repository.get_by_email(created.email)

        assert retrieved is not None
        assert retrieved.email == created.email

    @pytest.mark.asyncio
    async def test_get_by_google_id(self, user_repository: UserRepository) -> None:
        """Getting user by google_id works with any datastore."""
        user_data = UserCreateFactory.build()
        created = await user_repository.create(user_data)

        retrieved = await user_repository.get_by_google_id(created.google_id)

        assert retrieved is not None
        assert retrieved.google_id == created.google_id

    @pytest.mark.asyncio
    async def test_update_last_login(self, user_repository: UserRepository) -> None:
        """Updating last login works with any datastore."""
        user_data = UserCreateFactory.build()
        created = await user_repository.create(user_data)
        original_login = created.last_login

        await user_repository.update_last_login(created.id)
        updated = await user_repository.get_by_id(created.id)

        assert updated is not None
        assert updated.last_login > original_login

    @pytest.mark.asyncio
    async def test_nonexistent_returns_none(
        self, user_repository: UserRepository
    ) -> None:
        """Getting nonexistent user returns None."""
        assert await user_repository.get_by_id("USER-999999") is None
        assert await user_repository.get_by_email("none@test.com") is None
        assert await user_repository.get_by_google_id("none") is None


@pytest.mark.integration
@pytest.mark.postgres
class TestUserRepositoryPostgres:
    """Test UserRepository with PostgresDatastore."""

    @pytest.fixture
    def user_repository(self, postgres_datastore: DatastoreInterface) -> UserRepository:
        """Create UserRepository with PostgresDatastore."""
        return UserRepository(datastore=postgres_datastore)

    @pytest.mark.asyncio
    async def test_create_user(self, user_repository: UserRepository) -> None:
        """Creating a user works with PostgresDatastore."""
        user_data = UserCreateFactory.build()
        user = await user_repository.create(user_data)

        assert user.id is not None
        assert user.email == user_data.email
        assert user.google_id == user_data.google_id

    @pytest.mark.asyncio
    async def test_get_by_id(self, user_repository: UserRepository) -> None:
        """Getting user by ID works with PostgresDatastore."""
        user_data = UserCreateFactory.build()
        created = await user_repository.create(user_data)

        retrieved = await user_repository.get_by_id(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.email == created.email

    @pytest.mark.asyncio
    async def test_get_by_email(self, user_repository: UserRepository) -> None:
        """Getting user by email works with PostgresDatastore."""
        user_data = UserCreateFactory.build()
        created = await user_repository.create(user_data)

        retrieved = await user_repository.get_by_email(created.email)

        assert retrieved is not None
        assert retrieved.email == created.email

    @pytest.mark.asyncio
    async def test_get_by_google_id(self, user_repository: UserRepository) -> None:
        """Getting user by google_id works with PostgresDatastore."""
        user_data = UserCreateFactory.build()
        created = await user_repository.create(user_data)

        retrieved = await user_repository.get_by_google_id(created.google_id)

        assert retrieved is not None
        assert retrieved.google_id == created.google_id

    @pytest.mark.asyncio
    async def test_update_last_login(self, user_repository: UserRepository) -> None:
        """Updating last login works with PostgresDatastore."""
        user_data = UserCreateFactory.build()
        created = await user_repository.create(user_data)
        original_login = created.last_login

        await user_repository.update_last_login(created.id)
        updated = await user_repository.get_by_id(created.id)

        assert updated is not None
        assert updated.last_login > original_login

    @pytest.mark.asyncio
    async def test_nonexistent_returns_none(
        self, user_repository: UserRepository
    ) -> None:
        """Getting nonexistent user returns None with PostgresDatastore."""
        assert await user_repository.get_by_id("USER-999999") is None
        assert await user_repository.get_by_email("none@test.com") is None
        assert await user_repository.get_by_google_id("none") is None


@pytest.mark.integration
class TestRefreshTokenRepositoryInMemory:
    """Test RefreshTokenRepository with InMemoryDatastore."""

    @pytest.fixture
    def token_repository(
        self, inmemory_datastore: DatastoreInterface
    ) -> RefreshTokenRepository:
        """Create RefreshTokenRepository with InMemoryDatastore."""
        return RefreshTokenRepository(datastore=inmemory_datastore)

    @pytest.mark.asyncio
    async def test_store_and_get_token(
        self, token_repository: RefreshTokenRepository
    ) -> None:
        """Storing and getting token works with any datastore."""
        device_info = DeviceInfoFactory.build()
        token_id = "TOKEN-1"
        user_id = "USER-1"
        token_hash = "test_hash_123"

        await token_repository.store_token(
            token_id=token_id,
            user_id=user_id,
            token_hash=token_hash,
            device_info=device_info,
            created_at=datetime.now(timezone.utc),
        )

        result = await token_repository.get_token(token_hash, device_info.fingerprint)

        assert result is not None
        assert result["token_id"] == token_id
        assert result["user_id"] == user_id

    @pytest.mark.asyncio
    async def test_revoke_token(self, token_repository: RefreshTokenRepository) -> None:
        """Revoking token works with any datastore."""
        device_info = DeviceInfoFactory.build()
        token_hash = "revoke_test_hash"

        await token_repository.store_token(
            token_id="TOKEN-R1",
            user_id="USER-R1",
            token_hash=token_hash,
            device_info=device_info,
            created_at=datetime.now(timezone.utc),
        )

        await token_repository.revoke_token(token_hash)
        result = await token_repository.get_token(token_hash, device_info.fingerprint)

        assert result is None

    @pytest.mark.asyncio
    async def test_revoke_all_user_tokens(
        self, token_repository: RefreshTokenRepository
    ) -> None:
        """Revoking all user tokens works."""
        user_id = "USER-MULTI"
        device1 = DeviceInfoFactory.build()
        device2 = DeviceInfoFactory.build()

        await token_repository.store_token(
            token_id="TOKEN-M1",
            user_id=user_id,
            token_hash="multi_hash_1",
            device_info=device1,
            created_at=datetime.now(timezone.utc),
        )
        await token_repository.store_token(
            token_id="TOKEN-M2",
            user_id=user_id,
            token_hash="multi_hash_2",
            device_info=device2,
            created_at=datetime.now(timezone.utc),
        )

        await token_repository.revoke_all_user_tokens(user_id)

        assert (
            await token_repository.get_token("multi_hash_1", device1.fingerprint)
            is None
        )
        assert (
            await token_repository.get_token("multi_hash_2", device2.fingerprint)
            is None
        )


@pytest.mark.integration
@pytest.mark.postgres
class TestRefreshTokenRepositoryPostgres:
    """Test RefreshTokenRepository with PostgresDatastore."""

    @pytest.fixture
    def token_repository(
        self, postgres_datastore: DatastoreInterface
    ) -> RefreshTokenRepository:
        """Create RefreshTokenRepository with PostgresDatastore."""
        return RefreshTokenRepository(datastore=postgres_datastore)

    @pytest.mark.asyncio
    async def test_store_and_get_token(
        self, token_repository: RefreshTokenRepository
    ) -> None:
        """Storing and getting token works with PostgresDatastore."""
        device_info = DeviceInfoFactory.build()
        token_id = "TOKEN-1"
        user_id = "USER-1"
        token_hash = "test_hash_123"

        await token_repository.store_token(
            token_id=token_id,
            user_id=user_id,
            token_hash=token_hash,
            device_info=device_info,
            created_at=datetime.now(timezone.utc),
        )

        result = await token_repository.get_token(token_hash, device_info.fingerprint)

        assert result is not None
        assert result["token_id"] == token_id
        assert result["user_id"] == user_id

    @pytest.mark.asyncio
    async def test_revoke_token(self, token_repository: RefreshTokenRepository) -> None:
        """Revoking token works with PostgresDatastore."""
        device_info = DeviceInfoFactory.build()
        token_hash = "revoke_test_hash"

        await token_repository.store_token(
            token_id="TOKEN-R1",
            user_id="USER-R1",
            token_hash=token_hash,
            device_info=device_info,
            created_at=datetime.now(timezone.utc),
        )

        await token_repository.revoke_token(token_hash)
        result = await token_repository.get_token(token_hash, device_info.fingerprint)

        assert result is None

    @pytest.mark.asyncio
    async def test_revoke_all_user_tokens(
        self, token_repository: RefreshTokenRepository
    ) -> None:
        """Revoking all user tokens works with PostgresDatastore."""
        user_id = "USER-MULTI"
        device1 = DeviceInfoFactory.build()
        device2 = DeviceInfoFactory.build()

        await token_repository.store_token(
            token_id="TOKEN-M1",
            user_id=user_id,
            token_hash="multi_hash_1",
            device_info=device1,
            created_at=datetime.now(timezone.utc),
        )
        await token_repository.store_token(
            token_id="TOKEN-M2",
            user_id=user_id,
            token_hash="multi_hash_2",
            device_info=device2,
            created_at=datetime.now(timezone.utc),
        )

        await token_repository.revoke_all_user_tokens(user_id)

        assert (
            await token_repository.get_token("multi_hash_1", device1.fingerprint)
            is None
        )
        assert (
            await token_repository.get_token("multi_hash_2", device2.fingerprint)
            is None
        )


@pytest.mark.integration
class TestDatastoreFeatureFlags:
    """Test datastore feature flags (has_persistence, has_transactions)."""

    @pytest.mark.asyncio
    async def test_inmemory_has_persistence_false(
        self, inmemory_datastore: DatastoreInterface
    ) -> None:
        """InMemoryDatastore.has_persistence is False."""
        assert inmemory_datastore.has_persistence is False

    @pytest.mark.asyncio
    async def test_inmemory_has_transactions_false(
        self, inmemory_datastore: DatastoreInterface
    ) -> None:
        """InMemoryDatastore.has_transactions is False."""
        assert inmemory_datastore.has_transactions is False

    @pytest.mark.asyncio
    @pytest.mark.postgres
    async def test_postgres_has_persistence_true(
        self, postgres_datastore: DatastoreInterface
    ) -> None:
        """PostgresDatastore.has_persistence is True."""
        assert postgres_datastore.has_persistence is True

    @pytest.mark.asyncio
    @pytest.mark.postgres
    async def test_postgres_has_transactions_true(
        self, postgres_datastore: DatastoreInterface
    ) -> None:
        """PostgresDatastore.has_transactions is True."""
        assert postgres_datastore.has_transactions is True
