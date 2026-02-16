"""Test fixtures for datafeed module tests.

Provides MockDatafeedProvider to avoid real TWS Gateway connections during tests.
Overrides the apps fixture to inject mock provider instead of real TWSDatafeedProvider.
"""

from collections.abc import Generator
from datetime import datetime
from itertools import count
from pathlib import Path
from typing import Any, Awaitable, Callable

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from trading_api.app_factory import ModularApp
from trading_api.capabilities.datafeed import DatafeedCapability
from trading_api.datastores import create_memory_datastore
from trading_api.models.common import CapabilitySpec, ProviderConfig
from trading_api.models.exceptions import TradingApiException
from trading_api.models.market import (
    Bar,
    QuoteData,
    Resolution,
    SearchSymbolResultItem,
    SymbolInfo,
)
from trading_api.shared import FastWSAdapter, ModuleRegistry, Provider


class MockDatafeedProvider(Provider, DatafeedCapability):
    """Mock datafeed provider for testing.

    Simulates TWS responses without real socket connections.
    Includes call tracking for test assertions and configurable return values.

    Attributes:
        calls: Dict tracking method calls with their arguments for assertions.
        return_values: Dict to configure mock return values per method.
        _subscriptions: Active subscriptions with their callbacks.
        _error_callbacks: Error callbacks for triggering error scenarios in tests.
    """

    def __init__(self) -> None:
        self._subscription_counter = count(start=1)
        self._subscriptions: dict[str, Callable[..., Awaitable[None]]] = {}
        self._error_callbacks: dict[
            str, Callable[[TradingApiException], Awaitable[None]]
        ] = {}

        # Call tracking for assertions
        self.calls: dict[str, list[dict[str, Any]]] = {
            "search_symbols": [],
            "get_symbol_info": [],
            "get_historical_bars": [],
            "get_quotes_snapshot": [],
            "subscribe_realtime_bars": [],
            "subscribe_market_data": [],
            "unsubscribe_realtime_bars": [],
            "unsubscribe_market_data": [],
        }

        # Configurable return values (defaults set in methods)
        self.return_values: dict[str, Any] = {}

        # Track if methods should raise exceptions
        self.raise_exception: dict[str, Exception | None] = {}

    def reset(self) -> None:
        """Reset all call tracking and return values."""
        for key in self.calls:
            self.calls[key] = []
        self.return_values = {}
        self.raise_exception = {}
        self._subscriptions.clear()
        self._error_callbacks.clear()

    @classmethod
    def provider_dir(cls) -> Path:
        return Path(__file__).parent

    @property
    def name(self) -> str:
        return "mock_tws"

    @classmethod
    def capabilities(cls) -> list[CapabilitySpec]:
        return [CapabilitySpec(name="datafeed")]

    @property
    def config(self) -> ProviderConfig:
        """Return mock config."""

        class MockConfig(ProviderConfig):
            pass

        return MockConfig()

    async def search_symbols(
        self, pattern: str, **kwargs: Any
    ) -> list[SearchSymbolResultItem]:
        """Return mock search results."""
        self.calls["search_symbols"].append({"pattern": pattern, **kwargs})

        if exc := self.raise_exception.get("search_symbols"):
            raise exc

        if "search_symbols" in self.return_values:
            assert isinstance(self.return_values["search_symbols"], list)
            assert all(
                isinstance(item, SearchSymbolResultItem)
                for item in self.return_values["search_symbols"]
            )
            return self.return_values["search_symbols"]

        return [
            SearchSymbolResultItem(
                symbol="AAPL",
                exchange="NASDAQ",
                type="stock",
                description="Apple Inc.",
                ticker="AAPL:NASDAQ",
            )
        ]

    async def get_symbol_info(self, ticker_name: str, **kwargs: Any) -> SymbolInfo:
        """Return mock symbol info."""
        self.calls["get_symbol_info"].append({"ticker_name": ticker_name, **kwargs})

        if exc := self.raise_exception.get("get_symbol_info"):
            raise exc

        if "get_symbol_info" in self.return_values:
            # Allow None return for testing not-found scenarios
            val = self.return_values["get_symbol_info"]
            if val is None:
                # Return a placeholder - service handles None case
                raise KeyError("Symbol not found")  # Will be caught by service
            assert isinstance(val, SymbolInfo)
            return val

        parts = ticker_name.split(":")
        symbol = parts[0] if parts else ticker_name
        exchange = parts[1] if len(parts) > 1 else "SMART"
        return SymbolInfo(
            name=symbol,
            ticker=ticker_name,
            description=f"Mock {symbol}",
            type="stock",
            exchange=exchange,
            listed_exchange=exchange,
            session="0930-1600",
            timezone="America/New_York",
            format="price",
            minmov=1,
            pricescale=100,
            has_intraday=True,
            has_daily=True,
            supported_resolutions=[
                Resolution.MIN_1,
                Resolution.MIN_5,
                Resolution.MIN_15,
                Resolution.MIN_30,
                Resolution.HOUR_1,
                Resolution.DAY_1,
                Resolution.WEEK_1,
                Resolution.MONTH_1,
            ],
            volume_precision=0,
            data_status="streaming",
        )

    async def get_historical_bars(
        self,
        ticker_name: str,
        start_time: datetime,
        end_time: datetime,
        resolution: Resolution,
        **kwargs: Any,
    ) -> list[Bar]:
        """Return mock historical bars."""
        self.calls["get_historical_bars"].append(
            {
                "ticker_name": ticker_name,
                "start_time": start_time,
                "end_time": end_time,
                "resolution": resolution,
                **kwargs,
            }
        )

        if exc := self.raise_exception.get("get_historical_bars"):
            raise exc

        if "get_historical_bars" in self.return_values:
            assert isinstance(self.return_values["get_historical_bars"], list)
            assert all(
                isinstance(item, Bar)
                for item in self.return_values["get_historical_bars"]
            )
            return self.return_values["get_historical_bars"]

        return [
            Bar(
                time=1700000000000,
                open=150.0,
                high=151.0,
                low=149.0,
                close=150.5,
                volume=1000,
                count=10,
            )
        ]

    async def get_quotes_snapshot(
        self, ticker_names: list[str], **kwargs: Any
    ) -> list[QuoteData]:
        """Return mock quote snapshots."""
        self.calls["get_quotes_snapshot"].append(
            {
                "ticker_names": ticker_names,
                **kwargs,
            }
        )

        if exc := self.raise_exception.get("get_quotes_snapshot"):
            raise exc

        if "get_quotes_snapshot" in self.return_values:
            assert isinstance(self.return_values["get_quotes_snapshot"], list)
            assert all(
                isinstance(item, QuoteData)
                for item in self.return_values["get_quotes_snapshot"]
            )
            return self.return_values["get_quotes_snapshot"]

        return [
            QuoteData(s="ok", n=ticker_name, v={"bid": 150.0, "ask": 150.1})
            for ticker_name in ticker_names
        ]

    async def subscribe_realtime_bars(
        self,
        ticker_name: str,
        resolution: Resolution,
        callback: Callable[[Bar], Awaitable[None]],
        on_error: Callable[[TradingApiException], Awaitable[None]] | None = None,
        **kwargs: Any,
    ) -> str:
        """Subscribe to mock realtime bars."""
        sub_id = str(next(self._subscription_counter))
        self.calls["subscribe_realtime_bars"].append(
            {
                "ticker_name": ticker_name,
                "resolution": resolution,
                "sub_id": sub_id,
                **kwargs,
            }
        )
        self._subscriptions[sub_id] = callback
        if on_error:
            self._error_callbacks[sub_id] = on_error
        return sub_id

    async def subscribe_market_data(
        self,
        ticker_name: str,
        callback: Callable[[QuoteData], Awaitable[None]],
        on_error: Callable[[TradingApiException], Awaitable[None]] | None = None,
        **kwargs: Any,
    ) -> str:
        """Subscribe to mock market data."""
        sub_id = str(next(self._subscription_counter))
        self.calls["subscribe_market_data"].append(
            {
                "ticker_name": ticker_name,
                "sub_id": sub_id,
                **kwargs,
            }
        )
        self._subscriptions[sub_id] = callback
        if on_error:
            self._error_callbacks[sub_id] = on_error
        return sub_id

    def unsubscribe_realtime_bars(self, subscription_id: str) -> None:
        """Unsubscribe from mock realtime bars."""
        self.calls["unsubscribe_realtime_bars"].append(
            {
                "subscription_id": subscription_id,
            }
        )
        self._subscriptions.pop(subscription_id, None)
        self._error_callbacks.pop(subscription_id, None)

    def unsubscribe_market_data(self, subscription_id: str) -> None:
        """Unsubscribe from mock market data."""
        self.calls["unsubscribe_market_data"].append(
            {
                "subscription_id": subscription_id,
            }
        )
        self._subscriptions.pop(subscription_id, None)
        self._error_callbacks.pop(subscription_id, None)

    def shutdown(self) -> None:
        """Cleanup mock provider."""
        self._subscriptions.clear()
        self._error_callbacks.clear()

    # ========================================================================
    # Test helper methods - for triggering callbacks in tests
    # ========================================================================

    async def trigger_bar_update(self, subscription_id: str, bar: Bar) -> None:
        """Trigger a bar update callback for testing."""
        if callback := self._subscriptions.get(subscription_id):
            await callback(bar)

    async def trigger_quote_update(
        self, subscription_id: str, quote: QuoteData
    ) -> None:
        """Trigger a quote update callback for testing."""
        if callback := self._subscriptions.get(subscription_id):
            await callback(quote)

    async def trigger_error(
        self, subscription_id: str, exc: TradingApiException
    ) -> None:
        """Trigger an error callback for testing error handling."""
        if on_error := self._error_callbacks.get(subscription_id):
            await on_error(exc)


# ============================================================================
# Application Fixtures (Override to inject MockDatafeedProvider)
# ============================================================================


@pytest.fixture(scope="module")
def mock_datafeed_provider() -> MockDatafeedProvider:
    """Create mock datafeed provider for tests."""
    return MockDatafeedProvider()


@pytest.fixture(scope="module")
def apps(mock_datafeed_provider: MockDatafeedProvider) -> ModularApp:
    """Override apps fixture to inject mock provider instead of real TWSDatafeedProvider.

    This prevents tests from connecting to real TWS Gateway.
    Only loads datafeed module to avoid needing mock providers for other modules.
    """
    from trading_api.shared import ModuleApp, settings

    # Create module registry for test isolation
    module_registry = ModuleRegistry(Path(__file__).parents[2])

    # Auto-discover only datafeed module
    module_registry.auto_discover(enabled_modules=["datafeed"])

    # Get only datafeed module with mock provider injected
    datastore = create_memory_datastore()
    enabled_modules = module_registry.get_modules(
        providers=[mock_datafeed_provider],  # Inject mock provider
        datastores=[datastore],
    )

    # Create ModularApp without lifespan (simpler for tests)
    # Use __init__ directly since we're injecting dependencies manually
    app = ModularApp(
        base_url=settings.API_PREFIX,
        enabled_modules=["datafeed"],
        title="Trading API (Test)",
        version="1.0.0",
    )

    # Manually set runtime state (normally done in build_modules)
    app._modules = enabled_modules
    app._modules_apps = [ModuleApp(module) for module in enabled_modules]

    # Mount module routes (normally done in _start)
    for module_app in app._modules_apps:
        for api_app in module_app.api_versions:
            mount_path = f"{app.base_url}/{api_app.version}/{module_app.module.name}"
            app.mount(mount_path, api_app)

        # Start module
        module_app.start()

    return app


@pytest.fixture(scope="module")
def app(apps: ModularApp) -> FastAPI:
    """FastAPI application instance."""
    return apps


@pytest.fixture(scope="module")
def ws_apps(apps: ModularApp) -> list[FastWSAdapter]:
    """FastWSAdapter application instances."""
    return [
        ws_app for module_app in apps.modules_apps for ws_app in module_app.ws_versions
    ]


@pytest.fixture(scope="module")
def ws_app(ws_apps: list[FastWSAdapter]) -> FastWSAdapter | None:
    """First FastWSAdapter application instance."""
    return ws_apps[0] if ws_apps else None


@pytest.fixture
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    """Sync test client for WebSocket tests."""
    with TestClient(app) as c:
        yield c
