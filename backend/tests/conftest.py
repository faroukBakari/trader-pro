"""Shared test fixtures for all test suites.

This module provides a generic test app factory and the apps fixture for shared tests.
Other common fixtures (app, ws_apps, ws_app, client, async_client) are defined in the root
trading_api/conftest.py and are available to all tests via pytest discovery.

Each test suite can create an app with only the modules it needs for isolation.
"""

import asyncio
from pathlib import Path
from typing import Awaitable, Callable

import pytest

from trading_api.app_factory import AppFactory, ModularApp
from trading_api.capabilities.broker import BrokerCapability
from trading_api.models.broker import (
    AccountMetainfo,
    Brackets,
    EquityData,
    Execution,
    LeverageInfo,
    LeverageInfoParams,
    LeveragePreviewResult,
    LeverageSetParams,
    LeverageSetResult,
    OrderPreviewResult,
    PlacedOrder,
    PlaceOrderResult,
    Position,
    PreOrder,
)
from trading_api.models.common import CapabilitySpec, ProviderConfig
from trading_api.models.exceptions import TradingApiException
from trading_api.shared import Provider


class MockBrokerProvider(Provider, BrokerCapability):
    """Mock provider for testing broker module loading."""

    def __init__(self) -> None:
        self._order_counter = 1

    @classmethod
    def provider_dir(cls) -> Path:
        return Path(__file__).parent

    @property
    def name(self) -> str:
        return "mockbroker"

    @property
    def config(self) -> ProviderConfig:
        return ProviderConfig()

    @classmethod
    def capabilities(cls) -> list[CapabilitySpec]:
        return [CapabilitySpec(name="broker")]

    async def place_order(self, order: PreOrder) -> PlaceOrderResult:
        order_id = f"ORDER-{self._order_counter}"
        self._order_counter += 1
        return PlaceOrderResult(orderId=order_id)

    async def modify_order(self, order_id: str, order: PreOrder) -> None:
        pass

    async def cancel_order(self, order_id: str) -> None:
        pass

    async def close_position(
        self, position_id: str, amount: float | None = None
    ) -> None:
        pass

    async def edit_position_brackets(
        self,
        position_id: str,
        brackets: Brackets,
    ) -> None:
        pass

    async def get_orders(self) -> list[PlacedOrder]:
        return []

    async def get_positions(self) -> list[Position]:
        return []

    async def get_executions(self, symbol: str) -> list[Execution]:
        return []

    async def get_account_info(self) -> AccountMetainfo:
        return AccountMetainfo(id="MOCK", name="Mock Account")

    async def get_equity(self) -> EquityData:
        return EquityData(
            equity=100000.0, balance=100000.0, unrealizedPL=0.0, realizedPL=0.0
        )

    async def preview_order(self, order: PreOrder) -> OrderPreviewResult:
        return OrderPreviewResult(
            sections=[], confirmId="mock", warnings=None, errors=None
        )

    async def preview_leverage(
        self, params: LeverageSetParams
    ) -> LeveragePreviewResult:
        return LeveragePreviewResult(infos=None, warnings=None, errors=None)

    async def get_leverage_info(self, params: LeverageInfoParams) -> LeverageInfo:
        return LeverageInfo(title="Mock", leverage=10.0, min=1.0, max=100.0, step=1.0)

    async def set_leverage(self, params: LeverageSetParams) -> LeverageSetResult:
        return LeverageSetResult(leverage=params.leverage)

    def subscribe_orders(
        self,
        callback: Callable[[PlacedOrder], Awaitable[None]],
        on_error: Callable[[TradingApiException], Awaitable[None]] | None = None,
    ) -> str:
        return "sub_orders"

    def subscribe_positions(
        self,
        callback: Callable[[Position], Awaitable[None]],
        on_error: Callable[[TradingApiException], Awaitable[None]] | None = None,
    ) -> str:
        return "sub_positions"

    def subscribe_executions(
        self,
        symbol: str,
        callback: Callable[[Execution], Awaitable[None]],
        on_error: Callable[[TradingApiException], Awaitable[None]] | None = None,
    ) -> str:
        return "sub_executions"

    def subscribe_equity(
        self,
        callback: Callable[[EquityData], Awaitable[None]],
        on_error: Callable[[TradingApiException], Awaitable[None]] | None = None,
    ) -> str:
        return "sub_equity"

    def unsubscribe(self, subscription_id: str) -> None:
        pass


# Note: event_loop fixture is defined in backend/conftest.py (root level)
# to be shared across all test directories (tests/, src/trading_api/)


def create_test_app(
    enabled_modules: list[str] | None = None,
) -> ModularApp:
    """Create a test application with specified modules.

    Args:
        enabled_modules: List of module names to enable (e.g., ["broker", "datafeed"])
                        If None, all modules are enabled.

    Returns:
        ModularApp: Modular application (extends FastAPI)

    Example:
        # Test with all modules
        app = create_test_app()

        # Test with only broker module
        app = create_test_app(enabled_modules=["broker"])

        # Test with only shared infrastructure (no modules)
        app = create_test_app(enabled_modules=[])
    """
    factory = AppFactory()
    return asyncio.get_event_loop().run_until_complete(
        factory.create_app(enabled_module_names=enabled_modules)
    )


@pytest.fixture(scope="session")
def apps() -> ModularApp:
    """Full application with all modules enabled (shared across session)."""
    return create_test_app()
