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

from trading_api.models import APIVersion
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
) -> tuple[FastAPI, FastWSAdapter]:
    """Create and configure FastAPI and FastWSAdapter applications.

    Args:
        enabled_modules: List of module names to enable. If None, all registered
            modules are enabled. Use this to selectively load modules.

    Returns:
        tuple[FastAPI, FastWSAdapter]: Configured API and WebSocket applications

    Example:
        >>> # Load all modules
        >>> api_app, ws_app = create_app()
        >>> # Load only datafeed module
        >>> api_app, ws_app = create_app(enabled_modules=["datafeed"])
    """
    # TODO: Import and register modules here once Phase 2 is complete
    # from trading_api.modules.datafeed import DatafeedModule
    # from trading_api.modules.broker import BrokerModule
    # registry.register(DatafeedModule())
    # registry.register(BrokerModule())

    # Filter modules if enabled_modules is specified
    if enabled_modules is not None:
        for module in registry.get_all_modules():
            # Enable module if it's in the enabled list
            if hasattr(module, "_enabled"):
                module._enabled = module.name in enabled_modules

    # Create base URL
    base_url = "/api/v1"

    # Create WebSocket adapter (needs to be created before lifespan)
    ws_url = f"{base_url}/ws"
    ws_app = FastWSAdapter(
        title="Trading WebSockets",
        description=(
            "Real-time trading data streaming. "
            "Read the documentation to subscribe to specific data feeds."
        ),
        version="1.0.0",
        asyncapi_url=f"{ws_url}/asyncapi.json",
        asyncapi_docs_url=f"{ws_url}/asyncapi",
        heartbeat_interval=30.0,
        max_connection_lifespan=3600.0,
    )

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

        # Startup: Generate asyncapi.json file for file-based watching
        asyncapi_schema = ws_app.asyncapi()
        asyncapi_file = backend_dir / "asyncapi.json"

        try:
            with open(asyncapi_file, "w") as f:
                json.dump(asyncapi_schema, f, indent=2)
            print(f"📝 Generated AsyncAPI spec: {asyncapi_file}")
        except Exception as e:
            print(f"⚠️  Failed to generate AsyncAPI file: {e}")

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
        openapi_tags=[
            {"name": "health", "description": "Health check operations"},
            {"name": "versioning", "description": "API version information"},
            {"name": "datafeed", "description": "Market data and symbols operations"},
            {
                "name": "broker",
                "description": "Broker operations (orders, positions, executions)",
            },
        ],
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

        # Include WebSocket routers
        for ws_router in module.get_ws_routers():
            ws_app.include_router(ws_router)

        # Call configure_app hook
        module.configure_app(api_app, ws_app)

    # Add root endpoint
    @api_app.get("/", tags=["root"])
    async def root() -> dict:
        """Root endpoint with API information."""
        ws_routers = []
        for module in registry.get_enabled_modules():
            ws_routers.extend(module.get_ws_routers())

        return {
            "name": "Trading API",
            "version": "1.0.0",
            "current_api_version": APIVersion.get_latest().value,
            "documentation": f"{base_url}/docs",
            "health": f"{base_url}/health",
            "versions": f"{base_url}/versions",
            "datafeed": f"{base_url}/datafeed",
            "websockets": {
                router.route: router.build_specs(ws_url, ws_app)
                for router in ws_routers
            },
        }

    return api_app, ws_app
