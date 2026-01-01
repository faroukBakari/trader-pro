"""
Tests for ModuleRegistry validation functionality.

Tests cover:
1. Module name validation (no underscores)
2. Validation errors provide clear messages
3. Valid modules pass validation
4. Integration with existing registry functionality
"""

from collections.abc import Awaitable, Generator
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import pytest

# Import MockBrokerProvider from conftest
from tests.conftest import MockBrokerProvider  # type: ignore
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
from trading_api.shared import Provider
from trading_api.shared.module_registry import ModuleRegistry


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
        ticker_name: str,
        callback: Callable[[QuoteData], Awaitable[None]],
        on_error: Callable[[TradingApiException], Awaitable[None]] | None = None,
        **kwargs: Any,
    ) -> str:
        return "sub_0"

    def unsubscribe_realtime_bars(self, subscription_id: str) -> None:
        pass

    def unsubscribe_market_data(self, subscription_id: str) -> None:
        pass


class TestModuleRegistryValidation:
    """Test suite for ModuleRegistry._validate_module_names()."""

    @pytest.fixture
    def registry(self) -> ModuleRegistry:
        from pathlib import Path

        # Use actual modules directory
        backend_dir = Path(__file__).parent.parent
        modules_dir = backend_dir / "src" / "trading_api" / "modules"
        return ModuleRegistry(modules_dir=modules_dir)

    def test_validate_module_names_accepts_valid_hyphenated_names(
        self, registry: ModuleRegistry
    ):
        """Verify validation accepts module names with hyphens."""
        module_names = {"broker", "datafeed", "market-data", "user-auth"}

        errors = registry._validate_module_names(module_names)

        assert len(errors) == 0, "Valid module names should pass validation"

    def test_validate_module_names_rejects_underscore_names(
        self, registry: ModuleRegistry
    ):
        """Verify validation rejects module names with underscores."""
        module_names = {"broker", "market_data", "user_auth"}

        errors = registry._validate_module_names(module_names)

        assert len(errors) == 2, "Should report 2 errors (2 modules with underscores)"
        assert any("market_data" in err for err in errors)
        assert any("user_auth" in err for err in errors)
        assert all("underscore" in err.lower() for err in errors)

    def test_validate_module_names_rejects_single_underscore_module(
        self, registry: ModuleRegistry
    ):
        """Verify validation rejects even a single module with underscore."""
        module_names = {"bad_module"}

        errors = registry._validate_module_names(module_names)

        assert len(errors) == 1
        assert "bad_module" in errors[0]
        assert "underscore" in errors[0].lower()
        assert "hyphen" in errors[0].lower()

    def test_validate_module_names_empty_set(self, registry: ModuleRegistry):
        """Verify validation handles empty module set."""
        errors = registry._validate_module_names(set())

        assert len(errors) == 0, "Empty module set should pass validation"

    def test_validate_module_names_single_valid_module(self, registry: ModuleRegistry):
        """Verify validation handles single valid module."""
        errors = registry._validate_module_names({"broker"})

        assert len(errors) == 0, "Single valid module should pass validation"

    def test_validation_error_message_includes_suggestion(
        self, registry: ModuleRegistry
    ):
        """Verify validation error messages suggest using hyphens."""
        module_names = {"test_module"}

        errors = registry._validate_module_names(module_names)

        assert len(errors) == 1
        error_msg = errors[0]
        # Should mention specific module
        assert "test_module" in error_msg
        # Should mention the problem
        assert "underscore" in error_msg.lower()
        # Should suggest solution
        assert "hyphen" in error_msg.lower()

    def test_validate_module_names_multiple_errors(self, registry: ModuleRegistry):
        """Verify validation reports all errors, not just first one."""
        module_names = {"first_bad", "second_bad", "third_bad"}

        errors = registry._validate_module_names(module_names)

        assert len(errors) == 3
        # Each error should mention a specific module
        assert any("first_bad" in err for err in errors)
        assert any("second_bad" in err for err in errors)
        assert any("third_bad" in err for err in errors)


class TestModuleRegistryExistingFunctionality:
    """Test suite to ensure existing registry functionality still works."""

    @pytest.fixture
    def registry(self) -> Generator[ModuleRegistry, None, None]:
        """Create a fresh registry for each test."""
        from pathlib import Path

        # Use actual modules directory
        backend_dir = Path(__file__).parent.parent
        modules_dir = backend_dir / "src" / "trading_api" / "modules"
        reg = ModuleRegistry(modules_dir=modules_dir)
        yield reg
        reg.clear()

    def test_register_module_class(self, registry: ModuleRegistry):
        """Verify module registration still works."""
        from trading_api.modules.broker import BrokerModule

        registry.register(BrokerModule, "broker")

        assert "broker" in registry._module_classes
        assert registry._module_classes["broker"] == BrokerModule

    def test_get_module(self, registry: ModuleRegistry):
        """Verify getting a registered module works."""
        from trading_api.modules.broker import BrokerModule

        registry.register(BrokerModule, "broker")

        # Provide mock provider for broker capability using get_modules
        mock_broker = MockBrokerProvider()
        modules = registry.get_modules(module_names=["broker"], providers=[mock_broker])
        module = modules[0] if modules else None

        assert module is not None
        assert isinstance(module, BrokerModule)

    def test_get_modules_filtered(self, registry: ModuleRegistry):
        """Verify getting filtered modules works."""
        from trading_api.modules.broker import BrokerModule
        from trading_api.modules.datafeed import DatafeedModule

        registry.register(BrokerModule, "broker")
        registry.register(DatafeedModule, "datafeed")

        # Provide mock provider for broker capability
        mock_broker = MockBrokerProvider()
        modules = registry.get_modules(module_names=["broker"], providers=[mock_broker])

        assert len(modules) == 1
        assert isinstance(modules[0], BrokerModule)

    def test_clear_registry(self, registry: ModuleRegistry):
        """Verify clearing registry works."""
        from trading_api.modules.broker import BrokerModule

        registry.register(BrokerModule, "broker")
        assert len(registry._module_classes) == 1

        registry.clear()

        assert len(registry._module_classes) == 0
        assert len(registry._instances) == 0

    def test_auto_discover_with_real_modules(self, registry: ModuleRegistry):
        """Verify auto_discover works with real modules (broker, datafeed)."""
        # Should succeed (existing modules have valid names)
        registry.auto_discover()

        # Verify known modules were registered
        assert "broker" in registry._module_classes
        assert "datafeed" in registry._module_classes


class TestModuleVersionSelection:
    """Test suite for version-specific module loading optimization."""

    @pytest.fixture
    def registry(self) -> Generator[ModuleRegistry, None, None]:
        """Create a fresh registry for each test."""
        from pathlib import Path

        backend_dir = Path(__file__).parent.parent
        modules_dir = backend_dir / "src" / "trading_api" / "modules"
        reg = ModuleRegistry(modules_dir=modules_dir)
        yield reg
        reg.clear()

    def test_parse_module_spec_with_version(self, registry: ModuleRegistry):
        """Test parsing module spec with version."""
        name, version = registry._parse_module_spec("broker:v1")

        assert name == "broker"
        assert version == "v1"

    def test_parse_module_spec_without_version(self, registry: ModuleRegistry):
        """Test parsing module spec without version."""
        name, version = registry._parse_module_spec("broker")

        assert name == "broker"
        assert version is None

    def test_parse_module_spec_with_whitespace(self, registry: ModuleRegistry):
        """Test parsing module spec with whitespace."""
        name, version = registry._parse_module_spec(" broker : v1 ")

        assert name == "broker"
        assert version == "v1"

    def test_get_modules_with_specific_version(self, registry: ModuleRegistry):
        """Test loading a module with a specific version."""
        from trading_api.modules.broker import BrokerModule

        registry.register(BrokerModule, "broker")

        # Provide mock provider for broker capability
        mock_broker = MockBrokerProvider()

        # Load broker with only v1
        modules = registry.get_modules(
            module_names=["broker:v1"], providers=[mock_broker]
        )

        assert len(modules) == 1
        assert modules[0].name == "broker"
        assert modules[0].versions == ["v1"]
        assert len(modules[0].api_routers) == 1
        assert "v1" in modules[0].api_routers

    def test_get_modules_mixed_version_specs(self, registry: ModuleRegistry):
        """Test loading modules with mixed version specifications."""
        from trading_api.modules.broker import BrokerModule
        from trading_api.modules.datafeed import DatafeedModule

        registry.register(BrokerModule, "broker")
        registry.register(DatafeedModule, "datafeed")

        # Provide mock providers for capabilities
        mock_datafeed = MockDatafeedProvider()
        mock_broker = MockBrokerProvider()

        # Load broker:v1 and datafeed (all versions)
        modules = registry.get_modules(
            module_names=["broker:v1", "datafeed"],
            providers=[mock_datafeed, mock_broker],
        )

        assert len(modules) == 2
        broker = next(m for m in modules if m.name == "broker")
        datafeed = next(m for m in modules if m.name == "datafeed")

        assert broker.versions == ["v1"]  # Only v1
        assert len(datafeed.versions) >= 1  # All versions

    def test_cache_isolation_for_different_versions(self, registry: ModuleRegistry):
        """Test that different versions create separate instances."""
        from trading_api.modules.broker import BrokerModule
        from trading_api.modules.datafeed import DatafeedModule

        registry.register(BrokerModule, "broker")
        registry.register(DatafeedModule, "datafeed")

        # Provide mock providers for capabilities
        mock_datafeed = MockDatafeedProvider()
        mock_broker = MockBrokerProvider()

        # Load broker:v1 (specific version)
        modules_broker = registry.get_modules(
            module_names=["broker:v1"], providers=[mock_broker]
        )
        # Load datafeed without version (all versions)
        modules_datafeed = registry.get_modules(
            module_names=["datafeed"], providers=[mock_datafeed]
        )

        # Should be different instances with different version lists
        broker = modules_broker[0]
        datafeed = modules_datafeed[0]

        assert broker is not datafeed
        assert broker.versions == ["v1"]  # Only v1
        assert len(datafeed.versions) >= 1  # All available versions

        # Test same module with different version specs creates different instances
        modules_broker_all = registry.get_modules(
            module_names=["broker"], providers=[mock_broker]
        )
        broker_all = modules_broker_all[0]

        assert broker is not broker_all  # Different instances
        assert broker.versions == ["v1"]
        assert len(broker_all.versions) >= 1

    def test_cache_reuses_same_version_instance(self, registry: ModuleRegistry):
        """Test that requesting the same version twice returns the same instance."""
        from trading_api.modules.broker import BrokerModule

        registry.register(BrokerModule, "broker")

        # Provide mock provider for broker capability
        mock_broker = MockBrokerProvider()

        # Load broker:v1 twice
        modules_1 = registry.get_modules(
            module_names=["broker:v1"], providers=[mock_broker]
        )
        modules_2 = registry.get_modules(
            module_names=["broker:v1"], providers=[mock_broker]
        )

        # Should be the same instance (cached)
        assert modules_1[0] is modules_2[0]

    def test_get_modules_all_versions_when_no_spec(self, registry: ModuleRegistry):
        """Test that omitting version spec loads all versions."""
        from trading_api.modules.broker import BrokerModule

        registry.register(BrokerModule, "broker")

        # Provide mock provider for broker capability
        mock_broker = MockBrokerProvider()

        # Load broker without version spec
        modules = registry.get_modules(module_names=["broker"], providers=[mock_broker])

        assert len(modules) == 1
        # Should have multiple versions
        assert len(modules[0].versions) >= 1
        assert len(modules[0].api_routers) >= 1
