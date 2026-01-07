"""Test fixtures for integration tests.

Creates full-stack application with ALL modules enabled.
Provides session-scoped multi-process service fixtures for client testing.
Provides session-scoped module isolation fixtures for fast test execution.
"""

import multiprocessing
import os
import sys
import time
from collections.abc import AsyncGenerator
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient
from httpx import AsyncClient
from jose import jwt

from trading_api.app_factory import ModularApp
from trading_api.capabilities.auth import AuthCapability

# Import BrokerService for broker_provider fixture
from trading_api.capabilities.broker import BrokerCapability
from trading_api.capabilities.datafeed import DatafeedCapability
from trading_api.models.common import CapabilitySpec, ProviderConfig
from trading_api.models.exceptions import TradingApiException
from trading_api.models.market import (
    Bar,
    QuoteData,
    QuoteValues,
    Resolution,
    SearchSymbolResultItem,
    SymbolInfo,
)
from trading_api.modules.broker.service import BrokerService

# Import FakeBrokerProvider for integration tests (needs full broker functionality)
from trading_api.providers.fakebroker import FakeBrokerProvider
from trading_api.shared import FastWSAdapter, Provider
from trading_api.shared.config import Settings

# Add backend scripts to path for backend_manager imports
backend_scripts_dir = Path(__file__).parent.parent.parent / "scripts"
if str(backend_scripts_dir) not in sys.path:
    sys.path.insert(0, str(backend_scripts_dir))


# ============================================================================
# Mock Providers (for integration tests)
# ============================================================================


class MockAuthProvider(Provider, AuthCapability):
    """Mock provider for integration tests - simulates auth capability."""

    @classmethod
    def provider_dir(cls) -> Path:
        return Path(__file__).parent

    @property
    def name(self) -> str:
        return "mock_auth"

    @property
    def config(self) -> ProviderConfig:
        return ProviderConfig()

    @classmethod
    def capabilities(cls) -> list[CapabilitySpec]:
        return [CapabilitySpec(name="auth")]

    async def verify_token(self, token: str) -> dict[str, Any]:
        """Mock token verification - always succeeds for testing."""
        return {
            "sub": "test-user-id",
            "email": "test@example.com",
            "name": "Test User",
            "picture": "https://example.com/avatar.jpg",
            "email_verified": True,
        }


class MockDatafeedProvider(Provider, DatafeedCapability):
    """Mock provider for integration tests - simulates datafeed capability."""

    def __init__(self) -> None:
        self._subscriptions: dict[str, str] = {}
        self._next_sub_id = 1

    @classmethod
    def provider_dir(cls) -> Path:
        return Path(__file__).parent

    @property
    def name(self) -> str:
        return "mock_datafeed"

    @property
    def config(self) -> ProviderConfig:
        return ProviderConfig()

    @classmethod
    def capabilities(cls) -> list[CapabilitySpec]:
        return [CapabilitySpec(name="datafeed")]

    async def search_symbols(
        self, pattern: str, **kwargs: Any
    ) -> list[SearchSymbolResultItem]:
        """Return mock search results."""
        return [
            SearchSymbolResultItem(
                symbol=pattern.upper(),
                description=f"Mock {pattern} stock",
                exchange="MOCK",
                ticker=pattern.upper(),
                type="stock",
            )
        ]

    async def get_symbol_info(self, ticker_name: str, **kwargs: Any) -> SymbolInfo:
        """Return mock symbol info."""
        return SymbolInfo(
            name=ticker_name,
            description=f"Mock {ticker_name} stock",
            exchange="MOCK",
            listed_exchange="MOCK",
            ticker=ticker_name,
            type="stock",
            session="0930-1600",
            timezone="America/New_York",
            minmov=1,
            pricescale=100,
            format="price",
            has_intraday=True,
            has_daily=True,
            supported_resolutions=[
                Resolution.MIN_1,
                Resolution.MIN_5,
                Resolution.MIN_15,
                Resolution.HOUR_1,
                Resolution.DAY_1,
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
                time=int(start_time.timestamp()),
                open=100.0,
                high=105.0,
                low=99.0,
                close=103.0,
                volume=10000,
                count=1,
            )
        ]

    async def get_quotes_snapshot(
        self, ticker_names: list[str], **kwargs: Any
    ) -> list[QuoteData]:
        """Return mock quotes snapshot."""
        return [
            QuoteData(
                s="ok",
                n=ticker_name,
                v=QuoteValues(
                    lp=100.02,
                    ask=100.05,
                    bid=100.0,
                    spread=0.05,
                    open_price=99.5,
                    high_price=101.0,
                    low_price=99.0,
                    prev_close_price=99.8,
                    volume=10000,
                    ch=0.22,
                    chp=0.22,
                    short_name=ticker_name,
                    exchange="MOCK",
                    description=f"Mock {ticker_name}",
                    original_name=ticker_name,
                ),
            )
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
        """Subscribe to realtime bars (mock - no actual streaming)."""
        sub_id = str(self._next_sub_id)
        self._next_sub_id += 1
        self._subscriptions[sub_id] = ticker_name
        return sub_id

    async def subscribe_market_data(
        self,
        ticker_name: str,
        callback: Callable[[QuoteData], Awaitable[None]],
        on_error: Callable[[TradingApiException], Awaitable[None]] | None = None,
        **kwargs: Any,
    ) -> str:
        """Subscribe to market data (mock - no actual streaming)."""
        sub_id = str(self._next_sub_id)
        self._next_sub_id += 1
        self._subscriptions[sub_id] = ticker_name
        return sub_id

    def unsubscribe_realtime_bars(self, subscription_id: str) -> None:
        """Unsubscribe from realtime bars."""
        self._subscriptions.pop(subscription_id, None)

    def unsubscribe_market_data(self, subscription_id: str) -> None:
        """Unsubscribe from market data."""
        self._subscriptions.pop(subscription_id, None)


# ============================================================================
# Authentication Fixtures
# ============================================================================


@pytest.fixture
def valid_jwt_token() -> str:
    """Generate a valid JWT token for authentication."""
    settings = Settings()
    payload = {
        "user_id": "TEST-USER-001",
        "email": "test@example.com",
        "full_name": "Test User",
        "picture": "https://example.com/avatar.jpg",
        "exp": int(time.time()) + 300,
        "iat": int(time.time()),
    }
    return jwt.encode(
        payload, settings.jwt_private_key, algorithm=settings.JWT_ALGORITHM
    )


@pytest.fixture
def auth_cookies(valid_jwt_token: str) -> dict[str, str]:
    """Generate authentication cookies for testing."""
    return {"access_token": valid_jwt_token}


# ============================================================================
# Module Isolation Fixtures (Session-Scoped for Performance)
# ============================================================================


@pytest.fixture(scope="session")
async def datafeed_only_app() -> ModularApp:
    """Session-scoped datafeed-only app for isolation tests."""
    from trading_api.app_factory import AppFactory

    factory = AppFactory()
    return await factory.create_app(enabled_module_names=["datafeed"])


@pytest.fixture(scope="session")
async def broker_only_app() -> ModularApp:
    """Session-scoped broker-only app for isolation tests."""
    from trading_api.app_factory import AppFactory

    factory = AppFactory()
    return await factory.create_app(enabled_module_names=["broker"])


@pytest.fixture(scope="session")
async def all_modules_app() -> ModularApp:
    """Session-scoped app with all modules for isolation tests."""
    from trading_api.app_factory import AppFactory

    factory = AppFactory()
    return await factory.create_app(enabled_module_names=None)


@pytest.fixture(scope="session")
async def no_modules_app() -> ModularApp:
    """Session-scoped app with no modules (shared infrastructure only)."""
    from trading_api.app_factory import AppFactory

    factory = AppFactory()
    return await factory.create_app(enabled_module_names=[])


# ============================================================================
# Multi-Process Service Fixtures
# ============================================================================


def run_service(module_name: str, port: int) -> None:
    """Run a single module as a separate service.

    Args:
        module_name: Name of the module to run (broker or datafeed)
        port: Port to bind the service to
    """
    # Set environment variable to enable only this module
    os.environ["ENABLED_MODULES"] = module_name

    # Run uvicorn server
    uvicorn.run(
        "trading_api.main:app",
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False,
    )


def wait_for_service_sync(base_url: str, max_attempts: int = 30) -> bool:
    """Wait for a service to become available (synchronous version).

    Args:
        base_url: Base URL of the service
        max_attempts: Maximum number of connection attempts

    Returns:
        True if service is available, False otherwise
    """
    for _ in range(max_attempts):
        try:
            # Try broker first, then datafeed if broker fails
            response = httpx.get(f"{base_url}/api/v1/broker/health", timeout=0.2)
            if response.status_code == 200:
                return True
            response = httpx.get(f"{base_url}/api/v1/datafeed/health", timeout=0.2)
            if response.status_code == 200:
                return True
        except (httpx.ConnectError, httpx.RemoteProtocolError, httpx.ReadTimeout):
            time.sleep(0.2)
    return False


@pytest.fixture(scope="module")
async def apps() -> ModularApp:
    """Full application with all modules enabled (shared per test module).

    Uses MockDatafeedProvider instead of real TWS provider to avoid
    external dependencies in integration tests.
    """
    from trading_api.app_factory import AppFactory

    factory = AppFactory()

    # Clear and re-discover modules only (not providers)
    factory.module_registry.clear()
    factory.module_registry.auto_discover()

    # Register mock providers instead of auto-discovering real providers
    factory.provider_registry.clear()
    factory.provider_registry.register(MockDatafeedProvider, "mock_datafeed")
    factory.provider_registry.register(MockAuthProvider, "mock_auth")
    factory.provider_registry.register(FakeBrokerProvider, "fake_broker")

    # Resolve required capabilities
    required_capabilities = factory._resolve_capabilities(None)

    # Get provider instances (will use our mock)
    required_providers = await factory.provider_registry.get_providers(
        required_capabilities
    )

    # Instantiate modules with mock providers
    enabled_modules = factory.module_registry.get_modules(
        module_names=None, providers=required_providers
    )

    # Create base URL
    base_url = "/api"

    # Create ModularApp without lifespan (tests handle their own lifecycle)
    modular_app = ModularApp(
        modules=enabled_modules,
        base_url=base_url,
        title="Trading API (Test)",
        description="Test instance with mock providers",
        version="1.0.0",
    )

    # Add CORS middleware (same as production)
    from fastapi.middleware.cors import CORSMiddleware

    modular_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return modular_app


@pytest.fixture(scope="module")
def broker_provider(apps: ModularApp) -> BrokerCapability:
    """Get the broker provider from the apps fixture.

    Args:
        apps: The full modular application with all modules

    Returns:
        BrokerCapability: The broker provider (e.g., FakeBrokerProvider)
    """
    # Find the broker module app and extract the provider
    for module_app in apps.modules_apps:
        if isinstance(module_app.module.service, BrokerService):
            return module_app.module.service.broker_provider

    raise RuntimeError("BrokerService not found in apps.modules_apps")


@pytest.fixture(scope="module")
def app(apps: ModularApp) -> ModularApp:
    """ModularApp application instance (shared per test module).

    ModularApp extends FastAPI, so we can use it directly.
    """
    return apps  # ModularApp IS a FastAPI


@pytest.fixture(scope="module")
def ws_apps(apps: ModularApp) -> list[FastWSAdapter]:
    """FastWSAdapter application instances (shared per test module)."""
    return [
        ws_app for module_app in apps.modules_apps for ws_app in module_app.ws_versions
    ]


@pytest.fixture(scope="module")
def ws_app(ws_apps: list[FastWSAdapter]) -> FastWSAdapter | None:
    """First FastWSAdapter application instance (shared per test module)."""
    return ws_apps[0] if ws_apps else None


@pytest.fixture
def client(app: ModularApp, valid_jwt_token: str):
    """Sync test client for WebSocket tests with authentication cookies.

    Uses raise_server_exceptions=False so that exceptions are handled by
    FastAPI's exception handlers and return proper HTTP responses.
    """
    with TestClient(app, raise_server_exceptions=False) as c:
        c.cookies.set("access_token", valid_jwt_token)
        yield c


@pytest.fixture
def client_no_auth(app: ModularApp):
    """Sync test client WITHOUT authentication (for testing auth rejection).

    Uses raise_server_exceptions=False so that exceptions are handled by
    FastAPI's exception handlers and return proper HTTP responses.
    """
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
async def async_client(
    app: ModularApp, auth_cookies: dict[str, str]
) -> AsyncGenerator[AsyncClient, None]:
    """Async test client for API tests with authentication cookies.

    Uses ASGITransport with raise_app_exceptions=False so that exceptions
    are handled by FastAPI's exception handlers and return proper HTTP responses.
    """
    from httpx import ASGITransport

    transport = ASGITransport(
        app=app,  # type: ignore[arg-type]  # FastAPI is ASGI-compatible
        raise_app_exceptions=False,
    )
    async with AsyncClient(
        transport=transport, base_url="http://test", cookies=auth_cookies
    ) as ac:
        yield ac


@pytest.fixture
async def async_client_no_auth(app: ModularApp) -> AsyncGenerator[AsyncClient, None]:
    """Async test client for API tests WITHOUT authentication (for testing auth flows).

    Uses ASGITransport with raise_app_exceptions=False so that exceptions
    are handled by FastAPI's exception handlers and return proper HTTP responses.
    """
    from httpx import ASGITransport

    transport = ASGITransport(
        app=app,  # type: ignore[arg-type]  # FastAPI is ASGI-compatible
        raise_app_exceptions=False,
    )
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(scope="session")
def broker_service():
    """Start broker service once per session.

    Returns:
        Base URL of the broker service (http://127.0.0.1:8001)
    """
    port = 8001
    process = multiprocessing.Process(target=run_service, args=("broker", port))
    process.start()

    # Wait for service to become available
    base_url = f"http://127.0.0.1:{port}"
    if not wait_for_service_sync(base_url):
        process.terminate()
        pytest.fail("Broker service failed to start")

    yield base_url

    # Cleanup after ALL tests in session
    process.terminate()
    process.join(timeout=5)
    if process.is_alive():
        process.kill()
        process.join()


@pytest.fixture(scope="session")
def datafeed_service():
    """Start datafeed service once per session.

    Returns:
        Base URL of the datafeed service (http://127.0.0.1:8002)
    """
    port = 8002
    process = multiprocessing.Process(target=run_service, args=("datafeed", port))
    process.start()

    # Wait for service to become available
    base_url = f"http://127.0.0.1:{port}"
    if not wait_for_service_sync(base_url):
        process.terminate()
        pytest.fail("Datafeed service failed to start")

    yield base_url

    # Cleanup after ALL tests in session
    process.terminate()
    process.join(timeout=1)
    if process.is_alive():
        process.kill()
        process.join()
