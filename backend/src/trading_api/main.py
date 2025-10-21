"""Main FastAPI application with API versioning support."""

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, AsyncGenerator

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from external_packages.fastws import Client
from trading_api.plugins.fastws_adapter import FastWSAdapter

from .api.broker import router as broker_router
from .api.datafeed import router as datafeed_router
from .api.health import router as health_router
from .api.versions import router as versions_router
from .core.config import BroadcasterConfig
from .core.datafeed_broadcaster import DataFeedBroadcaster
from .core.datafeed_service import DatafeedService
from .core.versioning import APIVersion
from .ws import ws_routers

api_routers: list[APIRouter] = [
    health_router,
    versions_router,
    datafeed_router,
    broker_router,
]

# Configure logging for the application
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Set specific loggers to INFO level
logging.getLogger("trading_api").setLevel(logging.INFO)
logging.getLogger("uvicorn").setLevel(logging.INFO)
logging.getLogger("uvicorn.access").setLevel(logging.INFO)

# Global instances
datafeed_service = DatafeedService()
datafeed_broadcaster: DataFeedBroadcaster | None = None


def validate_response_models(app: FastAPI) -> None:
    """Validate that all routes have response_model defined for OpenAPI compliance"""

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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Handle application startup and shutdown events."""
    global datafeed_broadcaster

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
    asyncapi_schema = wsApp.asyncapi()
    asyncapi_file = backend_dir / "asyncapi.json"

    try:
        with open(asyncapi_file, "w") as f:
            json.dump(asyncapi_schema, f, indent=2)
        print(f"📝 Generated AsyncAPI spec: {asyncapi_file}")
    except Exception as e:
        print(f"⚠️  Failed to generate AsyncAPI file: {e}")

    # Startup: Start bar broadcaster if enabled
    if BroadcasterConfig.get_enabled():
        datafeed_broadcaster = DataFeedBroadcaster(
            ws_app=wsApp,
            datafeed_service=datafeed_service,
            interval=BroadcasterConfig.get_interval(),
            symbols=BroadcasterConfig.get_symbols(),
            resolutions=BroadcasterConfig.get_resolutions(),
        )
        datafeed_broadcaster.start()
        print(
            f"📡 Bar broadcaster started: "
            f"symbols={BroadcasterConfig.get_symbols()}, "
            f"interval={BroadcasterConfig.get_interval()}s"
        )
    else:
        print(
            "⏸️  Bar broadcaster disabled (set BAR_BROADCASTER_ENABLED=true to enable)"
        )

    wsApp.setup(apiApp)

    yield

    # Shutdown: Stop bar broadcaster
    if datafeed_broadcaster:
        datafeed_broadcaster.stop()
        print("📡 Bar broadcaster stopped")

    # Shutdown: Cleanup is handled by FastAPIAdapter
    print("🛑 FastAPI application shutdown complete")


base_url = "/api/v1"

apiApp = FastAPI(
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

# Add CORS middleware to allow frontend tests to connect
apiApp.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ws_url = f"{base_url}/ws"
wsApp = FastWSAdapter(
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

# Include all WebSocket routers
for ws_router in ws_routers:
    wsApp.include_router(ws_router)

# Include version 1 routes
for api_router in api_routers:
    apiApp.include_router(api_router, prefix=base_url, tags=["v1"])


# Register the WebSocket endpoint
@apiApp.websocket(ws_url)
async def websocket_bars_endpoint(
    client: Annotated[Client, Depends(wsApp.manage)],
) -> None:
    """WebSocket endpoint for real-time bar data streaming"""
    await wsApp.serve(client)


# Add version information to root endpoint
@apiApp.get("/", tags=["root"])
async def root() -> dict:
    """Root endpoint with API information."""
    return {
        "name": "Trading API",
        "version": "1.0.0",
        "current_api_version": APIVersion.get_latest().value,
        "documentation": f"{base_url}/docs",
        "health": f"{base_url}/health",
        "versions": f"{base_url}/versions",
        "datafeed": f"{base_url}/datafeed",
        "websockets": {
            router.route: router.build_specs(ws_url, wsApp) for router in ws_routers
        },
    }


# Backward compatibility alias for ASGI servers
app = apiApp
