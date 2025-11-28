"""Test fixtures for datafeed module tests.

Provides MockDatafeedProvider to avoid real TWS Gateway connections during tests.
Overrides the apps fixture to inject mock provider instead of real TWSProvider.
"""

import asyncio
from collections.abc import Generator
from itertools import count
from pathlib import Path
from typing import Any, Awaitable, Callable

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from trading_api.app_factory import AppFactory, ModularApp
from trading_api.models.common import CapabilitySpec, ProviderConfig
from trading_api.models.market import (
    Bar,
    QuoteData,
    SearchSymbolResultItem,
    SymbolInfo,
    TimeFrame,
)
from trading_api.providers.base import Provider
from trading_api.providers.capabilities.datafeed import DatafeedCapability
from trading_api.shared import FastWSAdapter


class MockDatafeedProvider(Provider, DatafeedCapability):
    """Mock datafeed provider for WebSocket integration tests.

    Simulates TWS responses without real socket connections.
    """

    def __init__(self) -> None:
        self._subscription_counter = count(start=1)
        self._subscriptions: dict[int, Callable[..., Awaitable[None]]] = {}

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

    async def get_symbol_info(
        self, symbol: str, exchange: str | None = None, **kwargs: Any
    ) -> SymbolInfo:
        """Return mock symbol info."""
        return SymbolInfo(
            name=symbol,
            ticker=f"{symbol}:{exchange or 'SMART'}",
            description=f"Mock {symbol}",
            type="stock",
            exchange=exchange or "SMART",
            listed_exchange=exchange or "SMART",
            session="0930-1600",
            timezone="America/New_York",
            format="price",
            minmov=1,
            pricescale=100,
            has_intraday=True,
            has_daily=True,
            supported_resolutions=["1", "5", "15", "30", "60", "1D", "1W", "1M"],
            volume_precision=0,
            data_status="streaming",
        )

    async def get_historical_bars(
        self,
        symbol: str,
        start_time: Any,
        end_time: Any,
        resolution: TimeFrame,
        exchange: str | None = None,
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
        self, symbols: list[str], exchange: str | None = None, **kwargs: Any
    ) -> list[QuoteData]:
        """Return mock quote snapshots."""
        return [
            QuoteData(s="ok", n=symbol, v={"bid": 150.0, "ask": 150.1})
            for symbol in symbols
        ]

    def subscribe_realtime_bars(
        self,
        symbol: str,
        callback: Callable[[Bar], Awaitable[None]],
        exchange: str | None = None,
        **kwargs: Any,
    ) -> int:
        """Subscribe to mock realtime bars."""
        sub_id = next(self._subscription_counter)
        self._subscriptions[sub_id] = callback
        return sub_id

    def subscribe_market_data(
        self,
        symbols: list[str],
        callback: Callable[[QuoteData], Awaitable[None]],
        exchange: str | None = None,
        **kwargs: Any,
    ) -> list[int]:
        """Subscribe to mock market data."""
        sub_ids = []
        for _ in symbols:
            sub_id = next(self._subscription_counter)
            self._subscriptions[sub_id] = callback
            sub_ids.append(sub_id)
        return sub_ids

    def unsubscribe_realtime_bars(self, subscription_id: int) -> None:
        """Unsubscribe from mock realtime bars."""
        self._subscriptions.pop(subscription_id, None)

    def unsubscribe_market_data(self, subscription_ids: list[int]) -> None:
        """Unsubscribe from mock market data."""
        for sub_id in subscription_ids:
            self._subscriptions.pop(sub_id, None)

    def shutdown(self) -> None:
        """Cleanup mock provider."""
        self._subscriptions.clear()


# ============================================================================
# Event Loop Fixture (Module-Scoped for Async Fixtures)
# ============================================================================


@pytest.fixture(scope="module")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for module-scoped async fixtures."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop

    try:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.run_until_complete(loop.shutdown_default_executor())
    except AttributeError:
        pass
    finally:
        loop.close()


# ============================================================================
# Application Fixtures (Override to inject MockDatafeedProvider)
# ============================================================================


@pytest.fixture(scope="module")
def mock_datafeed_provider() -> MockDatafeedProvider:
    """Create mock datafeed provider for tests."""
    return MockDatafeedProvider()


@pytest.fixture(scope="module")
async def apps(mock_datafeed_provider: MockDatafeedProvider) -> ModularApp:
    """Override apps fixture to inject mock provider instead of real TWSProvider.

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
