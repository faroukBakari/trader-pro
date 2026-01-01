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

from trading_api.app_factory import AppFactory, ModularApp
from trading_api.capabilities.datafeed import DatafeedCapability
from trading_api.models.common import CapabilitySpec, ProviderConfig
from trading_api.models.exceptions import TradingApiException
from trading_api.models.market import (
    Bar,
    QuoteData,
    Resolution,
    SearchSymbolResultItem,
    SymbolInfo,
)
from trading_api.shared import FastWSAdapter, Provider


class MockDatafeedProvider(Provider, DatafeedCapability):
    """Mock datafeed provider for WebSocket integration tests.

    Simulates TWS responses without real socket connections.
    """

    def __init__(self) -> None:
        self._subscription_counter = count(start=1)
        self._subscriptions: dict[str, Callable[..., Awaitable[None]]] = {}

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
        return [
            QuoteData(s="ok", n=ticker_name, v={"bid": 150.0, "ask": 150.1})
            for ticker_name in ticker_names
        ]

    def subscribe_realtime_bars(
        self,
        ticker_name: str,
        resolution: Resolution,
        callback: Callable[[Bar], Awaitable[None]],
        on_error: Callable[[TradingApiException], Awaitable[None]] | None = None,
        **kwargs: Any,
    ) -> str:
        """Subscribe to mock realtime bars."""
        sub_id = str(next(self._subscription_counter))
        self._subscriptions[sub_id] = callback
        return sub_id

    def subscribe_market_data(
        self,
        ticker_name: str,
        callback: Callable[[QuoteData], Awaitable[None]],
        on_error: Callable[[TradingApiException], Awaitable[None]] | None = None,
        **kwargs: Any,
    ) -> str:
        """Subscribe to mock market data."""
        sub_id = str(next(self._subscription_counter))
        self._subscriptions[sub_id] = callback
        return sub_id

    def unsubscribe_realtime_bars(self, subscription_id: str) -> None:
        """Unsubscribe from mock realtime bars."""
        self._subscriptions.pop(subscription_id, None)

    def unsubscribe_market_data(self, subscription_id: str) -> None:
        """Unsubscribe from mock market data."""
        self._subscriptions.pop(subscription_id, None)

    def shutdown(self) -> None:
        """Cleanup mock provider."""
        self._subscriptions.clear()


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
    factory = AppFactory()

    # Clear and auto-discover modules only (not providers)
    factory.module_registry.clear()
    factory.module_registry.auto_discover()

    # Get only datafeed module with mock provider injected
    enabled_modules = factory.module_registry.get_modules(
        module_names=["datafeed"],  # Only datafeed module
        providers=[mock_datafeed_provider],  # Inject mock provider
    )

    # Create ModularApp without lifespan (simpler for tests)
    modular_app = ModularApp(
        modules=enabled_modules,
        base_url="/api",
        title="Trading API (Test)",
        version="1.0.0",
    )

    return modular_app


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
