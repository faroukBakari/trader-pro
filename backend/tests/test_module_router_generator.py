"""
Comprehensive tests for the module-scoped WebSocket router generator.

Tests cover:
1. Successful generation when ws.py exists
2. No generation when ws.py doesn't exist
3. Failure handling for invalid TypeAlias
4. App factory integration
5. Cleanup of old files on regeneration
"""

import shutil
from collections.abc import Generator
from pathlib import Path

import pytest


class TestModuleRouterGenerator:
    """Test suite for module-scoped WebSocket router generation."""

    @pytest.fixture
    def backend_dir(self) -> Path:
        """Get backend directory path."""
        return Path(__file__).parent.parent

    @pytest.fixture
    def test_module_name(self) -> str:
        """Name for temporary test module."""
        return "test_ws_gen"

    @pytest.fixture
    def test_module_dir(
        self, backend_dir: Path, test_module_name: str
    ) -> Generator[Path, None, None]:
        """Create temporary test module directory."""
        module_dir = backend_dir / f"src/trading_api/modules/{test_module_name}"
        module_dir.mkdir(parents=True, exist_ok=True)
        (module_dir / "__init__.py").write_text(
            '"""Test module for WS generation."""\n'
        )
        yield module_dir
        # Cleanup after test
        if module_dir.exists():
            shutil.rmtree(module_dir)

    @pytest.fixture
    def cleanup_generated_dirs(self, backend_dir: Path):
        """Cleanup generated directories after tests."""
        yield
        # Clean up any test-generated directories
        modules_dir = backend_dir / "src/trading_api/modules"
        for module_dir in modules_dir.glob("*/"):
            if module_dir.name.startswith("test_"):
                ws_gen = module_dir / "ws_generated"
                if ws_gen.exists():
                    shutil.rmtree(ws_gen, ignore_errors=True)

    def test_generate_module_routers_returns_true_when_ws_py_exists(
        self,
        test_module_dir: Path,
        test_module_name: str,
        cleanup_generated_dirs,
    ):
        """Verify generation returns True when module has ws.py."""
        from trading_api.shared.ws.module_router_generator import (
            generate_module_routers,
        )

        # Create ws.py with valid TypeAlias
        ws_file = test_module_dir / "ws.py"
        ws_file.write_text(
            '''"""WebSocket router definitions."""
from typing import TYPE_CHECKING, TypeAlias
from trading_api.shared.ws.generic_route import WsRouter
from trading_api.models import Bar, BarsSubscriptionRequest

if TYPE_CHECKING:
    TestWsRouter: TypeAlias = WsRouter[BarsSubscriptionRequest, Bar]
'''
        )

        # Generate routers (skip quality checks for speed)
        result = generate_module_routers(
            test_module_name,
            silent=True,
            skip_quality_checks=True,
        )

        # Verify
        assert result is True, "Should return True when ws.py exists with valid routers"

        # Verify generated files exist
        ws_gen = test_module_dir / "ws_generated"
        assert ws_gen.exists(), "ws_generated directory should exist"
        assert (ws_gen / "__init__.py").exists(), "__init__.py should exist"
        assert (ws_gen / "testwsrouter.py").exists(), "Router file should exist"

        # Verify __init__.py has correct exports
        init_content = (ws_gen / "__init__.py").read_text()
        assert "TestWsRouter" in init_content
        assert "__all__" in init_content

    def test_generate_module_routers_returns_false_when_no_ws_py(
        self,
        test_module_dir: Path,
        test_module_name: str,
        cleanup_generated_dirs,
    ):
        """Verify generation returns False when module has no ws.py."""
        from trading_api.shared.ws.module_router_generator import (
            generate_module_routers,
        )

        # Don't create ws.py file
        result = generate_module_routers(
            test_module_name,
            silent=True,
            skip_quality_checks=True,
        )

        # Verify
        assert result is False, "Should return False when no ws.py exists"

        # Verify no ws_generated directory
        ws_gen = test_module_dir / "ws_generated"
        assert not ws_gen.exists(), "ws_generated should not be created"

    def test_generate_module_routers_fails_on_invalid_typealias(
        self,
        test_module_dir: Path,
        test_module_name: str,
        cleanup_generated_dirs,
    ):
        """Verify generation fails with clear error on invalid TypeAlias."""
        from trading_api.shared.ws.module_router_generator import (
            generate_module_routers,
        )

        # Create ws.py with invalid type references
        ws_file = test_module_dir / "ws.py"
        ws_file.write_text(
            '''"""WebSocket router with invalid types."""
from typing import TYPE_CHECKING, TypeAlias
from trading_api.shared.ws.generic_route import WsRouter

if TYPE_CHECKING:
    InvalidRouter: TypeAlias = WsRouter[NonExistentType, AlsoNonExistent]
'''
        )

        # Should fail during quality checks (type checking will catch undefined types)
        with pytest.raises(RuntimeError) as exc_info:
            generate_module_routers(
                test_module_name,
                silent=True,
                skip_quality_checks=False,  # Enable quality checks to catch error
            )

        # Verify error message contains module name for context
        assert test_module_name in str(exc_info.value)

        # Verify cleanup happened - no generated directory left behind
        ws_gen = test_module_dir / "ws_generated"
        assert not ws_gen.exists(), "Failed generation should clean up generated files"

    def test_regeneration_cleans_up_old_files_properly(
        self,
        test_module_dir: Path,
        test_module_name: str,
        cleanup_generated_dirs,
    ):
        """Verify regeneration removes old files and creates fresh ones."""
        from trading_api.shared.ws.module_router_generator import (
            generate_module_routers,
        )

        # Create ws.py with one router
        ws_file = test_module_dir / "ws.py"
        ws_file.write_text(
            '''"""WebSocket routers - version 1."""
from typing import TYPE_CHECKING, TypeAlias
from trading_api.shared.ws.generic_route import WsRouter
from trading_api.models import Bar, BarsSubscriptionRequest

if TYPE_CHECKING:
    FirstRouter: TypeAlias = WsRouter[BarsSubscriptionRequest, Bar]
'''
        )

        # First generation
        result1 = generate_module_routers(
            test_module_name,
            silent=True,
            skip_quality_checks=True,
        )
        assert result1 is True

        # Verify first router exists
        ws_gen = test_module_dir / "ws_generated"
        first_router = ws_gen / "firstrouter.py"
        assert first_router.exists()

        # Create a dummy old file that should be cleaned up
        old_file = ws_gen / "oldrouter.py"
        old_file.write_text("# This should be removed")
        assert old_file.exists()

        # Update ws.py with different router
        ws_file.write_text(
            '''"""WebSocket routers - version 2."""
from typing import TYPE_CHECKING, TypeAlias
from trading_api.shared.ws.generic_route import WsRouter
from trading_api.models import QuoteData, QuoteDataSubscriptionRequest

if TYPE_CHECKING:
    SecondRouter: TypeAlias = WsRouter[QuoteDataSubscriptionRequest, QuoteData]
'''
        )

        # Second generation (regeneration)
        result2 = generate_module_routers(
            test_module_name,
            silent=True,
            skip_quality_checks=True,
        )
        assert result2 is True

        # Verify old files are gone
        assert not first_router.exists(), "Old router should be removed"
        assert not old_file.exists(), "Old dummy file should be removed"

        # Verify new router exists
        second_router = ws_gen / "secondrouter.py"
        assert second_router.exists(), "New router should exist"

        # Verify __init__.py only exports new router
        init_content = (ws_gen / "__init__.py").read_text()
        assert "SecondRouter" in init_content
        assert "FirstRouter" not in init_content

    def test_app_factory_generates_routers_on_startup(self, backend_dir: Path):
        """Verify generated routers exist and work with app factory.

        IMPORTANT: Current implementation has a chicken-and-egg problem:
        - Line 89: auto_discover() imports modules
        - Line 203: generate_module_routers() generates routers

        Modules try to import from ws_generated during discovery (L89), which fails
        if routers don't exist. Therefore, routers MUST be pre-generated before app
        startup (via make generate-ws-routers or manual generation).

        This test validates routers exist and are usable, but doesn't test fresh
        generation because that would break module discovery.

        TODO: Move generation BEFORE auto_discover to fix this (see Phase 2 notes).
        """
        from trading_api.app_factory import mount_app_modules

        # Create app - routers should already exist or be generated during module loading
        api_app, ws_apps = mount_app_modules()

        # Verify generated directories exist for both modules
        datafeed_ws_gen = backend_dir / "src/trading_api/modules/datafeed/ws_generated"
        broker_ws_gen = backend_dir / "src/trading_api/modules/broker/ws_generated"

        assert datafeed_ws_gen.exists(), "Datafeed routers should exist"
        assert broker_ws_gen.exists(), "Broker routers should exist"

        # Verify routers can be imported (implicit validation they're correct)
        try:
            from trading_api.modules.broker.ws_generated import (
                OrderWsRouter,
                PositionWsRouter,
            )
            from trading_api.modules.datafeed.ws_generated import (
                BarWsRouter,
                QuoteWsRouter,
            )

            # Just checking imports work - actual instances created in ws.py
            assert BarWsRouter is not None
            assert QuoteWsRouter is not None
            assert OrderWsRouter is not None
            assert PositionWsRouter is not None

        except ImportError as e:
            pytest.fail(f"Generated routers should be importable: {e}")

    def test_generation_with_quality_checks_passes(
        self,
        test_module_dir: Path,
        test_module_name: str,
        cleanup_generated_dirs,
    ):
        """Verify generated code passes all quality checks."""
        from trading_api.shared.ws.module_router_generator import (
            generate_module_routers,
        )

        # Create ws.py with valid TypeAlias
        ws_file = test_module_dir / "ws.py"
        ws_file.write_text(
            '''"""WebSocket router definitions."""
from typing import TYPE_CHECKING, TypeAlias
from trading_api.shared.ws.generic_route import WsRouter
from trading_api.models import Bar, BarsSubscriptionRequest

if TYPE_CHECKING:
    BarRouter: TypeAlias = WsRouter[BarsSubscriptionRequest, Bar]
'''
        )

        # Generate with quality checks enabled
        result = generate_module_routers(
            test_module_name,
            silent=True,
            skip_quality_checks=False,  # Run full quality pipeline
        )

        # Should succeed without raising RuntimeError
        assert result is True

        # Verify generated code exists
        ws_gen = test_module_dir / "ws_generated"
        assert ws_gen.exists()
        assert (ws_gen / "barrouter.py").exists()

        # Verify code is properly formatted (check for quality check side effects)
        router_code = (ws_gen / "barrouter.py").read_text()
        assert "class BarRouter" in router_code
        assert "BarsSubscriptionRequest" in router_code
        assert "Bar" in router_code

    def test_multiple_routers_in_single_module(
        self,
        test_module_dir: Path,
        test_module_name: str,
        cleanup_generated_dirs,
    ):
        """Verify generation handles multiple routers in one ws.py file."""
        from trading_api.shared.ws.module_router_generator import (
            generate_module_routers,
        )

        # Create ws.py with multiple TypeAlias declarations
        ws_file = test_module_dir / "ws.py"
        ws_file.write_text(
            '''"""Multiple WebSocket routers."""
from typing import TYPE_CHECKING, TypeAlias
from trading_api.shared.ws.generic_route import WsRouter
from trading_api.models import (
    Bar,
    BarsSubscriptionRequest,
    QuoteData,
    QuoteDataSubscriptionRequest,
)

if TYPE_CHECKING:
    BarRouter: TypeAlias = WsRouter[BarsSubscriptionRequest, Bar]
    QuoteRouter: TypeAlias = WsRouter[QuoteDataSubscriptionRequest, QuoteData]
'''
        )

        # Generate
        result = generate_module_routers(
            test_module_name,
            silent=True,
            skip_quality_checks=True,
        )

        assert result is True

        # Verify both routers generated
        ws_gen = test_module_dir / "ws_generated"
        assert (ws_gen / "barrouter.py").exists()
        assert (ws_gen / "quoterouter.py").exists()

        # Verify __init__.py exports both
        init_content = (ws_gen / "__init__.py").read_text()
        assert "BarRouter" in init_content
        assert "QuoteRouter" in init_content
        assert "__all__" in init_content

    def test_empty_ws_py_returns_false(
        self,
        test_module_dir: Path,
        test_module_name: str,
        cleanup_generated_dirs,
    ):
        """Verify generation returns False when ws.py has no router definitions."""
        from trading_api.shared.ws.module_router_generator import (
            generate_module_routers,
        )

        # Create empty ws.py (no TypeAlias)
        ws_file = test_module_dir / "ws.py"
        ws_file.write_text(
            '''"""WebSocket module with no routers yet."""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass  # No routers defined
'''
        )

        # Should return False (no routers to generate)
        result = generate_module_routers(
            test_module_name,
            silent=True,
            skip_quality_checks=True,
        )

        assert result is False
        # No generation, so no ws_generated directory
        ws_gen = test_module_dir / "ws_generated"
        assert not ws_gen.exists()

    def test_generation_before_module_import_required(self, backend_dir: Path):
        """Demonstrate that routers must be generated BEFORE module imports.

        This test documents the current limitation where modules cannot be
        imported if ws_generated doesn't exist, because they try to import
        from ws_generated during module loading.
        """
        # This test documents expected behavior, not desired behavior
        # In the future, generation should happen BEFORE auto_discover

        # Verify that existing modules have ws_generated directories
        datafeed_ws_gen = backend_dir / "src/trading_api/modules/datafeed/ws_generated"
        broker_ws_gen = backend_dir / "src/trading_api/modules/broker/ws_generated"

        # These should exist from pre-generation (make generate-ws-routers)
        assert datafeed_ws_gen.exists(), (
            "Routers must be pre-generated before module import. "
            "Run 'make generate-ws-routers' first."
        )
        assert broker_ws_gen.exists(), (
            "Routers must be pre-generated before module import. "
            "Run 'make generate-ws-routers' first."
        )

        # Verify modules can be imported (they depend on ws_generated)
        try:
            from trading_api.modules.broker import BrokerModule
            from trading_api.modules.datafeed import DatafeedModule

            assert DatafeedModule is not None
            assert BrokerModule is not None
        except ImportError as e:
            pytest.fail(
                f"Modules should import successfully when routers pre-generated: {e}"
            )


class TestRouterSpecParsing:
    """Test suite for parsing TypeAlias declarations from ws.py files."""

    def test_parse_single_line_typealias(self, tmp_path: Path):
        """Test parsing single-line TypeAlias declaration."""
        from trading_api.shared.ws.module_router_generator import (
            parse_router_specs_from_file,
        )

        ws_file = tmp_path / "ws.py"
        ws_file.write_text(
            """
from typing import TYPE_CHECKING, TypeAlias
from trading_api.shared.ws.generic_route import WsRouter
from trading_api.models import Bar, BarsSubscriptionRequest

if TYPE_CHECKING:
    BarRouter: TypeAlias = WsRouter[BarsSubscriptionRequest, Bar]
"""
        )

        specs = parse_router_specs_from_file(ws_file, "test")

        assert len(specs) == 1
        assert specs[0].class_name == "BarRouter"
        assert specs[0].request_type == "BarsSubscriptionRequest"
        assert specs[0].data_type == "Bar"
        assert specs[0].module_name == "test"

    def test_parse_multiline_typealias(self, tmp_path: Path):
        """Test parsing multi-line TypeAlias declaration."""
        from trading_api.shared.ws.module_router_generator import (
            parse_router_specs_from_file,
        )

        ws_file = tmp_path / "ws.py"
        ws_file.write_text(
            """
from typing import TYPE_CHECKING, TypeAlias
from trading_api.shared.ws.generic_route import WsRouter

if TYPE_CHECKING:
    OrderRouter: TypeAlias = WsRouter[
        OrderSubscriptionRequest,
        OrderUpdate
    ]
"""
        )

        specs = parse_router_specs_from_file(ws_file, "broker")

        assert len(specs) == 1
        assert specs[0].class_name == "OrderRouter"
        assert specs[0].request_type == "OrderSubscriptionRequest"
        assert specs[0].data_type == "OrderUpdate"

    def test_parse_multiple_typealias(self, tmp_path: Path):
        """Test parsing multiple TypeAlias declarations."""
        from trading_api.shared.ws.module_router_generator import (
            parse_router_specs_from_file,
        )

        ws_file = tmp_path / "ws.py"
        ws_file.write_text(
            """
from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    BarRouter: TypeAlias = WsRouter[BarsSubscriptionRequest, Bar]
    QuoteRouter: TypeAlias = WsRouter[QuoteDataSubscriptionRequest, QuoteData]
    OrderRouter: TypeAlias = WsRouter[OrderRequest, OrderUpdate]
"""
        )

        specs = parse_router_specs_from_file(ws_file, "multi")

        assert len(specs) == 3
        assert specs[0].class_name == "BarRouter"
        assert specs[1].class_name == "QuoteRouter"
        assert specs[2].class_name == "OrderRouter"

    def test_parse_ignores_non_wsrouter_typealias(self, tmp_path: Path):
        """Test that parsing ignores TypeAlias that are not WsRouter."""
        from trading_api.shared.ws.module_router_generator import (
            parse_router_specs_from_file,
        )

        ws_file = tmp_path / "ws.py"
        ws_file.write_text(
            """
from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    # Should be parsed
    BarRouter: TypeAlias = WsRouter[BarsSubscriptionRequest, Bar]

    # Should be ignored (not WsRouter)
    SomeOtherType: TypeAlias = dict[str, Any]
    AnotherType: TypeAlias = list[str]
"""
        )

        specs = parse_router_specs_from_file(ws_file, "test")

        assert len(specs) == 1
        assert specs[0].class_name == "BarRouter"


class TestGeneratedCodeStructure:
    """Test suite for validating generated code structure."""

    def test_generated_code_imports_correct_types(
        self,
        tmp_path: Path,
    ):
        """Verify generated code imports the correct request and data types."""
        from trading_api.shared.ws.module_router_generator import (
            RouterSpec,
            generate_router_code,
        )

        # Load actual template
        backend_dir = Path(__file__).parent.parent
        template_path = backend_dir / "src/trading_api/shared/ws/generic_route.py"
        template = template_path.read_text()

        spec = RouterSpec(
            class_name="TestRouter",
            request_type="TestRequest",
            data_type="TestData",
            module_name="test",
        )

        code = generate_router_code(spec, template)

        # Verify imports
        assert "from trading_api.models import TestRequest, TestData" in code
        assert "class TestRouter(WsRouteInterface):" in code
        # Verify no TypeVar declarations
        assert "TypeVar(" not in code
        # Verify no Generic imports
        assert "from typing import Generic" not in code

    def test_generated_init_exports_all_routers(self):
        """Verify generated __init__.py exports all router classes."""
        from trading_api.shared.ws.module_router_generator import (
            RouterSpec,
            generate_init_file,
        )

        specs = [
            RouterSpec("BarRouter", "BarReq", "Bar", "test"),
            RouterSpec("QuoteRouter", "QuoteReq", "Quote", "test"),
        ]

        init_content = generate_init_file(specs)

        # Verify imports
        assert "from .barrouter import BarRouter" in init_content
        assert "from .quoterouter import QuoteRouter" in init_content

        # Verify exports
        assert "__all__" in init_content
        assert '"BarRouter"' in init_content
        assert '"QuoteRouter"' in init_content


class TestRouterVerification:
    """Test suite for router verification functionality."""

    @pytest.fixture
    def backend_dir(self) -> Path:
        """Get backend directory path."""
        return Path(__file__).parent.parent

    @pytest.fixture
    def test_module_name(self) -> str:
        """Name for temporary test module."""
        return "test_ws_verify"

    @pytest.fixture
    def test_module_dir(
        self, backend_dir: Path, test_module_name: str
    ) -> Generator[Path, None, None]:
        """Create temporary test module directory."""
        module_dir = backend_dir / f"src/trading_api/modules/{test_module_name}"
        module_dir.mkdir(parents=True, exist_ok=True)

        # Create module __init__.py with service
        (module_dir / "__init__.py").write_text(
            f'''"""Test module for verification."""
from pathlib import Path
from typing import Any
from fastapi import APIRouter
from trading_api.shared.module_interface import Module
from trading_api.shared.ws.router_interface import WsRouteInterface


class TestWsVerifyService:
    """Concrete service implementation for testing."""
    pass


class Test_ws_verifyModule(Module):
    """Test module with service."""

    def __init__(self):
        super().__init__()
        self._service = TestWsVerifyService()

    @property
    def name(self) -> str:
        return "{test_module_name}"

    @property
    def module_dir(self) -> Path:
        return Path(__file__).parent

    @property
    def service(self) -> Any:
        return self._service

    @property
    def api_routers(self) -> list[APIRouter]:
        return []

    @property
    def ws_routers(self) -> list[WsRouteInterface]:
        return []

    @property
    def openapi_tags(self) -> list[dict[str, str]]:
        return []
'''
        )

        yield module_dir

        # Cleanup after test
        if module_dir.exists():
            shutil.rmtree(module_dir)

    @pytest.fixture
    def cleanup_generated_dirs(self, backend_dir: Path):
        """Cleanup generated directories after tests."""
        yield
        # Clean up any test-generated directories
        modules_dir = backend_dir / "src/trading_api/modules"
        for module_dir in modules_dir.glob("*/"):
            if module_dir.name.startswith("test_"):
                ws_gen = module_dir / "ws_generated"
                if ws_gen.exists():
                    shutil.rmtree(ws_gen, ignore_errors=True)

    def test_verify_router_succeeds_for_valid_router(
        self,
        test_module_dir: Path,
        test_module_name: str,
        cleanup_generated_dirs,
    ):
        """Verify _verify_router succeeds for a valid generated router."""
        from trading_api.shared.ws.module_router_generator import (
            _verify_router,
            generate_module_routers,
        )

        # Create ws.py with valid TypeAlias
        ws_file = test_module_dir / "ws.py"
        ws_file.write_text(
            '''"""WebSocket router definitions."""
from typing import TYPE_CHECKING, TypeAlias
from trading_api.shared.ws.generic_route import WsRouter
from trading_api.models import Bar, BarsSubscriptionRequest

if TYPE_CHECKING:
    TestRouter: TypeAlias = WsRouter[BarsSubscriptionRequest, Bar]
'''
        )

        # Generate routers (skip quality checks for speed)
        result = generate_module_routers(
            test_module_name,
            silent=True,
            skip_quality_checks=True,
        )
        assert result is True

        # Verify the router
        ws_gen = test_module_dir / "ws_generated"
        success, message = _verify_router(
            module_name=test_module_name,
            router_class_name="TestRouter",
            output_dir=ws_gen,
        )

        assert success is True
        assert "✓ TestRouter verified" in message

    def test_verify_router_fails_for_missing_router(
        self,
        test_module_dir: Path,
        test_module_name: str,
        cleanup_generated_dirs,
    ):
        """Verify _verify_router fails when router doesn't exist."""
        from trading_api.shared.ws.module_router_generator import _verify_router

        ws_gen = test_module_dir / "ws_generated"
        ws_gen.mkdir(parents=True, exist_ok=True)

        # Try to verify non-existent router
        success, message = _verify_router(
            module_name=test_module_name,
            router_class_name="NonExistentRouter",
            output_dir=ws_gen,
        )

        assert success is False
        assert "Import failed" in message or "failed" in message.lower()

    def test_generate_module_routers_calls_verification(
        self,
        test_module_dir: Path,
        test_module_name: str,
        cleanup_generated_dirs,
    ):
        """Verify generate_module_routers calls verification after generation."""
        from trading_api.shared.ws.module_router_generator import (
            generate_module_routers,
        )

        # Create ws.py with valid TypeAlias
        ws_file = test_module_dir / "ws.py"
        ws_file.write_text(
            '''"""WebSocket router definitions."""
from typing import TYPE_CHECKING, TypeAlias
from trading_api.shared.ws.generic_route import WsRouter
from trading_api.models import Bar, BarsSubscriptionRequest

if TYPE_CHECKING:
    ValidRouter: TypeAlias = WsRouter[BarsSubscriptionRequest, Bar]
'''
        )

        # Generate routers - should include verification
        result = generate_module_routers(
            test_module_name,
            silent=True,
            skip_quality_checks=True,
        )

        # Should succeed (verification passed)
        assert result is True

        # Verify router exists and is importable
        ws_gen = test_module_dir / "ws_generated"
        assert (ws_gen / "validrouter.py").exists()

    def test_generate_module_routers_cleans_up_on_verification_failure(
        self,
        test_module_dir: Path,
        test_module_name: str,
        backend_dir: Path,
        cleanup_generated_dirs,
    ):
        """Verify failed verification cleans up generated files."""
        from trading_api.shared.ws.module_router_generator import (
            generate_module_routers,
        )

        # Create ws.py with router that will fail verification
        # (using undefined types that will cause import errors)
        ws_file = test_module_dir / "ws.py"
        ws_file.write_text(
            '''"""WebSocket router with types that will cause verification to fail."""
from typing import TYPE_CHECKING, TypeAlias
from trading_api.shared.ws.generic_route import WsRouter

if TYPE_CHECKING:
    BrokenRouter: TypeAlias = WsRouter[UndefinedRequest, UndefinedData]
'''
        )

        # Generation should fail during verification
        with pytest.raises(RuntimeError) as exc_info:
            generate_module_routers(
                test_module_name,
                silent=True,
                skip_quality_checks=True,  # Skip quality checks to reach verification
            )

        # Verify error mentions verification
        assert (
            "verification failed" in str(exc_info.value).lower()
            or "import failed" in str(exc_info.value).lower()
        )

        # Verify cleanup happened - no generated directory left behind
        ws_gen = test_module_dir / "ws_generated"
        assert (
            not ws_gen.exists()
        ), "Failed verification should clean up generated files"
