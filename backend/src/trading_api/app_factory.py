"""Application Factory - Dynamic module composition.

Creates FastAPI and FastWSAdapter applications with configurable module loading.
Supports selective module enabling via configuration.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from trading_api.shared import FastWSAdapter, ModuleRegistry

# Configure logging for the application
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Set specific loggers to INFO level
logging.getLogger("trading_api").setLevel(logging.INFO)
logging.getLogger("uvicorn").setLevel(logging.INFO)
logging.getLogger("uvicorn.access").setLevel(logging.INFO)

# Module logger for app_factory
logger = logging.getLogger(__name__)


class AppFactory:
    """Application factory with instance-scoped module registry.

    Creates FastAPI and FastWSAdapter applications with configurable
    module loading. Each factory instance has its own registry for
    better test isolation and encapsulation.

    Example:
        >>> # Create factory and build apps
        >>> factory = AppFactory()
        >>> api_app, ws_apps = factory.create_apps(["datafeed"])
        >>>
        >>> # Or use the convenience wrapper
        >>> api_app, ws_apps = mount_app_modules(["datafeed"])
    """

    def __init__(self, modules_dir: Path | None = None):
        """Initialize factory with fresh registry.

        Args:
            modules_dir: Path to modules directory.
                        Defaults to trading_api/modules/
        """
        self.registry = ModuleRegistry()
        self.modules_dir = modules_dir or Path(__file__).parent / "modules"

    def create_apps(
        self,
        enabled_module_names: list[str] | None = None,
    ) -> tuple[FastAPI, list[FastWSAdapter]]:
        """Create and configure FastAPI and FastWSAdapter applications.

        The core module is always enabled and loaded first, regardless of the
        enabled_module_names parameter. This ensures health checks and versioning
        are always available.

        Args:
            enabled_module_names: List of module names to enable. If None, all
                registered modules are enabled. Core is always enabled automatically.
                Use this to selectively load feature modules.

        Returns:
            tuple[FastAPI, list[FastWSAdapter]]: API app and list of module WS apps

        Example:
            >>> factory = AppFactory()
            >>> # Load all modules (core + all feature modules)
            >>> api_app, ws_apps = factory.create_apps()
            >>> # Load core + datafeed only
            >>> api_app, ws_apps = factory.create_apps(["datafeed"])
            >>> # Load only core module
            >>> api_app, ws_apps = factory.create_apps([])
        """
        # Clear registry to allow fresh registration (important for tests)
        self.registry.clear()

        # Auto-discover and register all available modules
        self.registry.auto_discover(self.modules_dir)

        # Core module is ALWAYS enabled - ensure it's in the enabled list
        if enabled_module_names is not None and "core" not in enabled_module_names:
            enabled_module_names.append("core")

        # Set which modules should be enabled (core will be included)
        self.registry.set_enabled_modules(enabled_module_names)

        # Create base URL
        base_url = "/api/v1"

        # Compute OpenAPI tags dynamically from enabled modules (including core)
        openapi_tags = [
            tag
            for module in self.registry.get_enabled_modules()
            for tag in module.openapi_tags
        ]

        enabled_modules = self.registry.get_enabled_modules()
        module_api_apps: list[FastAPI] = []
        module_ws_apps: list[FastWSAdapter] = []

        for module in enabled_modules:
            api_app, ws_app = module.create_app()
            module_api_apps.append(api_app)
            if ws_app:
                module_ws_apps.append(ws_app)

        @asynccontextmanager
        async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
            """Handle application startup and shutdown events."""

            # Validate all routes have response models
            validate_response_models(app)

            yield

            # Shutdown: Cleanup is handled by FastAPIAdapter
            print("🛑 FastAPI application shutdown complete")

        # Create FastAPI app
        api_app = FastAPI(
            title="Trading API",
            description=(
                "A comprehensive trading API server with market data "
                "and portfolio management. Supports multiple API versions for "
                "backwards compatibility."
            ),
            version="1.0.0",
            openapi_url=f"{base_url}/openapi.json",
            docs_url=f"{base_url}/docs",
            redoc_url=f"{base_url}/redoc",
            openapi_tags=openapi_tags,
            lifespan=lifespan,
        )

        # Add CORS middleware
        api_app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Allow all origins for development
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Add root endpoint with API information
        @api_app.get("/", tags=["root"])
        async def root() -> dict:
            """Root endpoint providing API metadata and navigation."""
            return {
                "name": "Trading API",
                "version": "1.0.0",
                "current_api_version": "v1",
                "documentation": f"{base_url}/docs",
                "health": f"{base_url}/health",
                "versions": f"{base_url}/versions",
            }

        for module_app, module in zip(module_api_apps, enabled_modules):
            api_app.mount(f"{base_url}/{module.name}", module_app)

        # Merge OpenAPI specs from mounted modules into main app
        merge_openapi_specs(
            main_app=api_app,
            module_apps=[
                (mod_app, mod.name)
                for mod_app, mod in zip(module_api_apps, enabled_modules)
            ],
            base_url=base_url,
        )

        return api_app, module_ws_apps


def validate_response_models(app: FastAPI) -> None:
    """Validate that all routes have response_model defined for OpenAPI compliance."""
    missing_models = []

    for route in app.routes:
        if isinstance(route, APIRoute):
            if route.response_model is None:
                # Skip OPTIONS method as it's auto-generated
                methods = route.methods or set()
                if methods and "OPTIONS" not in methods:
                    endpoint_name = getattr(route.endpoint, "__name__", "unknown")
                    path = route.path
                    missing_models.append(f"{list(methods)} {path} -> {endpoint_name}")

    if missing_models:
        error_msg = (
            "❌ FastAPI Response Model Violations Found:\n"
            + "\n".join(f"  - {model}" for model in missing_models)
            + "\n\nAll FastAPI routes must have response_model"
            + " defined for OpenAPI compliance."
        )
        raise ValueError(error_msg)

    print("✅ All FastAPI routes have response_model defined")


def merge_openapi_specs(
    main_app: FastAPI,
    module_apps: list[tuple[FastAPI, str]],
    base_url: str,
) -> None:
    """Override main app's openapi() to include mounted module specs.

    Merges OpenAPI specifications from mounted module sub-applications into the
    main application's OpenAPI schema. This ensures all endpoints are visible
    in a single unified API documentation.

    Args:
        main_app: Main FastAPI application
        module_apps: List of (module_app, module_name) tuples
        base_url: Base URL prefix (e.g., '/api/v1')
    """
    # Store reference to original openapi method
    original_openapi = main_app.openapi

    def custom_openapi() -> dict:
        """Generate merged OpenAPI schema including all mounted modules."""
        if main_app.openapi_schema:
            return main_app.openapi_schema

        # Get main app's OpenAPI schema
        openapi_schema = original_openapi()

        # Merge each mounted module's schema
        for module_app, module_name in module_apps:
            mount_path = f"{base_url}/{module_name}"
            module_schema = module_app.openapi()

            # Merge paths with mount path prefix
            for path, path_item in module_schema.get("paths", {}).items():
                full_path = f"{mount_path}{path}"
                openapi_schema["paths"][full_path] = path_item

            # Merge components (schemas, security schemes, etc.)
            module_components = module_schema.get("components", {})
            if module_components:
                if "components" not in openapi_schema:
                    openapi_schema["components"] = {}
                for comp_type, comp_data in module_components.items():
                    if comp_type not in openapi_schema["components"]:
                        openapi_schema["components"][comp_type] = {}
                    openapi_schema["components"][comp_type].update(comp_data)

        # Cache the merged schema
        main_app.openapi_schema = openapi_schema
        return openapi_schema

    # Override the openapi method (type: ignore needed for method reassignment)
    main_app.openapi = custom_openapi  # type: ignore[method-assign]


def mount_app_modules(
    enabled_module_names: list[str] | None = None,
) -> tuple[FastAPI, list[FastWSAdapter]]:
    """Create and configure FastAPI and FastWSAdapter applications.

    LEGACY FUNCTION: Maintained for backward compatibility with existing code.
    New code should use AppFactory directly for better encapsulation.

    The core module is always enabled and loaded first, regardless of the
    enabled_module_names parameter. This ensures health checks and versioning
    are always available.

    Args:
        enabled_module_names: List of module names to enable. If None, all registered
            modules (except core) are enabled. Core is always enabled automatically.
            Use this to selectively load feature modules.

    Returns:
        tuple[FastAPI, list[FastWSAdapter]]: API app and list of module WS apps

    Example:
        >>> # Load all modules (core + all feature modules)
        >>> api_app, ws_apps = mount_app_modules()
        >>> # Load core + datafeed only
        >>> api_app, ws_apps = mount_app_modules(enabled_modules=["datafeed"])
        >>> # Load only core module
        >>> api_app, ws_apps = mount_app_modules(enabled_modules=[])
    """
    # Create a fresh factory instance for each call
    # This ensures test isolation (each test gets independent apps)
    factory = AppFactory()
    return factory.create_apps(enabled_module_names)
