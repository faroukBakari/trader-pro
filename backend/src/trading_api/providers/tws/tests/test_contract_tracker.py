"""Tests for ContractTracker with SQLite persistence.

Tests cover:
- SQLiteContractCache: CRUD operations, WAL mode, thread safety
- ContractTracker: Lazy loading (memory → SQLite → None), upsert, session management
"""

from pathlib import Path

import pytest
from ibapi.contract import Contract, ContractDescription, ContractDetails

from trading_api.providers.tws.contract_tracker import (
    ContractTracker,
    SQLiteContractCache,
)


def _make_contract(
    symbol: str = "AAPL",
    sec_type: str = "STK",
    exchange: str = "SMART",
    primary_exchange: str = "NASDAQ",
    con_id: int = 265598,
    currency: str = "USD",
) -> Contract:
    """Helper to create a Contract with required fields."""
    contract = Contract()
    contract.symbol = symbol
    contract.secType = sec_type
    contract.exchange = exchange
    contract.primaryExchange = primary_exchange
    contract.conId = con_id
    contract.currency = currency
    return contract


def _make_description(
    symbol: str = "AAPL",
    con_id: int = 265598,
    primary_exchange: str = "NASDAQ",
    derivative_sec_types: list[str] | None = None,
) -> ContractDescription:
    """Helper to create a ContractDescription."""
    desc = ContractDescription()
    desc.contract = _make_contract(
        symbol=symbol, con_id=con_id, primary_exchange=primary_exchange
    )
    desc.derivativeSecTypes = derivative_sec_types or []
    return desc


def _make_details(
    symbol: str = "AAPL",
    con_id: int = 265598,
    primary_exchange: str = "NASDAQ",
    long_name: str = "Apple Inc",
) -> ContractDetails:
    """Helper to create a ContractDetails."""
    details = ContractDetails()
    details.contract = _make_contract(
        symbol=symbol, con_id=con_id, primary_exchange=primary_exchange
    )
    details.longName = long_name
    details.minTick = 0.01
    details.validExchanges = "SMART,NASDAQ"
    details.tradingHours = "20260114:0930-20260114:1600"
    return details


# === SQLiteContractCache Tests ===


class TestSQLiteContractCacheInit:
    """Test SQLiteContractCache initialization."""

    def test_creates_database_file(self, tmp_path: Path) -> None:
        """Test SQLiteContractCache creates database file."""
        db_path = str(tmp_path / "test.db")
        cache = SQLiteContractCache(db_path)

        assert Path(db_path).exists()
        cache.close()

    def test_creates_directory_if_missing(self, tmp_path: Path) -> None:
        """Test SQLiteContractCache creates parent directory."""
        db_path = str(tmp_path / "subdir" / "deep" / "test.db")
        cache = SQLiteContractCache(db_path)

        assert Path(db_path).exists()
        cache.close()

    def test_wal_mode_enabled(self, tmp_path: Path) -> None:
        """Test SQLiteContractCache enables WAL mode."""
        db_path = str(tmp_path / "test.db")
        cache = SQLiteContractCache(db_path)

        conn = cache._get_connection()
        cursor = conn.execute("PRAGMA journal_mode")
        mode = cursor.fetchone()[0]

        assert mode == "wal"
        cache.close()


class TestSQLiteContractCacheUpsertMany:
    """Test SQLiteContractCache.upsert_many method."""

    def test_inserts_single_description(self, tmp_path: Path) -> None:
        """Test upsert_many inserts a single description."""
        db_path = str(tmp_path / "test.db")
        cache = SQLiteContractCache(db_path)

        desc_dict = {
            "con_id": 265598,
            "symbol": "AAPL",
            "sec_type": "STK",
            "primary_exchange": "NASDAQ",
            "currency": "USD",
            "derivative_sec_types": ["OPT"],
            "description": "Apple Inc",
        }
        cache.upsert_many([desc_dict])

        results = cache.get_by_symbol_prefix("AAPL")
        assert len(results) == 1
        assert results[0]["symbol"] == "AAPL"
        cache.close()

    def test_inserts_multiple_descriptions(self, tmp_path: Path) -> None:
        """Test upsert_many inserts multiple descriptions."""
        db_path = str(tmp_path / "test.db")
        cache = SQLiteContractCache(db_path)

        descs = [
            {
                "con_id": 265598,
                "symbol": "AAPL",
                "sec_type": "STK",
                "primary_exchange": "NASDAQ",
                "currency": "USD",
                "derivative_sec_types": [],
                "description": "",
            },
            {
                "con_id": 272093,
                "symbol": "MSFT",
                "sec_type": "STK",
                "primary_exchange": "NASDAQ",
                "currency": "USD",
                "derivative_sec_types": [],
                "description": "",
            },
        ]
        cache.upsert_many(descs)

        assert len(cache.get_by_symbol_prefix("AAPL")) == 1
        assert len(cache.get_by_symbol_prefix("MSFT")) == 1
        cache.close()

    def test_upsert_replaces_existing(self, tmp_path: Path) -> None:
        """Test upsert_many replaces existing row on conflict."""
        db_path = str(tmp_path / "test.db")
        cache = SQLiteContractCache(db_path)

        # Insert original
        cache.upsert_many(
            [
                {
                    "con_id": 265598,
                    "symbol": "AAPL",
                    "sec_type": "STK",
                    "primary_exchange": "NASDAQ",
                    "currency": "USD",
                    "derivative_sec_types": [],
                    "description": "Original",
                }
            ]
        )

        # Upsert with updated description
        cache.upsert_many(
            [
                {
                    "con_id": 265598,
                    "symbol": "AAPL",
                    "sec_type": "STK",
                    "primary_exchange": "NASDAQ",
                    "currency": "USD",
                    "derivative_sec_types": ["OPT"],
                    "description": "Updated",
                }
            ]
        )

        results = cache.get_by_symbol_prefix("AAPL")
        assert len(results) == 1
        result = results[0]
        assert result["description"] == "Updated"
        assert result["derivative_sec_types"] == ["OPT"]
        cache.close()

    def test_upsert_empty_list_no_op(self, tmp_path: Path) -> None:
        """Test upsert_many with empty list is a no-op."""
        db_path = str(tmp_path / "test.db")
        cache = SQLiteContractCache(db_path)

        cache.upsert_many([])  # Should not raise

        cache.close()


class TestSQLiteContractCacheGetBySymbolPrefix:
    """Test SQLiteContractCache.get_by_symbol_prefix method."""

    def test_returns_matching_symbols(self, tmp_path: Path) -> None:
        """Test get_by_symbol_prefix returns all matching symbols."""
        db_path = str(tmp_path / "test.db")
        cache = SQLiteContractCache(db_path)

        cache.upsert_many(
            [
                {
                    "con_id": 1,
                    "symbol": "AAPL",
                    "sec_type": "STK",
                    "primary_exchange": "NASDAQ",
                    "currency": "USD",
                    "derivative_sec_types": [],
                    "description": "",
                },
                {
                    "con_id": 2,
                    "symbol": "AA",
                    "sec_type": "STK",
                    "primary_exchange": "NYSE",
                    "currency": "USD",
                    "derivative_sec_types": [],
                    "description": "",
                },
                {
                    "con_id": 3,
                    "symbol": "MSFT",
                    "sec_type": "STK",
                    "primary_exchange": "NASDAQ",
                    "currency": "USD",
                    "derivative_sec_types": [],
                    "description": "",
                },
            ]
        )

        results = cache.get_by_symbol_prefix("AA")
        symbols = [r["symbol"] for r in results]

        assert len(results) == 2
        assert "AAPL" in symbols
        assert "AA" in symbols
        cache.close()

    def test_returns_empty_list_for_no_match(self, tmp_path: Path) -> None:
        """Test get_by_symbol_prefix returns empty list when no match."""
        db_path = str(tmp_path / "test.db")
        cache = SQLiteContractCache(db_path)

        cache.upsert_many(
            [
                {
                    "con_id": 1,
                    "symbol": "AAPL",
                    "sec_type": "STK",
                    "primary_exchange": "NASDAQ",
                    "currency": "USD",
                    "derivative_sec_types": [],
                    "description": "",
                }
            ]
        )

        results = cache.get_by_symbol_prefix("GOOG")
        assert results == []
        cache.close()


# === ContractTracker Tests ===


@pytest.fixture
def tracker(tmp_path: Path) -> ContractTracker:
    """Create a ContractTracker with temp database."""
    db_path = str(tmp_path / "contracts.db")
    return ContractTracker(db_path=db_path)


class TestContractTrackerGetBySymbolPrefix:
    """Test ContractTracker.get_by_symbol_prefix lazy loading."""

    def test_returns_from_memory(self, tracker: ContractTracker) -> None:
        """Test get_by_symbol_prefix returns from in-memory cache."""
        tracker.upsert_descriptions(
            [
                _make_description(symbol="AAPL", con_id=1),
                _make_description(symbol="AA", con_id=2),
            ]
        )

        results = tracker.get_by_symbol_prefix("AA")

        assert len(results) == 2
        symbols = [r.contract.symbol for r in results]
        assert "AAPL" in symbols
        assert "AA" in symbols

    def test_loads_from_sqlite_on_memory_miss(self, tracker: ContractTracker) -> None:
        """Test get_by_symbol_prefix loads from SQLite when not in memory."""
        tracker._sqlite.upsert_many(
            [
                {
                    "con_id": 1,
                    "symbol": "AAPL",
                    "sec_type": "STK",
                    "primary_exchange": "NASDAQ",
                    "currency": "USD",
                    "derivative_sec_types": [],
                    "description": "",
                },
                {
                    "con_id": 2,
                    "symbol": "AA",
                    "sec_type": "STK",
                    "primary_exchange": "NYSE",
                    "currency": "USD",
                    "derivative_sec_types": [],
                    "description": "",
                },
            ]
        )

        results = tracker.get_by_symbol_prefix("AA")

        assert len(results) == 2
        assert 1 in tracker._descriptions
        assert 2 in tracker._descriptions

    def test_returns_empty_list_when_not_found(self, tracker: ContractTracker) -> None:
        """Test get_by_symbol_prefix returns empty list when not found."""
        results = tracker.get_by_symbol_prefix("UNKNOWN")
        assert results == []


class TestContractTrackerUpsertDescriptions:
    """Test ContractTracker.upsert_descriptions method."""

    def test_persists_to_sqlite_and_memory(self, tracker: ContractTracker) -> None:
        """Test upsert_descriptions persists to both SQLite and memory."""
        desc = _make_description(con_id=265598, symbol="AAPL")

        result = tracker.upsert_descriptions([desc])

        assert len(result) == 1
        assert result[0].con_id == 265598

        # In memory
        assert 265598 in tracker._descriptions

        # In SQLite (via fresh lookup)
        tracker._descriptions.clear()
        loaded = tracker.get_by_symbol_prefix("AAPL")
        assert len(loaded) == 1

    def test_skips_invalid_con_ids(self, tracker: ContractTracker) -> None:
        """Test upsert_descriptions skips entries with invalid conId."""
        desc = _make_description(con_id=0)  # Invalid

        result = tracker.upsert_descriptions([desc])

        assert len(result) == 0
        assert 0 not in tracker._descriptions

    def test_returns_empty_list_for_empty_input(self, tracker: ContractTracker) -> None:
        """Test upsert_descriptions returns empty list for empty input."""
        result = tracker.upsert_descriptions([])
        assert result == []


class TestContractTrackerUpsertDetails:
    """Test ContractTracker.upsert_details method."""

    def test_stores_in_memory_only(self, tracker: ContractTracker) -> None:
        """Test upsert_details stores in memory, NOT SQLite."""
        details = _make_details(con_id=265598)

        result = tracker.upsert_details(details)

        assert result.has_full_details is True
        assert 265598 in tracker._details

        # NOT in SQLite (details never persisted to SQLite)
        sqlite_result = tracker._sqlite.get_by_symbol_prefix("AAPL")
        assert sqlite_result == []

    def test_stores_overnight_hours(self, tracker: ContractTracker) -> None:
        """Test upsert_details stores overnight hours."""
        details = _make_details(con_id=265598)

        result = tracker.upsert_details(details, overnight_hours="20260114:1600-2000")

        assert result.overnight_hours == "20260114:1600-2000"


class TestContractTrackerGetFullDetails:
    """Test ContractTracker.get_full_details method."""

    def test_returns_details_from_memory(self, tracker: ContractTracker) -> None:
        """Test get_full_details returns from details cache."""
        details = _make_details(con_id=265598)
        tracker.upsert_details(details)

        result = tracker.get_details_from_cache(265598)

        assert result is not None
        assert result.has_full_details is True

    def test_does_not_return_descriptions(self, tracker: ContractTracker) -> None:
        """Test get_full_details does not return description-level entries."""
        desc = _make_description(con_id=265598)
        tracker.upsert_descriptions([desc])

        result = tracker.get_details_from_cache(265598)

        assert result is None  # Only descriptions in cache

    def test_returns_none_when_not_found(self, tracker: ContractTracker) -> None:
        """Test get_full_details returns None when not found."""
        result = tracker.get_details_from_cache(999999)
        assert result is None


class TestContractTrackerSessionManagement:
    """Test ContractTracker session management methods."""

    def test_clear_details_cache_clears_details_only(
        self, tracker: ContractTracker
    ) -> None:
        """Test clear_details_cache clears details but not descriptions."""
        desc = _make_description(con_id=1)
        details = _make_details(con_id=2)
        tracker.upsert_descriptions([desc])
        tracker.upsert_details(details)

        tracker.clear_details_cache()

        assert 1 in tracker._descriptions
        assert 2 not in tracker._details

    def test_reset_clears_all_memory(self, tracker: ContractTracker) -> None:
        """Test reset clears all in-memory caches."""
        desc = _make_description(con_id=1)
        details = _make_details(con_id=2)
        tracker.upsert_descriptions([desc])
        tracker.upsert_details(details)

        tracker.reset()

        assert len(tracker._descriptions) == 0
        assert len(tracker._details) == 0

    def test_reset_preserves_sqlite_data(self, tracker: ContractTracker) -> None:
        """Test reset preserves SQLite data."""
        desc = _make_description(con_id=265598, symbol="AAPL")
        tracker.upsert_descriptions([desc])

        tracker.reset()

        # SQLite data still available via lazy load
        results = tracker.get_by_symbol_prefix("AAPL")
        assert len(results) == 1
