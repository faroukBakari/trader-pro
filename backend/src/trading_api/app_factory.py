"""Application Factory - Dynamic module composition.

Creates FastAPI and FastWSAdapter applications with configurable module loading.
Supports selective module enabling via configuration.
"""

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from trading_api.shared import FastWSAdapter, HealthApi, ModuleRegistry, VersionApi

# Configure logging for the application
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Set specific loggers to INFO level
logging.getLogger("trading_api").setLevel(logging.INFO)
logging.getLogger("uvicorn").setLevel(logging.INFO)
logging.getLogger("uvicorn.access").setLevel(logging.INFO)

# Global registry instance
registry = ModuleRegistry()

# Module logger for app_factory
logger = logging.getLogger(__name__)


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


def create_app(
    enabled_modules: list[str] | None = None,
) -> tuple[FastAPI, list[FastWSAdapter]]:
    """Create and configure FastAPI and FastWSAdapter applications.

    Args:
        enabled_modules: List of module names to enable. If None, all registered
            modules are enabled. Use this to selectively load modules.

    Returns:
        tuple[FastAPI, list[FastWSAdapter]]: API app and list of module WS apps

    Example:
        >>> # Load all modules
        >>> api_app, ws_apps = create_app()
        >>> # Load only datafeed module
        >>> api_app, ws_apps = create_app(enabled_modules=["datafeed"])
    """
    # Clear registry to allow fresh registration (important for tests)
    registry.clear()

    modules_dir = Path(__file__).parent / "modules"

    # Auto-discover and register all available modules
    registry.auto_discover(modules_dir)

    # Set which modules should be enabled
    registry.set_enabled_modules(enabled_modules)

    # Create base URL
    base_url = "/api/v1"
    module_ws_map: dict[str, FastWSAdapter] = {}  # Map module names to WS apps

    # Compute OpenAPI tags dynamically from enabled modules
    openapi_tags = [
        {"name": "health", "description": "Health check operations"},
        {"name": "versioning", "description": "API version information"},
    ] + [
        tag
        for module in registry.get_enabled_modules()
        for tag in module.get_openapi_tags()
    ]

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        """Handle application startup and shutdown events."""
        # Startup: Validate all routes have response models
        validate_response_models(app)

        # Backend directory for spec files
        backend_dir = Path(__file__).parent.parent.parent

        # Startup: Generate openapi.json file for file-based watching
        openapi_schema = app.openapi()
        openapi_file = backend_dir / "openapi.json"

        try:
            with open(openapi_file, "w") as f:
                json.dump(openapi_schema, f, indent=2)
            print(f"📝 Generated OpenAPI spec: {openapi_file}")
        except Exception as e:
            print(f"⚠️  Failed to generate OpenAPI file: {e}")

        # Startup: Generate AsyncAPI specs for each module in module's specs/ dir
        modules_dir = backend_dir / "src" / "trading_api" / "modules"
        for module_name, ws_app in module_ws_map.items():
            asyncapi_schema = ws_app.asyncapi()
            # Create module specs directory
            module_specs_dir = modules_dir / module_name / "specs"
            module_specs_dir.mkdir(parents=True, exist_ok=True)
            asyncapi_file = module_specs_dir / "asyncapi.json"
            try:
                with open(asyncapi_file, "w") as f:
                    json.dump(asyncapi_schema, f, indent=2)
                print(f"📝 Generated AsyncAPI spec for '{module_name}': {asyncapi_file}")
            except Exception as e:
                print(f"⚠️  Failed to generate AsyncAPI file for '{module_name}': {e}")

        # Note: OpenAPI specs and Python clients are now generated by backend_manager
        # before starting uvicorn servers to avoid race conditions and redundant work.
        # This lifespan only generates AsyncAPI specs which require the running app.

        # Setup all WebSocket apps
        for ws_app in module_ws_map.values():
            ws_app.setup(app)

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

    # Load shared routers (health, versions) - always available
    api_app.include_router(HealthApi(tags=["health"]), prefix=base_url, tags=["v1"])
    api_app.include_router(
        VersionApi(tags=["versioning"]), prefix=base_url, tags=["v1"]
    )

    # Load enabled modules
    for module in registry.get_enabled_modules():
        # Include API routers
        for router in module.get_api_routers():
            api_app.include_router(router, prefix=base_url, tags=["v1"])

        # Register module's WebSocket endpoint (if supported)
        module.register_ws_endpoint(api_app, base_url)
        ws_app = module.get_ws_app(base_url)
        if ws_app:
            module_ws_map[module.name] = ws_app

        # Call configure_app hook - ws_app parameter deprecated
        module.configure_app(api_app)

    return api_app, list(module_ws_map.values())
