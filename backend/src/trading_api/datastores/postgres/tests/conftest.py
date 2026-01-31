"""Conftest for PostgreSQL datastore tests.

The test_settings fixture from root conftest.py is the Single Source of Truth (SSOT)
for all test configuration, including PostgreSQL DSN setup via testcontainers or CI env.
"""

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, text
from sqlmodel import Session, SQLModel

from trading_api.shared.config import Settings


@pytest.fixture(scope="function")
def db_session(test_settings: Settings) -> Iterator[Session]:
    """Provide a database session for tests with automatic cleanup.

    Creates all SQLModel tables, yields session, then rolls back and drops tables.
    Each test function gets a fresh database state.

    Uses synchronous psycopg3 via the postgresql+psycopg:// driver.
    """
    dsn = test_settings.DATASTORE_POSTGRES_DSN
    if dsn is None:
        pytest.skip("No PostgreSQL DSN configured")

    # Ensure we use psycopg3 (not psycopg2)
    if "postgresql+psycopg://" not in dsn:
        sync_dsn = dsn.replace("postgresql://", "postgresql+psycopg://")
    else:
        sync_dsn = dsn

    engine = create_engine(sync_dsn, echo=False)

    # Enable btree_gist extension for EXCLUDE constraints
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist"))

    # Create tables
    SQLModel.metadata.create_all(engine)

    # Add EXCLUDE constraint for covered_ranges (matches PostgresDatastore.create())
    with engine.begin() as conn:
        conn.execute(
            text(
                """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'excl_covered_ranges_overlap'
                ) THEN
                    ALTER TABLE covered_ranges
                    ADD CONSTRAINT excl_covered_ranges_overlap
                    EXCLUDE USING gist (
                        symbol WITH =,
                        resolution WITH =,
                        time_range WITH &&
                    )
                    WHERE (time_range IS NOT NULL);
                END IF;
            END $$;
        """
            )
        )

    with Session(engine) as session:
        yield session
        session.rollback()

    # Cleanup: drop tables
    SQLModel.metadata.drop_all(engine)
    engine.dispose()
