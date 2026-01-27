"""Datastore integration tests - validates both InMemory and Postgres implementations.

These tests run the same test cases against multiple datastore implementations
to ensure interface conformance and behavioral consistency.

PostgreSQL tests require:
- PostgreSQL running (docker-compose.dev.yml or CI service)
- DATASTORE_POSTGRES_DSN or DATASTORE_POSTGRES_* env vars

Run with: make -C backend test-integration
Or: pytest tests/integration/test_datastore_integration.py -v
"""

import os
from datetime import datetime
from typing import AsyncIterator

import pytest

from trading_api.datastores import InMemoryDatastore
from trading_api.modules.auth.repository import RefreshTokenRepository, UserRepository
from trading_api.modules.auth.tests.conftest import DeviceInfoFactory, UserCreateFactory
from trading_api.shared.datastore_interface import DatastoreInterface

# Test DSN for PostgreSQL
TEST_DSN = os.environ.get(
    "DATASTORE_POSTGRES_DSN",
    "postgresql://trader:trader_dev@localhost:5433/trader_bars",
)


def postgres_available() -> bool:
    """Check if PostgreSQL is available for testing."""
    try:
        import socket

        # Parse DSN to get host and port
        # Format: postgresql://user:pass@host:port/db
        parts = TEST_DSN.split("@")[1].split("/")[0]
        host, port = parts.split(":")

        # Simple socket check for connectivity
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((host, int(port)))
        sock.close()
        return result == 0
    except Exception:
        return False


# Cache the result to avoid repeated checks
_POSTGRES_AVAILABLE = postgres_available()


# Mark to skip postgres tests if not available
skip_postgres = pytest.mark.skipif(
    not _POSTGRES_AVAILABLE,
    reason="PostgreSQL not available (start with: docker compose -f backend/docker-compose.dev.yml up -d)",
)


@pytest.fixture
async def inmemory_datastore() -> AsyncIterator[DatastoreInterface]:
    """InMemoryDatastore fixture."""
    yield InMemoryDatastore()


@pytest.fixture
async def postgres_datastore() -> AsyncIterator[DatastoreInterface]:
    """PostgresDatastore fixture with cleanup."""
    from trading_api.datastores import PostgresDatastore

    ds = await PostgresDatastore.create(dsn=TEST_DSN)
    yield ds
    await ds.close()


@pytest.fixture(params=["inmemory", "postgres"])
async def datastore(
    request: pytest.FixtureRequest,
) -> AsyncIterator[DatastoreInterface]:
    """Parametrized fixture providing both datastore implementations.

    This allows running the same tests against both InMemory and Postgres.
    """
    if request.param == "inmemory":
        yield InMemoryDatastore()
    else:
        if not _POSTGRES_AVAILABLE:
            pytest.skip("PostgreSQL not available")
        from trading_api.datastores import PostgresDatastore, PostgresTable

        ds = await PostgresDatastore.create(dsn=TEST_DSN)
        # Clear test tables before use
        users_table = ds.table("users", unique_indexes=["email", "google_id"])
        tokens_table = ds.table("refresh_tokens", indexes=["user_id"])
        # Cast to PostgresTable for _ensure_table access (internal method)
        assert isinstance(users_table, PostgresTable)
        assert isinstance(tokens_table, PostgresTable)
        await users_table._ensure_table()
        await tokens_table._ensure_table()
        await users_table.clear()
        await tokens_table.clear()
        yield ds
        # Cleanup
        await users_table.clear()
        await tokens_table.clear()
        await ds.close()


@pytest.mark.integration
class TestUserRepositoryDatastoreCompatibility:
    """Test UserRepository works identically with both datastores."""

    @pytest.fixture
    def user_repository(self, datastore: DatastoreInterface) -> UserRepository:
        """Create UserRepository with parametrized datastore."""
        return UserRepository(datastore=datastore)

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
        """Getting nonexistent user returns None with any datastore."""
        assert await user_repository.get_by_id("USER-999999") is None
        assert await user_repository.get_by_email("none@test.com") is None
        assert await user_repository.get_by_google_id("none") is None


@pytest.mark.integration
class TestRefreshTokenRepositoryDatastoreCompatibility:
    """Test RefreshTokenRepository works identically with both datastores."""

    @pytest.fixture
    def token_repository(self, datastore: DatastoreInterface) -> RefreshTokenRepository:
        """Create RefreshTokenRepository with parametrized datastore."""
        return RefreshTokenRepository(datastore=datastore)

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
            created_at=datetime.now(),
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
            created_at=datetime.now(),
        )

        await token_repository.revoke_token(token_hash)
        result = await token_repository.get_token(token_hash, device_info.fingerprint)

        assert result is None

    @pytest.mark.asyncio
    async def test_revoke_all_user_tokens(
        self, token_repository: RefreshTokenRepository
    ) -> None:
        """Revoking all user tokens works with any datastore."""
        user_id = "USER-MULTI"
        device1 = DeviceInfoFactory.build()
        device2 = DeviceInfoFactory.build()

        await token_repository.store_token(
            token_id="TOKEN-M1",
            user_id=user_id,
            token_hash="multi_hash_1",
            device_info=device1,
            created_at=datetime.now(),
        )
        await token_repository.store_token(
            token_id="TOKEN-M2",
            user_id=user_id,
            token_hash="multi_hash_2",
            device_info=device2,
            created_at=datetime.now(),
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

    @skip_postgres
    @pytest.mark.asyncio
    async def test_postgres_has_persistence_true(
        self, postgres_datastore: DatastoreInterface
    ) -> None:
        """PostgresDatastore.has_persistence is True."""
        assert postgres_datastore.has_persistence is True

    @skip_postgres
    @pytest.mark.asyncio
    async def test_postgres_has_transactions_true(
        self, postgres_datastore: DatastoreInterface
    ) -> None:
        """PostgresDatastore.has_transactions is True."""
        assert postgres_datastore.has_transactions is True
