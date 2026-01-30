"""Root conftest for all backend tests.

This conftest configures pytest-asyncio for session-scoped event loops.
pytest-asyncio 1.1+ uses asyncio.Runner internally which properly:
- Cancels pending tasks before loop close
- Shuts down async generators
- Shuts down the default executor

Configuration is in pyproject.toml:
  asyncio_default_fixture_loop_scope = "session"

[ARCHITECTURE] test_settings as Single Source of Truth:
- CI mode: DATASTORE_POSTGRES_DSN env var presence = indicator (no _is_ci_environment())
- Local mode: testcontainers spins up postgres:16, DSN injected into Settings
- Settings constructed once with correct DSN - no mutation
"""

import logging
import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from trading_api.shared.config import Settings

logger = logging.getLogger(__name__)

# No custom event_loop fixture needed - pytest-asyncio 1.1+ handles cleanup properly

# Disable Ryuk sidecar - context manager handles cleanup, no need for reaper
os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")


def _build_test_settings(project_root: Path, postgres_dsn: str | None) -> Settings:
    """Build Settings instance with test-specific configuration.

    Args:
        project_root: Path to backend/ directory
        postgres_dsn: PostgreSQL DSN (None if postgres tests should skip)

    Returns:
        Configured Settings instance
    """
    return Settings(
        # JWT paths - resolve from project root (same as production)
        JWT_PRIVATE_KEY_PATH=project_root / ".local/secrets/jwt_private.pem",
        JWT_PUBLIC_KEY_PATH=project_root / ".local/secrets/jwt_public.pem",
        INTERNAL_HMAC_KEY_PATH=project_root / ".local/secrets/hmac_internal.key",
        # PostgreSQL - DSN from env (CI) or testcontainers (local)
        DATASTORE_POSTGRES_DSN=postgres_dsn,
        DATASTORE_POSTGRES_POOL_MAX_SIZE=2,  # Minimal pool for tests
        DATASTORE_POSTGRES_POOL_RECONNECT_TIMEOUT=2.0,  # Faster timeouts for tests
        DATASTORE_POSTGRES_POOL_OPEN_TIMEOUT=10.0,
        # API config
        API_PORT=8000,
        DEFAULT_TIMEOUT=10.0,
        # CORS/Cookie - test defaults
        CORS_ORIGINS=["http://localhost:5173"],
        COOKIE_SECURE=False,
        # Google OAuth - empty for tests (mocked)
        GOOGLE_CLIENT_ID="",
    )


@pytest.fixture(scope="session")
def test_settings() -> Iterator[Settings]:
    """Session-scoped test settings - SINGLE SOURCE OF TRUTH for all config.

    Handles PostgreSQL setup automatically:
    - CI mode: Uses DATASTORE_POSTGRES_DSN from environment (GitHub Actions service container)
    - Local mode: Spins up postgres:16 via testcontainers, creates test database

    DSN presence in environment IS the CI indicator - no separate detection needed.
    Settings is constructed once with correct DSN - no mutation after creation.

    Yields:
        Settings: Fully configured Settings instance for test session
    """
    # Import here to avoid import errors when testcontainers not installed
    from testcontainers.postgres import PostgresContainer

    from tests.integration.fixtures.postgres_db import (
        TEST_DB_NAME,
        _build_dsn,
        _create_test_database,
        _drop_test_database,
        _run_migrations,
    )

    project_root = Path(__file__).parent
    env_dsn = os.environ.get("DATASTORE_POSTGRES_DSN")

    # CI mode: DSN from environment = indicator
    if env_dsn:
        dsn = env_dsn.replace("postgresql+psycopg://", "postgresql://")
        logger.info("CI mode: using pre-configured DSN from environment")
        _run_migrations(dsn)
        yield _build_test_settings(project_root, dsn)
        return

    # Local mode: testcontainers for PostgreSQL
    logger.info("Local mode: starting PostgreSQL via testcontainers...")

    with PostgresContainer("postgres:16", driver="psycopg") as postgres:
        container_url = postgres.get_connection_url()
        logger.info(f"PostgreSQL container started: {postgres.get_container_host_ip()}")

        maintenance_dsn = _build_dsn(container_url, "postgres")
        test_dsn = _build_dsn(container_url, TEST_DB_NAME)

        _create_test_database(maintenance_dsn, TEST_DB_NAME)

        try:
            _run_migrations(test_dsn)
            # Set env var for alembic/env.py backward compatibility
            os.environ["DATASTORE_POSTGRES_DSN"] = test_dsn

            yield _build_test_settings(project_root, test_dsn)

        finally:
            try:
                _drop_test_database(maintenance_dsn, TEST_DB_NAME)
            except Exception as e:
                logger.warning(f"Failed to drop test database: {e}")
            os.environ.pop("DATASTORE_POSTGRES_DSN", None)


def pytest_configure(config: pytest.Config) -> None:
    """Safety guard: block integration tests if DSN points to non-test database.

    If DATASTORE_POSTGRES_DSN is explicitly set (e.g., by CI or user override),
    verify it points to a test database (contains '_test' in the database name).

    This prevents accidental data corruption in dev/prod databases.
    """
    dsn = os.environ.get("DATASTORE_POSTGRES_DSN", "")

    # Only check if DSN is explicitly set AND we're running integration tests
    if not dsn:
        return  # No external DSN - fixture will handle test DB creation

    # Check if running integration tests
    markexpr = getattr(config.option, "markexpr", "") or ""
    keyword = getattr(config.option, "keyword", "") or ""

    running_integration = "integration" in markexpr or "integration" in keyword

    if running_integration:
        # Extract database name from DSN (format: ...host:port/dbname or ...host/dbname)
        try:
            db_name = dsn.rstrip("/").split("/")[-1]
            # Check for "test" anywhere in database name (e.g., test_db, trader_bars_test)
            if "test" not in db_name.lower():
                pytest.exit(
                    f"❌ SECURITY: DATASTORE_POSTGRES_DSN must point to a test database!\n"
                    f"   Current database: {db_name}\n"
                    f"   Either unset the variable (fixture will create test DB) or use a *test* database.",
                    returncode=1,
                )
        except Exception:
            pass  # If we can't parse, let the test fixtures handle validation
