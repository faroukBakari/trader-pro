"""
Tests for ModuleRegistry validation functionality.

Tests cover:
1. Module name validation (no underscores)
2. Validation errors provide clear messages
3. Valid modules pass validation
4. Integration with existing registry functionality
"""

from collections.abc import Generator

import pytest

from trading_api.shared.module_registry import ModuleRegistry


class TestModuleRegistryValidation:
    """Test suite for ModuleRegistry._validate_module_names()."""

    @pytest.fixture
    def registry(self) -> ModuleRegistry:
        """Create a fresh registry for each test."""
        return ModuleRegistry()

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
        reg = ModuleRegistry()
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

        module = registry.get_module("broker")

        assert module is not None
        assert isinstance(module, BrokerModule)

    def test_get_enabled_modules(self, registry: ModuleRegistry):
        """Verify getting enabled modules works."""
        from trading_api.modules.broker import BrokerModule
        from trading_api.modules.datafeed import DatafeedModule

        registry.register(BrokerModule, "broker")
        registry.register(DatafeedModule, "datafeed")
        registry.set_enabled_modules(["broker"])

        enabled = registry.get_enabled_modules()

        assert len(enabled) == 1
        assert isinstance(enabled[0], BrokerModule)

    def test_clear_registry(self, registry: ModuleRegistry):
        """Verify clearing registry works."""
        from trading_api.modules.broker import BrokerModule

        registry.register(BrokerModule, "broker")
        assert len(registry._module_classes) == 1

        registry.clear()

        assert len(registry._module_classes) == 0
        assert len(registry._instances) == 0
        assert registry._enabled_modules is None

    def test_auto_discover_with_real_modules(self, registry: ModuleRegistry):
        """Verify auto_discover works with real modules (broker, datafeed)."""
        from pathlib import Path

        # Use actual modules directory
        backend_dir = Path(__file__).parent.parent
        modules_dir = backend_dir / "src" / "trading_api" / "modules"

        # Should succeed (existing modules have valid names)
        registry.auto_discover(modules_dir)

        # Verify known modules were registered
        assert "broker" in registry._module_classes
        assert "datafeed" in registry._module_classes
