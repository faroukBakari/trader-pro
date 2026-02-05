"""PostgreSQL test database helpers.

Utility functions for PostgreSQL test database management.
Used by conftest.py test_settings fixture.

[ARCHITECTURE] Helper module only - no fixtures here.
Fixtures live in conftest.py (test_settings is SSOT for all config).
"""

import logging
import os
from pathlib import Path
from urllib.parse import urlparse

import psycopg
from psycopg import sql

from alembic import command
from alembic.config import Config
from trading_api.datastores.postgres.engine import AsyncEngineFactory

logger = logging.getLogger(__name__)

# Test database name (created on container's postgres instance)
TEST_DB_NAME = "trader_test"


def _get_alembic_config(dsn: str) -> Config:
    """Create Alembic config pointing to the test database.

    Args:
        dsn: Database connection string (normalized via AsyncEngineFactory)

    Returns:
        Configured Alembic Config object
    """
    async_dsn = AsyncEngineFactory._normalize_url(dsn)

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
    # Set the DSN in environment for alembic/env.py (normalization handled by engine.py)
    os.environ["DATASTORE_POSTGRES_DSN"] = dsn
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

    parsed = urlparse(clean_url)
    # Replace the path (database name) with our test database
    return f"{parsed.scheme}://{parsed.netloc}/{db_name}"
