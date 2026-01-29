"""Alembic migration tests - validates JSONB → typed column data integrity.

Tests the migration path from Wave 2A (JSONB storage) to Wave 2B (typed columns).
Uses fake data to verify:
- Data is preserved during upgrade
- Round-trip (upgrade → downgrade → upgrade) maintains integrity
- Edge cases (NULL values, special characters) are handled

Run with: pytest tests/integration/test_alembic_migrations.py -v
"""

import json
import logging
import os
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlparse

import psycopg
import pytest
from psycopg import sql

from alembic import command
from alembic.config import Config

# Import testcontainers setup (includes RYUK_DISABLED)

logger = logging.getLogger(__name__)

# Separate database for migration tests to avoid conflicts
MIGRATION_TEST_DB = "trader_migration_test"


# =============================================================================
# Test Data Fixtures
# =============================================================================


FAKE_USERS = [
    {
        "key": "USER-001",
        "value": {
            "email": "alice@example.com",
            "google_id": "google-alice-123",
            "full_name": "Alice Wonderland",
            "picture": "https://example.com/alice.jpg",
            "created_at": "2025-06-15T10:30:00+00:00",
            "last_login": "2026-01-28T14:22:00+00:00",
            "is_active": True,
        },
    },
    {
        "key": "USER-002",
        "value": {
            "email": "bob@example.com",
            "google_id": "google-bob-456",
            "full_name": "Bob Builder",
            "picture": None,  # Test NULL handling
            "created_at": "2025-08-20T08:00:00+00:00",
            "last_login": "2026-01-27T09:15:00+00:00",
            "is_active": True,
        },
    },
    {
        "key": "USER-003",
        "value": {
            "email": "charlie@example.com",
            "google_id": "google-charlie-789",
            "full_name": "Charlie O'Brien",  # Test special characters
            "picture": "https://example.com/charlie.png",
            "created_at": "2025-12-01T16:45:00+00:00",
            "last_login": "2026-01-29T11:00:00+00:00",
            "is_active": False,  # Test inactive user
        },
    },
]

FAKE_TOKENS = [
    {
        "key": "hash_abc123",
        "value": {
            "token_id": "TOKEN-001",
            "user_id": "USER-001",
            "created_at": "2026-01-28T14:22:00+00:00",
            "ip_address": "192.168.1.100",
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "fingerprint": "fp_alice_device1",
        },
    },
    {
        "key": "hash_def456",
        "value": {
            "token_id": "TOKEN-002",
            "user_id": "USER-001",
            "created_at": "2026-01-27T09:00:00+00:00",
            "ip_address": "10.0.0.50",
            "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "fingerprint": "fp_alice_device2",
        },
    },
    {
        "key": "hash_ghi789",
        "value": {
            "token_id": "TOKEN-003",
            "user_id": "USER-002",
            "created_at": "2026-01-27T09:15:00+00:00",
            "ip_address": "172.16.0.25",
            "user_agent": "Mozilla/5.0 (Linux; Android 11)",
            "fingerprint": "fp_bob_mobile",
        },
    },
]


# =============================================================================
# Helper Functions
# =============================================================================


def _get_alembic_config(dsn: str) -> Config:
    """Create Alembic config pointing to the test database."""
    async_dsn = dsn.replace("postgresql://", "postgresql+asyncpg://")
    backend_dir = Path(__file__).parents[2]  # backend/
    alembic_ini = backend_dir / "alembic.ini"

    config = Config(str(alembic_ini))
    config.set_main_option("sqlalchemy.url", async_dsn)
    return config


def _build_dsn(base_url: str, db_name: str) -> str:
    """Build a DSN for a specific database from a base URL."""
    clean_url = base_url.replace("postgresql+psycopg://", "postgresql://")
    clean_url = clean_url.replace("postgresql+asyncpg://", "postgresql://")
    parsed = urlparse(clean_url)
    return f"{parsed.scheme}://{parsed.netloc}/{db_name}"


def _create_jsonb_schema(dsn: str) -> None:
    """Create Wave 2A JSONB schema (simulating pre-migration state).

    This creates tables with the JSONB pattern:
    - key (primary key)
    - value (JSONB)
    - created_at
    - updated_at
    """
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            # Users table (Wave 2A JSONB schema)
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    key VARCHAR PRIMARY KEY,
                    value JSONB NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """
            )
            # JSONB indexes (Wave 2A pattern)
            cur.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uidx_users_email
                ON users ((value->>'email'))
            """
            )
            cur.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uidx_users_google_id
                ON users ((value->>'google_id'))
            """
            )

            # Refresh tokens table (Wave 2A JSONB schema)
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS refresh_tokens (
                    key VARCHAR PRIMARY KEY,
                    value JSONB NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """
            )
            # JSONB index
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id
                ON refresh_tokens ((value->>'user_id'))
            """
            )


def _seed_jsonb_data(dsn: str) -> None:
    """Insert fake data into JSONB tables."""
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            # Insert users
            for user in FAKE_USERS:
                cur.execute(
                    """
                    INSERT INTO users (key, value, created_at, updated_at)
                    VALUES (%s, %s, NOW(), NOW())
                    """,
                    (user["key"], json.dumps(user["value"])),
                )

            # Insert tokens
            for token in FAKE_TOKENS:
                cur.execute(
                    """
                    INSERT INTO refresh_tokens (key, value, created_at, updated_at)
                    VALUES (%s, %s, NOW(), NOW())
                    """,
                    (token["key"], json.dumps(token["value"])),
                )


def _get_typed_users(dsn: str) -> list[dict]:
    """Fetch users from typed schema (post-migration)."""
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, email, google_id, full_name, picture,
                       created_at, last_login, is_active
                FROM users ORDER BY id
            """
            )
            assert cur.description is not None
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]


def _get_typed_tokens(dsn: str) -> list[dict]:
    """Fetch tokens from typed schema (post-migration)."""
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT token_hash, token_id, user_id, created_at,
                       ip_address, user_agent, fingerprint
                FROM refresh_tokens ORDER BY token_hash
            """
            )
            assert cur.description is not None
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]


def _get_jsonb_users(dsn: str) -> list[dict]:
    """Fetch users from JSONB schema (pre-migration or post-downgrade)."""
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT key, value FROM users ORDER BY key")
            return [{"key": row[0], "value": row[1]} for row in cur.fetchall()]


def _get_jsonb_tokens(dsn: str) -> list[dict]:
    """Fetch tokens from JSONB schema (pre-migration or post-downgrade)."""
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT key, value FROM refresh_tokens ORDER BY key")
            return [{"key": row[0], "value": row[1]} for row in cur.fetchall()]


def _table_has_column(dsn: str, table: str, column: str) -> bool:
    """Check if a column exists in a table."""
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_name = %s AND column_name = %s
                """,
                (table, column),
            )
            return cur.fetchone() is not None


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(scope="module")
def migration_database() -> Iterator[str]:
    """Isolated database for migration testing.

    Creates a fresh database, sets up JSONB schema with test data,
    and provides DSN for migration tests.
    """
    from testcontainers.postgres import PostgresContainer

    logger.info("Starting PostgreSQL container for migration tests...")

    with PostgresContainer("postgres:16", driver="psycopg") as postgres:
        container_url = postgres.get_connection_url()
        maintenance_dsn = _build_dsn(container_url, "postgres")
        test_dsn = _build_dsn(container_url, MIGRATION_TEST_DB)

        # Create database
        with psycopg.connect(maintenance_dsn, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL("DROP DATABASE IF EXISTS {}").format(
                        sql.Identifier(MIGRATION_TEST_DB)
                    )
                )
                cur.execute(
                    sql.SQL("CREATE DATABASE {}").format(
                        sql.Identifier(MIGRATION_TEST_DB)
                    )
                )

        # Set up JSONB schema (simulating Wave 2A)
        _create_jsonb_schema(test_dsn)
        _seed_jsonb_data(test_dsn)

        # Mark alembic_version as 000 (pre-migration state)
        with psycopg.connect(test_dsn, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS alembic_version (
                        version_num VARCHAR(32) PRIMARY KEY
                    )
                """
                )
                cur.execute("DELETE FROM alembic_version")
                cur.execute(
                    "INSERT INTO alembic_version (version_num) VALUES ('000_initial_schema')"
                )

        # Export DSN for alembic env.py
        os.environ["DATASTORE_POSTGRES_DSN"] = test_dsn.replace(
            "postgresql://", "postgresql+asyncpg://"
        )

        yield test_dsn

        # Cleanup
        os.environ.pop("DATASTORE_POSTGRES_DSN", None)


# =============================================================================
# Tests
# =============================================================================


@pytest.mark.integration
class TestAlembicMigrationDataIntegrity:
    """Test data integrity during JSONB → typed column migration."""

    def test_pre_migration_jsonb_schema_exists(self, migration_database: str) -> None:
        """Verify JSONB schema is set up correctly before migration."""
        # Check JSONB columns exist
        assert _table_has_column(migration_database, "users", "key")
        assert _table_has_column(migration_database, "users", "value")
        assert not _table_has_column(migration_database, "users", "id")
        assert not _table_has_column(migration_database, "users", "email")

        # Verify test data
        users = _get_jsonb_users(migration_database)
        assert len(users) == 3
        assert users[0]["key"] == "USER-001"
        assert users[0]["value"]["email"] == "alice@example.com"

    def test_upgrade_preserves_user_data(self, migration_database: str) -> None:
        """Verify user data is correctly migrated to typed columns."""
        config = _get_alembic_config(migration_database)

        # Run migration
        command.upgrade(config, "001_migrate_jsonb_to_typed")

        # Verify typed schema
        assert _table_has_column(migration_database, "users", "id")
        assert _table_has_column(migration_database, "users", "email")
        assert not _table_has_column(migration_database, "users", "key")
        assert not _table_has_column(migration_database, "users", "value")

        # Verify data integrity
        users = _get_typed_users(migration_database)
        assert len(users) == 3

        # USER-001: Alice
        alice = next(u for u in users if u["id"] == "USER-001")
        assert alice["email"] == "alice@example.com"
        assert alice["google_id"] == "google-alice-123"
        assert alice["full_name"] == "Alice Wonderland"
        assert alice["picture"] == "https://example.com/alice.jpg"
        assert alice["is_active"] is True

        # USER-002: Bob (NULL picture)
        bob = next(u for u in users if u["id"] == "USER-002")
        assert bob["email"] == "bob@example.com"
        assert bob["picture"] is None

        # USER-003: Charlie (special chars, inactive)
        charlie = next(u for u in users if u["id"] == "USER-003")
        assert charlie["full_name"] == "Charlie O'Brien"
        assert charlie["is_active"] is False

    def test_upgrade_preserves_token_data(self, migration_database: str) -> None:
        """Verify token data is correctly migrated to typed columns."""
        # Migration already ran in previous test (tests run sequentially)
        tokens = _get_typed_tokens(migration_database)
        assert len(tokens) == 3

        # TOKEN-001
        token1 = next(t for t in tokens if t["token_hash"] == "hash_abc123")
        assert token1["token_id"] == "TOKEN-001"
        assert token1["user_id"] == "USER-001"
        assert token1["ip_address"] == "192.168.1.100"
        assert token1["fingerprint"] == "fp_alice_device1"

    def test_downgrade_restores_jsonb_schema(self, migration_database: str) -> None:
        """Verify downgrade correctly restores JSONB schema with data."""
        config = _get_alembic_config(migration_database)

        # Downgrade
        command.downgrade(config, "000_initial_schema")

        # Verify JSONB schema restored
        assert _table_has_column(migration_database, "users", "key")
        assert _table_has_column(migration_database, "users", "value")
        assert not _table_has_column(migration_database, "users", "id")

        # Verify data preserved
        users = _get_jsonb_users(migration_database)
        assert len(users) == 3

        alice = next(u for u in users if u["key"] == "USER-001")
        assert alice["value"]["email"] == "alice@example.com"
        assert alice["value"]["google_id"] == "google-alice-123"

    def test_round_trip_preserves_data(self, migration_database: str) -> None:
        """Verify upgrade → downgrade → upgrade preserves all data."""
        config = _get_alembic_config(migration_database)

        # Upgrade again
        command.upgrade(config, "001_migrate_jsonb_to_typed")

        # Verify data still intact
        users = _get_typed_users(migration_database)
        assert len(users) == 3

        alice = next(u for u in users if u["id"] == "USER-001")
        assert alice["email"] == "alice@example.com"
        assert alice["full_name"] == "Alice Wonderland"

        tokens = _get_typed_tokens(migration_database)
        assert len(tokens) == 3

        token1 = next(t for t in tokens if t["token_hash"] == "hash_abc123")
        assert token1["user_id"] == "USER-001"


@pytest.mark.integration
class TestAlembicMigrationEdgeCases:
    """Test edge cases and error handling in migrations."""

    def test_migration_handles_empty_tables(self) -> None:
        """Verify migration works on empty JSONB tables."""
        from testcontainers.postgres import PostgresContainer

        with PostgresContainer("postgres:16", driver="psycopg") as postgres:
            container_url = postgres.get_connection_url()
            maintenance_dsn = _build_dsn(container_url, "postgres")
            test_dsn = _build_dsn(container_url, "empty_test")

            # Create database
            with psycopg.connect(maintenance_dsn, autocommit=True) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        sql.SQL("CREATE DATABASE {}").format(
                            sql.Identifier("empty_test")
                        )
                    )

            # Create empty JSONB tables
            _create_jsonb_schema(test_dsn)

            # Mark as pre-migration
            with psycopg.connect(test_dsn, autocommit=True) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS alembic_version (
                            version_num VARCHAR(32) PRIMARY KEY
                        )
                    """
                    )
                    cur.execute(
                        "INSERT INTO alembic_version (version_num) VALUES ('000_initial_schema')"
                    )

            os.environ["DATASTORE_POSTGRES_DSN"] = test_dsn.replace(
                "postgresql://", "postgresql+asyncpg://"
            )

            try:
                config = _get_alembic_config(test_dsn)

                # Should not raise
                command.upgrade(config, "001_migrate_jsonb_to_typed")

                # Verify typed schema exists but empty
                users = _get_typed_users(test_dsn)
                assert len(users) == 0

                tokens = _get_typed_tokens(test_dsn)
                assert len(tokens) == 0
            finally:
                os.environ.pop("DATASTORE_POSTGRES_DSN", None)

    def test_idempotent_upgrade_on_fresh_db(self) -> None:
        """Verify migrations are idempotent on fresh databases."""
        from testcontainers.postgres import PostgresContainer

        with PostgresContainer("postgres:16", driver="psycopg") as postgres:
            container_url = postgres.get_connection_url()
            maintenance_dsn = _build_dsn(container_url, "postgres")
            test_dsn = _build_dsn(container_url, "fresh_test")

            # Create empty database (no tables)
            with psycopg.connect(maintenance_dsn, autocommit=True) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        sql.SQL("CREATE DATABASE {}").format(
                            sql.Identifier("fresh_test")
                        )
                    )

            os.environ["DATASTORE_POSTGRES_DSN"] = test_dsn.replace(
                "postgresql://", "postgresql+asyncpg://"
            )

            try:
                config = _get_alembic_config(test_dsn)

                # Run full migration chain on fresh db
                command.upgrade(config, "head")

                # Verify typed schema exists
                assert _table_has_column(test_dsn, "users", "id")
                assert _table_has_column(test_dsn, "users", "email")

                # Running upgrade again should be idempotent
                command.upgrade(config, "head")

                # Still valid
                assert _table_has_column(test_dsn, "users", "id")
            finally:
                os.environ.pop("DATASTORE_POSTGRES_DSN", None)
