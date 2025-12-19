"""Tests for module code generation script."""

import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable

import pytest

# Add src to path for module imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from trading_api.models.common import CapabilitySpec, ProviderConfig  # noqa: E402
from trading_api.models.exceptions import (  # noqa: E402
    CommonException,
    TradingApiException,
)
from trading_api.models.market import (  # noqa: E402
    Bar,
    QuoteData,
    Resolution,
    SearchSymbolResultItem,
    SymbolInfo,
)
from trading_api.modules.auth import AuthModule  # noqa: E402
from trading_api.modules.broker import BrokerModule  # noqa: E402
from trading_api.modules.datafeed import DatafeedModule  # noqa: E402
from trading_api.providers.capabilities.datafeed import DatafeedCapability  # noqa: E402
from trading_api.shared import Provider  # noqa: E402
from trading_api.shared.module_interface import ModuleApp  # noqa: E402


class MockDatafeedProvider(Provider, DatafeedCapability):
    """Mock provider for testing datafeed module loading."""

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
        return []

    async def get_symbol_info(self, ticker_name: str, **kwargs: Any) -> SymbolInfo:
        raise NotImplementedError("Mock provider")

    async def get_historical_bars(
        self,
        ticker_name: str,
        start_time: datetime,
        end_time: datetime,
        resolution: Resolution,
        **kwargs: Any,
    ) -> list[Bar]:
        return []

    async def get_quotes_snapshot(
        self, ticker_names: list[str], **kwargs: Any
    ) -> list[QuoteData]:
        return []

    def subscribe_realtime_bars(
        self,
        ticker_name: str,
        resolution: Resolution,
        callback: Callable[[Bar], Awaitable[None]],
        on_error: Callable[[TradingApiException], Awaitable[None]] | None = None,
        **kwargs: Any,
    ) -> str:
        return "sub_0"

    def subscribe_market_data(
        self,
        ticker_names: list[str],
        callback: Callable[[QuoteData], Awaitable[None]],
        on_error: Callable[[TradingApiException], Awaitable[None]] | None = None,
        **kwargs: Any,
    ) -> list[str]:
        return []

    def unsubscribe_realtime_bars(self, subscription_id: str) -> None:
        pass

    def unsubscribe_market_data(self, subscription_ids: list[str]) -> None:
        pass


class TestModuleCodegen:
    """Test module code generation functionality."""

    def test_datafeed_module_creates_apps_via_module_app_wrapper(self):
        """Test that DatafeedModule can generate apps via ModuleApp wrapper.

        This test reproduces the bug: 'DatafeedModule' object has no attribute 'create_app'
        The correct pattern is to use ModuleApp(module) wrapper, not module.create_app()
        """
        # Provide mock provider for datafeed capability
        mock_provider = MockDatafeedProvider()

        # Instantiate module with provider
        module = DatafeedModule(providers=[mock_provider])

        # Create apps using ModuleApp wrapper (correct pattern)
        module_app = ModuleApp(module)

        # Verify apps were created
        assert len(module_app.api_versions) > 0
        assert module_app.api_versions[0] is not None

    def test_broker_module_creates_apps_via_module_app_wrapper(self):
        """Test that BrokerModule can generate apps via ModuleApp wrapper."""
        # Instantiate module
        module = BrokerModule()

        # Create apps using ModuleApp wrapper (correct pattern)
        module_app = ModuleApp(module)

        # Verify apps were created
        assert len(module_app.api_versions) > 0
        assert module_app.api_versions[0] is not None

    def test_module_app_generates_specs_and_clients(self):
        """Test that ModuleApp can generate specs and clients."""
        # Provide mock provider for datafeed capability
        mock_provider = MockDatafeedProvider()

        # Instantiate module with provider
        module = DatafeedModule(providers=[mock_provider])

        # Create apps using ModuleApp wrapper
        module_app = ModuleApp(module)

        # Should be callable without errors
        # (actual file generation tested in integration tests)
        assert hasattr(module_app, "gen_specs_and_clients")
        assert callable(module_app.gen_specs_and_clients)

    def test_auth_module_requires_providers(self) -> None:
        """Test that AuthModule fails without providers.

        This ensures fail-fast validation works when modules are
        instantiated directly (e.g., in codegen scripts).
        """
        with pytest.raises(
            CommonException,
            match="Service 'auth' requires capability 'auth'",
        ):
            AuthModule()  # Should fail: no providers for auth capability

    @pytest.mark.parametrize("module_name", ["datafeed", "broker"])
    def test_module_codegen_script_for_modules_without_capabilities(
        self, module_name: str
    ) -> None:
        """Test that module_codegen.py runs for modules without capabilities."""
        script_path = (
            Path(__file__).parent.parent.parent / "scripts" / "module_codegen.py"
        )

        result = subprocess.run(
            [sys.executable, str(script_path), module_name],
            cwd=Path(__file__).parent.parent.parent,
            capture_output=True,
            text=True,
        )

        # Should succeed
        assert (
            result.returncode == 0
        ), f"Script failed for {module_name}: {result.stderr}"
        assert "AttributeError" not in result.stderr

    def test_module_codegen_script_for_auth_module(self) -> None:
        """Test that module_codegen.py runs for auth module (requires providers).

        This test will fail until module_codegen.py is fixed to inject providers.
        """
        script_path = (
            Path(__file__).parent.parent.parent / "scripts" / "module_codegen.py"
        )

        result = subprocess.run(
            [sys.executable, str(script_path), "auth"],
            cwd=Path(__file__).parent.parent.parent,
            capture_output=True,
            text=True,
        )

        # Should succeed (after fix to module_codegen.py)
        assert result.returncode == 0, f"Script failed for auth: {result.stderr}"
        assert "CommonException" not in result.stderr
