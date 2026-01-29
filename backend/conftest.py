"""Root conftest for all backend tests.

This conftest configures pytest-asyncio for session-scoped event loops.
pytest-asyncio 1.1+ uses asyncio.Runner internally which properly:
- Cancels pending tasks before loop close
- Shuts down async generators
- Shuts down the default executor

Configuration is in pyproject.toml:
  asyncio_default_fixture_loop_scope = "session"
"""

import os

import pytest

# No custom event_loop fixture needed - pytest-asyncio 1.1+ handles cleanup properly


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
