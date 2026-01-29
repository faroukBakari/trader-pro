"""PostgreSQL test database fixture.

Creates an ephemeral test database for integration tests.
The database is created at session start and dropped at session end.

[ARCHITECTURE] Wave 2B: Robust test database management using testcontainers
- Local: Uses testcontainers to spin up PostgreSQL container programmatically
- CI: Uses GitHub Actions service container (DATASTORE_POSTGRES_DSN env var)
- Uses Alembic migrations for schema (ensures typed tables exist)
- Ryuk sidecar disabled; context manager handles immediate cleanup

Dual-path architecture:
- CI mode: Detects via CI/GITHUB_ACTIONS env vars, uses pre-configured DSN
- Local mode: testcontainers manages container lifecycle with health checks
"""

import logging
import os
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlparse

import psycopg
import pytest
from psycopg import sql
from testcontainers.postgres import PostgresContainer

from alembic import command
from alembic.config import Config

logger = logging.getLogger(__name__)

# Disable Ryuk sidecar - context manager handles cleanup, no need for reaper
# This ensures immediate container removal on test exit (no 10s delay)
os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

# Test database name (created on container's postgres instance)
TEST_DB_NAME = "trader_test"


def _is_ci_environment() -> bool:
    """Detect CI environment using standard environment variables.

    Returns:
        True if running in CI (GitHub Actions, GitLab CI, etc.)
    """
    ci_indicators = [
        os.environ.get("CI"),
        os.environ.get("GITHUB_ACTIONS"),
        os.environ.get("GITLAB_CI"),
    ]
    return any(ci_indicators)


def _get_alembic_config(dsn: str) -> Config:
    """Create Alembic config pointing to the test database.

    Args:
        dsn: Database connection string (will be converted to asyncpg driver)

    Returns:
        Configured Alembic Config object
    """
    # Alembic expects asyncpg driver for async migrations
    async_dsn = dsn.replace("postgresql://", "postgresql+asyncpg://")

    backend_dir = Path(__file__).parents[3]  # backend/
    alembic_ini = backend_dir / "alembic.ini"

    config = Config(str(alembic_ini))
    config.set_main_option("sqlalchemy.url", async_dsn)
    return config


def _create_test_database(maintenance_dsn: str, db_name: str) -> None:
    """Create the test database on the PostgreSQL instance.

    Args:
        maintenance_dsn: DSN to connect to 'postgres' database (superuser)
        db_name: Name of the test database to create
    """
    with psycopg.connect(maintenance_dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            # Terminate existing connections to test db
            cur.execute(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = %s AND pid <> pg_backend_pid()
                """,
                (db_name,),
            )
            # Drop if exists, then create fresh
            # Use sql.Identifier for safe SQL composition (DDL doesn't support parameters)
            cur.execute(
                sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(db_name))
            )
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))


def _drop_test_database(maintenance_dsn: str, db_name: str) -> None:
    """Drop the test database.

    Args:
        maintenance_dsn: DSN to connect to 'postgres' database (superuser)
        db_name: Name of the test database to drop
    """
    with psycopg.connect(maintenance_dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            # Terminate existing connections first
            cur.execute(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = %s AND pid <> pg_backend_pid()
                """,
                (db_name,),
            )
            # Use sql.Identifier for safe SQL composition
            cur.execute(
                sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(db_name))
            )


def _run_migrations(dsn: str) -> None:
    """Run Alembic migrations on the test database.

    Args:
        dsn: Database connection string
    """
    config = _get_alembic_config(dsn)
    # Set the DSN in environment for alembic/env.py
    os.environ["DATASTORE_POSTGRES_DSN"] = dsn.replace(
        "postgresql://", "postgresql+asyncpg://"
    )
    command.upgrade(config, "head")


def _build_dsn(base_url: str, db_name: str) -> str:
    """Build a DSN for a specific database from a base URL.

    Args:
        base_url: Base connection URL (may include SQLAlchemy driver suffix)
        db_name: Target database name

    Returns:
        DSN pointing to the specified database (psycopg-compatible)
    """
    # Strip SQLAlchemy driver suffix (e.g., postgresql+psycopg:// -> postgresql://)
    clean_url = base_url.replace("postgresql+psycopg://", "postgresql://")
    clean_url = clean_url.replace("postgresql+asyncpg://", "postgresql://")

    parsed = urlparse(clean_url)
    # Replace the path (database name) with our test database
    return f"{parsed.scheme}://{parsed.netloc}/{db_name}"


@pytest.fixture(scope="session")
def test_database() -> Iterator[str]:
    """Session-scoped fixture providing an ephemeral test database.

    Creates a fresh database at session start, runs migrations for schema,
    and drops it at session end.

    [ARCHITECTURE] Wave 2B: testcontainers-based PostgreSQL management
    - CI mode: Uses DATASTORE_POSTGRES_DSN from GitHub Actions service container
    - Local mode: testcontainers spins up postgres:16 with automatic cleanup
    - Runs Alembic migrations (000_initial_schema → 001_migrate_jsonb_to_typed)
    - Container lifecycle managed by testcontainers ryuk sidecar

    Yields:
        str: Database connection string (DSN) for the test database

    Raises:
        pytest.fail: If PostgreSQL cannot be started or migrations fail
    """
    # CI mode: use pre-configured DSN from GitHub Actions service container
    if _is_ci_environment():
        env_dsn = os.environ.get("DATASTORE_POSTGRES_DSN", "")
        if not env_dsn:
            pytest.fail(
                "CI environment detected but DATASTORE_POSTGRES_DSN not set. "
                "Ensure PostgreSQL service container is configured in CI workflow."
            )
        # Convert asyncpg URL to psycopg format for consistency
        dsn = env_dsn.replace("postgresql+asyncpg://", "postgresql://")
        logger.info("CI mode: using pre-configured DSN")
        # Run migrations on CI database
        _run_migrations(dsn)
        os.environ["DATASTORE_POSTGRES_DSN"] = dsn.replace(
            "postgresql://", "postgresql+asyncpg://"
        )
        yield dsn
        return

    # Local mode: use testcontainers for PostgreSQL
    logger.info("Local mode: starting PostgreSQL via testcontainers...")

    with PostgresContainer("postgres:16", driver="psycopg") as postgres:
        # Get the superuser connection URL (points to 'test' database by default)
        container_url = postgres.get_connection_url()
        logger.info(f"PostgreSQL container started: {postgres.get_container_host_ip()}")

        # Build maintenance DSN (connect to 'postgres' db for CREATE DATABASE)
        maintenance_dsn = _build_dsn(container_url, "postgres")

        # Build test database DSN
        test_dsn = _build_dsn(container_url, TEST_DB_NAME)

        # Create fresh test database
        _create_test_database(maintenance_dsn, TEST_DB_NAME)

        try:
            # Run Alembic migrations to create schema
            _run_migrations(test_dsn)

            # Export for any code that reads from environment
            os.environ["DATASTORE_POSTGRES_DSN"] = test_dsn.replace(
                "postgresql://", "postgresql+asyncpg://"
            )

            yield test_dsn

        finally:
            # Cleanup: drop the test database (optional, container will be destroyed)
            try:
                _drop_test_database(maintenance_dsn, TEST_DB_NAME)
            except Exception as e:
                logger.warning(
                    f"Failed to drop test database (container cleanup will handle it): {e}"
                )

            # Clean up environment
            os.environ.pop("DATASTORE_POSTGRES_DSN", None)
