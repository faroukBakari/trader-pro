"""Application Factory - Dynamic module composition.

Creates FastAPI and FastWSAdapter applications with configurable module loading.
Supports selective module enabling via configuration.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator, Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from trading_api.shared import FastWSAdapter, Module, ModuleRegistry

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


class ModuleApp:
    def __init__(self, module: Module):
        self.module = module
        self.api_app, self.ws_app = module.create_app()


class ModularFastAPI(FastAPI):
    """FastAPI application with integrated WebSocket apps tracking.

    Extends FastAPI to provide centralized management of WebSocket applications
    alongside the REST API. This class maintains a list of FastWSAdapter instances
    and provides convenient access to both REST and WebSocket functionality.

    Example:
        >>> app = ModularApp(title="Trading API")
        >>> # Access WebSocket apps
        >>> for ws_app in app.ws_apps:
        >>>     ws_app.setup(app)
        >>> # Use like regular FastAPI
        >>> @app.get("/health")
        >>> async def health():
        >>>     return {"status": "ok"}
    """

    def __init__(self, modules: list[Module], base_url: str, *args: Any, **kwargs: Any):
        """Initialize ModularFastAPI with empty WebSocket apps list.

        Args:
            *args: Positional arguments passed to FastAPI
            **kwargs: Keyword arguments passed to FastAPI
        """
        self.base_url = base_url
        self._modules_apps: list[ModuleApp] = [ModuleApp(module) for module in modules]
        self.asyncapi_schema: Dict[str, Any] | None = None
        super().__init__(
            *args,
            openapi_url=f"{base_url}/openapi.json",
            docs_url=f"{base_url}/docs",
            redoc_url=f"{base_url}/redoc",
            openapi_tags=[
                tag
                for module in self.modules_apps
                if module.api_app.openapi_tags
                for tag in module.api_app.openapi_tags
            ],
            **kwargs,
        )
        for module_app in self._modules_apps:
            mount_path = f"{self.base_url}/{module_app.module.name}"
            self.mount(mount_path, module_app.api_app)
            logger.info(f"📦 Mounted module '{module_app.module.name}' at {mount_path}")

    @property
    def modules_apps(self) -> list[ModuleApp]:
        """Get list of module applications.

        Returns:
            list[ModuleApp]: Read-only list of module apps
        """
        return self._modules_apps

    @property
    def ws_apps(self) -> list[FastWSAdapter]:
        """Get list of WebSocket applications from all modules.

        Returns:
            list[FastWSAdapter]: List of WebSocket apps
        """
        return [
            module_app.ws_app
            for module_app in self._modules_apps
            if module_app.ws_app is not None
        ]

    def openapi(self) -> Dict[str, Any]:
        """Generate merged OpenAPI schema including all mounted modules."""

        # Get main app's OpenAPI schema
        if self.openapi_schema:
            return self.openapi_schema

        openapi_schema = super().openapi()

        # Merge each mounted module's schema
        for module_app in self._modules_apps:
            mount_path = f"{self.base_url}/{module_app.module.name}"
            module_schema = module_app.api_app.openapi()

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

        self.openapi_schema = openapi_schema
        return openapi_schema

    def asyncapi(self) -> Dict[str, Any]:
        """Generate merged AsyncAPI schema including all module WebSocket channels.

        Merges AsyncAPI specifications from all module WebSocket apps, updating
        channel paths to reflect their actual mounted endpoints.

        Returns:
            Dict[str, Any]: Merged AsyncAPI specification with all module channels

        Example:
            >>> app = ModularFastAPI(...)
            >>> asyncapi_spec = app.asyncapi()
            >>> # Contains channels like:
            >>> # "/api/v1/datafeed/ws" - for datafeed WebSocket operations
            >>> # "/api/v1/broker/ws" - for broker WebSocket operations
        """
        if self.asyncapi_schema:
            return self.asyncapi_schema

        # Start with base AsyncAPI structure
        merged_spec: Dict[str, Any] = {
            "asyncapi": "2.4.0",
            "info": {
                "title": f"{self.title} - WebSocket API",
                "version": self.version,
                "description": (
                    f"{self.description}\n\n"
                    "Real-time WebSocket endpoints for streaming market data, "
                    "order updates, position updates, and account information."
                ),
            },
            "channels": {},
            "components": {"schemas": {}, "messages": {}},
        }

        # Merge each module's AsyncAPI spec
        for module_app in self._modules_apps:
            ws_app = module_app.ws_app
            if ws_app is None:
                continue

            # Get module's AsyncAPI spec
            module_spec = ws_app.asyncapi()

            # The module's WebSocket endpoint
            ws_endpoint = f"{self.base_url}/{module_app.module.name}/ws"

            # Merge channels with corrected endpoint paths
            for channel_path, channel_spec in module_spec.get("channels", {}).items():
                # Replace generic "/" with actual endpoint path
                actual_channel = (
                    ws_endpoint if channel_path == "/" else ws_endpoint + channel_path
                )
                merged_spec["channels"][actual_channel] = channel_spec

            # Merge component schemas (avoiding duplicates)
            module_schemas = module_spec.get("components", {}).get("schemas", {})
            for schema_name, schema_def in module_schemas.items():
                if schema_name not in merged_spec["components"]["schemas"]:
                    merged_spec["components"]["schemas"][schema_name] = schema_def

            # Merge component messages (avoiding duplicates)
            module_messages = module_spec.get("components", {}).get("messages", {})
            for message_name, message_def in module_messages.items():
                if message_name not in merged_spec["components"]["messages"]:
                    merged_spec["components"]["messages"][message_name] = message_def

        self.asyncapi_schema = merged_spec
        return merged_spec

    def validate_response_models(self) -> None:
        """Validate that all routes have response_model defined for OpenAPI compliance."""
        missing_models = []

        for route in self.routes:
            if isinstance(route, APIRoute):
                if route.response_model is None:
                    # Skip OPTIONS method as it's auto-generated
                    methods = route.methods or set()
                    if methods and "OPTIONS" not in methods:
                        endpoint_name = getattr(route.endpoint, "__name__", "unknown")
                        path = route.path
                        missing_models.append(
                            f"{list(methods)} {path} -> {endpoint_name}"
                        )

        if missing_models:
            error_msg = (
                "❌ FastAPI Response Model Violations Found:\n"
                + "\n".join(f"  - {model}" for model in missing_models)
                + "\n\nAll FastAPI routes must have response_model"
                + " defined for OpenAPI compliance."
            )
            raise ValueError(error_msg)

        print("✅ All FastAPI routes have response_model defined")


class AppFactory:
    """Factory for creating ModularFastAPI applications with dynamic module loading."""

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
    ) -> ModularFastAPI:
        """Create and configure ModularApp (FastAPI + WebSocket apps).

        The core module is always enabled and loaded first, regardless of the
        enabled_module_names parameter. This ensures health checks and versioning
        are always available.

        Args:
            enabled_module_names: List of module names to enable. If None, all
                registered modules are enabled. Core is always enabled automatically.
                Use this to selectively load feature modules.

        Returns:
            tuple[ModularApp, list[FastWSAdapter]]: ModularApp instance (with ws_apps
                tracked internally) and list of module WS apps for backward compatibility

        Example:
            >>> factory = AppFactory()
            >>> # Load all modules (core + all feature modules)
            >>> app, ws_apps = factory.create_apps()
            >>> # Access WebSocket apps via ModularApp
            >>> assert app.ws_apps == ws_apps
            >>> # Load core + datafeed only
            >>> app, ws_apps = factory.create_apps(["datafeed"])
            >>> # Load only core module
            >>> app, ws_apps = factory.create_apps([])
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

        enabled_modules = self.registry.get_enabled_modules()

        @asynccontextmanager
        async def lifespan(app: ModularFastAPI) -> AsyncGenerator[None, None]:
            """Handle application startup and shutdown events."""

            # Validate all routes have response models
            app.validate_response_models()

            yield

            # Shutdown: Cleanup is handled by FastAPIAdapter
            print("🛑 FastAPI application shutdown complete")

        # Create ModularApp (FastAPI + WebSocket tracking)
        modular_app = ModularFastAPI(
            modules=enabled_modules,
            base_url=base_url,
            title="Trading API",
            description=(
                "A comprehensive trading API server with market data "
                "and portfolio management. Supports multiple API versions for "
                "backwards compatibility."
            ),
            version="1.0.0",
            lifespan=lifespan,
        )

        # Add CORS middleware
        modular_app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Allow all origins for development
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Add root endpoint with API information
        @modular_app.get("/", include_in_schema=False)
        async def root() -> dict[str, Any]:
            """Root endpoint with API version and navigation information."""
            return {
                "name": "Trading API",
                "version": "1.0.0",
                "current_api_version": "v1",
                "documentation": f"{base_url}/docs",
                "health": f"{base_url}/core/health",
                "versions": f"{base_url}/core/versions",
            }

        return modular_app
