"""Tests for ContractTracker with SQLite persistence.

Tests cover:
- SQLiteContractCache: CRUD operations, WAL mode, thread safety
- ContractTracker: Lazy loading (memory → SQLite → None), wiring interface, session management
"""

from pathlib import Path
from unittest.mock import MagicMock, PropertyMock

import pytest
from ibapi.contract import Contract, ContractDescription, ContractDetails

from trading_api.providers.tws.contract_tracker import (
    ContractTracker,
    SQLiteContractCache,
)
from trading_api.providers.tws.wiring_interfaces import IbSocketWiringInterface


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
def mock_ibsocket() -> MagicMock:
    """Create a mock IbSocketWiringInterface for ContractTracker tests.

    The mock returns incrementing req_ids starting from 1.
    """
    mock = MagicMock(spec=IbSocketWiringInterface)
    req_id_counter = [0]

    def get_next_req_id() -> int:
        req_id_counter[0] += 1
        return req_id_counter[0]

    type(mock).next_req_id = PropertyMock(side_effect=get_next_req_id)
    return mock


@pytest.fixture
def tracker(tmp_path: Path, mock_ibsocket: MagicMock) -> ContractTracker:
    """Create a ContractTracker with temp database and mock ibsocket."""
    db_path = str(tmp_path / "contracts.db")
    return ContractTracker(ibsocket=mock_ibsocket, db_path=db_path)


class TestContractTrackerWiring:
    """Test ContractTracker wiring interface integration."""

    def test_wires_to_ibsocket_on_init(
        self, tmp_path: Path, mock_ibsocket: MagicMock
    ) -> None:
        """ContractTracker calls wire_contract_tracker() during __init__."""
        db_path = str(tmp_path / "contracts.db")
        tracker = ContractTracker(ibsocket=mock_ibsocket, db_path=db_path)

        mock_ibsocket.wire_contract_tracker.assert_called_once_with(tracker)


class TestContractTrackerLoadCachedDescriptions:
    """Test ContractTracker._search_cache lazy loading."""

    def test_returns_from_memory_cache(self, tracker: ContractTracker) -> None:
        """Test _search_cache returns from in-memory _cached_contracts."""
        from trading_api.providers.tws.cached_contract import CachedContract

        # Directly populate memory cache via _cache_results
        desc1 = _make_description(symbol="AAPL", con_id=1)
        desc2 = _make_description(symbol="AA", con_id=2)
        cached1 = CachedContract.from_contract_description(desc1)
        cached2 = CachedContract.from_contract_description(desc2)
        tracker._cache_results([cached1, cached2])

        results = tracker._search_cache("AA")

        assert len(results) == 2
        symbols = [r.contract.symbol for r in results]
        assert "AAPL" in symbols
        assert "AA" in symbols

    def test_loads_from_sqlite_on_memory_miss(self, tracker: ContractTracker) -> None:
        """Test _search_cache loads from SQLite when not in memory."""
        # Directly populate SQLite (bypass memory cache)
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

        results = tracker._search_cache("AA")

        assert len(results) == 2
        # Verify loaded into _cached_contracts (ticker-keyed)
        assert "NASDAQ:AAPL" in tracker._cached_contracts
        assert "NYSE:AA" in tracker._cached_contracts

    def test_returns_empty_list_when_not_found(self, tracker: ContractTracker) -> None:
        """Test _search_cache returns empty list when not found."""
        results = tracker._search_cache("UNKNOWN")
        assert results == []


class TestContractTrackerCacheResults:
    """Test ContractTracker._cache_results method."""

    def test_persists_to_sqlite_and_memory(self, tracker: ContractTracker) -> None:
        """Test _cache_results persists to both SQLite and in-memory cache."""
        from trading_api.providers.tws.cached_contract import CachedContract

        desc = _make_description(con_id=265598, symbol="AAPL")
        cached = CachedContract.from_contract_description(desc)

        tracker._cache_results([cached])

        # In memory (_cached_contracts is ticker-keyed)
        assert "NASDAQ:AAPL" in tracker._cached_contracts

        # In SQLite (via fresh lookup after clearing memory)
        tracker._cached_contracts.clear()
        loaded = tracker._search_cache("AAPL")
        assert len(loaded) == 1

    def test_skips_duplicate_tickers(self, tracker: ContractTracker) -> None:
        """Test _cache_results skips entries already in cache."""
        from trading_api.providers.tws.cached_contract import CachedContract

        desc = _make_description(con_id=265598, symbol="AAPL")
        cached = CachedContract.from_contract_description(desc)

        # First call caches
        tracker._cache_results([cached])
        assert "NASDAQ:AAPL" in tracker._cached_contracts

        # Second call with same ticker should not overwrite
        desc2 = _make_description(con_id=265598, symbol="AAPL")
        cached2 = CachedContract.from_contract_description(desc2)
        tracker._cache_results([cached2])

        # Still only one entry
        assert len([k for k in tracker._cached_contracts if "AAPL" in k]) == 1


class TestContractTrackerUpdateDescriptions:
    """Test ContractTracker.update_descriptions wiring callback."""

    def test_filters_invalid_con_ids(
        self, tracker: ContractTracker, mock_ibsocket: MagicMock
    ) -> None:
        """Test update_descriptions skips entries with conId <= 0."""
        import asyncio

        # Set up a pending future to receive results
        loop = asyncio.new_event_loop()
        future: asyncio.Future[list] = loop.create_future()
        req_id = 1

        with tracker.tracker_lock:
            tracker._pending_descriptions[req_id] = {"test": (loop, future)}

        # Call update_descriptions with invalid conId
        invalid_desc = _make_description(con_id=0)
        valid_desc = _make_description(con_id=265598, symbol="AAPL")

        tracker.update_descriptions(req_id, [invalid_desc, valid_desc])

        # Process pending callbacks
        loop.run_until_complete(asyncio.sleep(0.01))

        # Future should be set with only valid result
        assert future.done()
        result = future.result()
        assert len(result) == 1
        assert result[0].contract.conId == 265598

        loop.close()


class TestContractTrackerUpdateDetails:
    """Test ContractTracker.update_details wiring callback."""

    def test_accumulates_details_by_req_id(self, tracker: ContractTracker) -> None:
        """Test update_details accumulates details in _details dict."""
        details1 = _make_details(con_id=265598, symbol="AAPL")
        details2 = _make_details(con_id=272093, symbol="MSFT")

        req_id = 1
        tracker.update_details(req_id, details1)
        tracker.update_details(req_id, details2)

        assert req_id in tracker._details
        assert len(tracker._details[req_id]) == 2


class TestContractTrackerFlagDetailsComplete:
    """Test ContractTracker.flag_details_complete wiring callback."""

    def test_resolves_pending_future(self, tracker: ContractTracker) -> None:
        """Test flag_details_complete resolves pending futures."""
        import asyncio

        loop = asyncio.new_event_loop()
        future: asyncio.Future[list] = loop.create_future()
        req_id = 1

        # Add pending details hook
        with tracker.tracker_lock:
            tracker._pending_details[req_id] = {"test": (loop, future)}

        # Add some details first
        details = _make_details(con_id=265598)
        tracker.update_details(req_id, details)

        # Flag complete
        tracker.flag_details_complete(req_id)

        # Process callbacks
        loop.run_until_complete(asyncio.sleep(0.01))

        assert future.done()
        result = future.result()
        assert len(result) == 1
        assert result[0].contract.conId == 265598

        loop.close()


class TestContractTrackerSessionManagement:
    """Test ContractTracker session management methods."""

    def test_reset_clears_all_memory(self, tracker: ContractTracker) -> None:
        """Test reset clears all in-memory caches."""
        from trading_api.providers.tws.cached_contract import CachedContract

        desc = _make_description(con_id=1)
        cached = CachedContract.from_contract_description(desc)
        tracker._cache_results([cached])

        # Also add to details
        details = _make_details(con_id=2)
        tracker.update_details(req_id=1, details=details)

        tracker.reset()

        assert len(tracker._cached_contracts) == 0
        assert len(tracker._details) == 0
        assert len(tracker._descriptions) == 0

    def test_reset_preserves_sqlite_data(self, tracker: ContractTracker) -> None:
        """Test reset preserves SQLite data."""
        from trading_api.providers.tws.cached_contract import CachedContract

        desc = _make_description(con_id=265598, symbol="AAPL")
        cached = CachedContract.from_contract_description(desc)
        tracker._cache_results([cached])

        tracker.reset()

        # SQLite data still available via lazy load
        results = tracker._search_cache("AAPL")
        assert len(results) == 1
