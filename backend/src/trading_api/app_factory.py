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
    enabled_module_names: list[str] | None = None,
) -> tuple[FastAPI, list[FastWSAdapter]]:
    """Create and configure FastAPI and FastWSAdapter applications.

    Args:
        enabled_module_names: List of module names to enable. If None, all registered
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
    registry.set_enabled_modules(enabled_module_names)

    # Create base URL
    base_url = "/api/v1"

    # Compute OpenAPI tags dynamically from enabled modules
    openapi_tags = [
        {"name": "health", "description": "Health check operations"},
        {"name": "versioning", "description": "API version information"},
    ] + [
        tag for module in registry.get_enabled_modules() for tag in module.openapi_tags
    ]

    enabled_modules = registry.get_enabled_modules()
    module_api_apps: list[FastAPI] = []
    module_ws_apps: list[FastWSAdapter] = []

    for module in enabled_modules:
        api_app, ws_app = module.create_app(base_url)
        module_api_apps.append(api_app)
        if ws_app:
            module_ws_apps.append(ws_app)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        """Handle application startup and shutdown events."""
        # Startup: Trigger module app lifespans to generate/compare specs
        module_lifespan_cms = []
        for module_app in module_api_apps:
            cm = module_app.router.lifespan_context(module_app)
            module_lifespan_cms.append(cm)
            await cm.__aenter__()

        # Validate all routes have response models
        validate_response_models(app)

        yield

        # Shutdown: Clean up module lifespans
        for cm in module_lifespan_cms:
            await cm.__aexit__(None, None, None)

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

    # Include shared API routers (always available)
    api_app.include_router(HealthApi(tags=["health"]), prefix=base_url, tags=["v1"])
    api_app.include_router(
        VersionApi(tags=["versioning"]), prefix=base_url, tags=["v1"]
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

    # Include module routers directly (not mounting sub-apps)
    # Module apps already have routes with full prefix (e.g., /api/v1/broker/*)
    # so we merge them into the main app's route table
    for module_app, module in zip(module_api_apps, enabled_modules):
        # Copy routes from module app to main app
        for route in module_app.routes:
            # Skip the default OpenAPI/docs routes from module apps
            route_path = getattr(route, "path", "")
            if route_path in ["/openapi.json", "/docs", "/redoc"]:
                continue
            api_app.router.routes.append(route)

        # Merge WebSocket setup from module apps
        # (WebSocket endpoints are already registered as routes above)

    return api_app, module_ws_apps
