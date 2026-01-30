"""Tests for PostgreSQL bar storage (Wave 3A).

Unit tests for bar_table_name() run without database.
Integration tests for PostgresBarRepository require PostgreSQL.
"""

from collections.abc import AsyncIterator

import pytest

from trading_api.datastores.postgres.bars import (
    BAR_TABLE_PREFIX,
    PostgresBarRepository,
    bar_table_name,
)
from trading_api.datastores.postgres.datastore import PostgresDatastore
from trading_api.models.market import Bar, Resolution
from trading_api.shared.config import Settings

# =============================================================================
# Unit Tests for bar_table_name() - No database required
# =============================================================================


class TestBarTableName:
    """Unit tests for bar_table_name() helper function."""

    def test_basic_symbol_resolution(self) -> None:
        """Basic symbol and resolution produce expected table name."""
        # Numeric resolutions get 'r' prefix for valid PostgreSQL identifier
        assert bar_table_name("AAPL", "1D") == "bars_aapl_r1d"

    def test_lowercase_conversion(self) -> None:
        """Uppercase inputs are lowercased."""
        assert bar_table_name("MSFT", "1H") == "bars_msft_r1h"
        assert bar_table_name("msft", "1h") == "bars_msft_r1h"

    def test_forex_slash_replacement(self) -> None:
        """Forex pairs with slashes are converted to underscores."""
        assert bar_table_name("EUR/USD", "1D") == "bars_eur_usd_r1d"
        assert bar_table_name("GBP/JPY", "60") == "bars_gbp_jpy_r60"

    def test_resolution_enum_accepted(self) -> None:
        """Resolution enum is converted to its value."""
        assert bar_table_name("AAPL", Resolution.DAY_1) == "bars_aapl_r1d"
        assert bar_table_name("AAPL", Resolution.HOUR_1) == "bars_aapl_r60"
        assert bar_table_name("AAPL", Resolution.MIN_5) == "bars_aapl_r5"

    def test_prefix_constant(self) -> None:
        """BAR_TABLE_PREFIX is used in generated names."""
        name = bar_table_name("TEST", "1D")
        assert name.startswith(BAR_TABLE_PREFIX)

    def test_rejects_sql_injection_in_symbol(self) -> None:
        """SQL injection attempts in symbol raise ValueError."""
        with pytest.raises(ValueError, match="Invalid symbol"):
            bar_table_name("'; DROP TABLE--", "1D")

    def test_rejects_sql_injection_in_resolution(self) -> None:
        """SQL injection attempts in resolution raise ValueError."""
        with pytest.raises(ValueError, match="Invalid resolution"):
            bar_table_name("AAPL", "1D; DROP TABLE")

    def test_rejects_empty_symbol(self) -> None:
        """Empty symbol raises ValueError."""
        with pytest.raises(ValueError, match="Empty symbol"):
            bar_table_name("", "1D")

    def test_rejects_empty_resolution(self) -> None:
        """Empty resolution raises ValueError."""
        with pytest.raises(ValueError, match="Empty resolution"):
            bar_table_name("AAPL", "")

    def test_rejects_special_characters(self) -> None:
        """Special characters other than slash are rejected."""
        with pytest.raises(ValueError):
            bar_table_name("AAPL$", "1D")
        with pytest.raises(ValueError):
            bar_table_name("AAPL", "1D!")


# =============================================================================
# Integration Tests for PostgresBarRepository - Require PostgreSQL
# =============================================================================

pytestmark_integration = [pytest.mark.integration, pytest.mark.postgres]


@pytest.fixture
async def postgres_datastore(
    test_settings: Settings,
) -> AsyncIterator[PostgresDatastore]:
    """Create PostgresDatastore for testing with cleanup."""
    ds = await PostgresDatastore.create(config=test_settings)
    yield ds
    await ds.close()


@pytest.fixture
async def bar_repository(
    postgres_datastore: PostgresDatastore,
) -> AsyncIterator[PostgresBarRepository]:
    """Create PostgresBarRepository for testing.

    Uses the internal _pool from PostgresDatastore.
    """
    repo = PostgresBarRepository(postgres_datastore._pool)
    yield repo
    # Cleanup: drop any test tables created
    tables = await postgres_datastore.list_tables(prefix=BAR_TABLE_PREFIX)
    for table in tables:
        async with postgres_datastore._pool.connection() as conn:
            from psycopg import sql

            await conn.execute(
                sql.SQL("DROP TABLE IF EXISTS {}").format(sql.Identifier(table))
            )


@pytest.mark.integration
@pytest.mark.postgres
class TestPostgresBarRepositoryStoreAndGet:
    """Integration tests for store_bars() and get_bars()."""

    @pytest.mark.asyncio
    async def test_store_single_bar(
        self, bar_repository: PostgresBarRepository
    ) -> None:
        """Single bar can be stored and retrieved."""
        bar = Bar(
            time=1000000,
            open=100.0,
            high=105.0,
            low=99.0,
            close=104.0,
            volume=1000,
            count=50,
        )

        stored = await bar_repository.store_bars("AAPL", "1D", [bar])
        assert stored == 1

        bars = await bar_repository.get_bars("AAPL", "1D")
        assert len(bars) == 1
        assert bars[0].time == 1000000
        assert bars[0].open == 100.0
        assert bars[0].close == 104.0

    @pytest.mark.asyncio
    async def test_store_multiple_bars(
        self, bar_repository: PostgresBarRepository
    ) -> None:
        """Multiple bars can be stored and retrieved in order."""
        bars = [
            Bar(time=1000, open=100, high=105, low=99, close=104, volume=100, count=10),
            Bar(
                time=2000, open=104, high=110, low=103, close=108, volume=200, count=20
            ),
            Bar(
                time=3000, open=108, high=112, low=107, close=111, volume=150, count=15
            ),
        ]

        stored = await bar_repository.store_bars("TEST", "1H", bars)
        assert stored == 3

        retrieved = await bar_repository.get_bars("TEST", "1H")
        assert len(retrieved) == 3
        # Verify ordering by time
        assert retrieved[0].time == 1000
        assert retrieved[1].time == 2000
        assert retrieved[2].time == 3000

    @pytest.mark.asyncio
    async def test_upsert_updates_existing(
        self, bar_repository: PostgresBarRepository
    ) -> None:
        """Storing bar with same timestamp updates existing."""
        bar1 = Bar(
            time=1000, open=100, high=105, low=99, close=104, volume=100, count=10
        )
        bar2 = Bar(
            time=1000, open=101, high=106, low=100, close=105, volume=150, count=15
        )

        await bar_repository.store_bars("UPSERT", "1D", [bar1])
        await bar_repository.store_bars("UPSERT", "1D", [bar2])

        bars = await bar_repository.get_bars("UPSERT", "1D")
        assert len(bars) == 1
        assert bars[0].open == 101.0  # Updated value
        assert bars[0].volume == 150

    @pytest.mark.asyncio
    async def test_get_bars_time_range(
        self, bar_repository: PostgresBarRepository
    ) -> None:
        """get_bars() respects time range filters."""
        bars = [
            Bar(time=1000, open=100, high=105, low=99, close=104, volume=100, count=10),
            Bar(
                time=2000, open=104, high=110, low=103, close=108, volume=200, count=20
            ),
            Bar(
                time=3000, open=108, high=112, low=107, close=111, volume=150, count=15
            ),
            Bar(
                time=4000, open=111, high=115, low=110, close=114, volume=180, count=18
            ),
        ]
        await bar_repository.store_bars("RANGE", "1H", bars)

        # Get middle range
        result = await bar_repository.get_bars(
            "RANGE", "1H", from_time=2000, to_time=3000
        )
        assert len(result) == 2
        assert result[0].time == 2000
        assert result[1].time == 3000

    @pytest.mark.asyncio
    async def test_get_bars_empty_table(
        self, bar_repository: PostgresBarRepository
    ) -> None:
        """get_bars() returns empty list for empty/nonexistent table."""
        # Ensure table is created but empty
        await bar_repository._ensure_table(bar_table_name("EMPTY", "1D"))

        bars = await bar_repository.get_bars("EMPTY", "1D")
        assert bars == []

    @pytest.mark.asyncio
    async def test_store_empty_list(
        self, bar_repository: PostgresBarRepository
    ) -> None:
        """Storing empty list returns 0 and doesn't error."""
        stored = await bar_repository.store_bars("EMPTY", "1D", [])
        assert stored == 0

    @pytest.mark.asyncio
    async def test_resolution_enum(self, bar_repository: PostgresBarRepository) -> None:
        """Resolution enum works with store/get."""
        bar = Bar(
            time=1000, open=100, high=105, low=99, close=104, volume=100, count=10
        )

        await bar_repository.store_bars("ENUM", Resolution.DAY_1, [bar])
        bars = await bar_repository.get_bars("ENUM", Resolution.DAY_1)

        assert len(bars) == 1
        assert bars[0].time == 1000


@pytest.mark.integration
@pytest.mark.postgres
class TestPostgresBarRepositoryDropIfEmpty:
    """Integration tests for drop_if_empty()."""

    @pytest.mark.asyncio
    async def test_drop_empty_table(
        self, bar_repository: PostgresBarRepository
    ) -> None:
        """Empty table is dropped."""
        # Create table without data
        await bar_repository._ensure_table(bar_table_name("DROP_EMPTY", "1D"))

        dropped = await bar_repository.drop_if_empty("DROP_EMPTY", "1D")
        assert dropped is True

        # Verify table no longer exists
        exists = await bar_repository.table_exists("DROP_EMPTY", "1D")
        assert exists is False

    @pytest.mark.asyncio
    async def test_drop_nonempty_table_returns_false(
        self, bar_repository: PostgresBarRepository
    ) -> None:
        """Non-empty table is not dropped."""
        bar = Bar(
            time=1000, open=100, high=105, low=99, close=104, volume=100, count=10
        )
        await bar_repository.store_bars("DROP_NONEMPTY", "1D", [bar])

        dropped = await bar_repository.drop_if_empty("DROP_NONEMPTY", "1D")
        assert dropped is False

        # Verify table still exists with data
        bars = await bar_repository.get_bars("DROP_NONEMPTY", "1D")
        assert len(bars) == 1

    @pytest.mark.asyncio
    async def test_drop_nonexistent_table_returns_false(
        self, bar_repository: PostgresBarRepository
    ) -> None:
        """Nonexistent table returns False without error."""
        dropped = await bar_repository.drop_if_empty("NONEXISTENT_SYMBOL", "1D")
        assert dropped is False


@pytest.mark.integration
@pytest.mark.postgres
class TestPostgresBarRepositoryTableHelpers:
    """Integration tests for table_exists() and count_bars()."""

    @pytest.mark.asyncio
    async def test_table_exists_true(
        self, bar_repository: PostgresBarRepository
    ) -> None:
        """table_exists() returns True for existing table."""
        bar = Bar(
            time=1000, open=100, high=105, low=99, close=104, volume=100, count=10
        )
        await bar_repository.store_bars("EXISTS", "1D", [bar])

        exists = await bar_repository.table_exists("EXISTS", "1D")
        assert exists is True

    @pytest.mark.asyncio
    async def test_table_exists_false(
        self, bar_repository: PostgresBarRepository
    ) -> None:
        """table_exists() returns False for nonexistent table."""
        exists = await bar_repository.table_exists("NOT_EXISTS", "1D")
        assert exists is False

    @pytest.mark.asyncio
    async def test_count_bars(self, bar_repository: PostgresBarRepository) -> None:
        """count_bars() returns correct count."""
        bars = [
            Bar(time=1000, open=100, high=105, low=99, close=104, volume=100, count=10),
            Bar(
                time=2000, open=104, high=110, low=103, close=108, volume=200, count=20
            ),
        ]
        await bar_repository.store_bars("COUNT", "1D", bars)

        count = await bar_repository.count_bars("COUNT", "1D")
        assert count == 2

    @pytest.mark.asyncio
    async def test_count_bars_nonexistent(
        self, bar_repository: PostgresBarRepository
    ) -> None:
        """count_bars() returns 0 for nonexistent table."""
        count = await bar_repository.count_bars("NO_TABLE", "1D")
        assert count == 0
