"""Application Factory - Dynamic module composition.

Creates FastAPI application with configurable module loading.
Unified ModularApp class with async factory method pattern.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from trading_api.shared import Module, ModuleApp, ModuleRegistry, settings
from trading_api.shared.datastore_registry import DatastoreRegistry
from trading_api.shared.exception_handlers import register_exception_handlers
from trading_api.shared.provider_registry import ProviderRegistry

if TYPE_CHECKING:
    from trading_api.shared.provider_interface import Provider

# Configure logging for the application
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Set specific loggers to INFO level
logging.getLogger("trading_api").setLevel(logging.INFO)
logging.getLogger("uvicorn").setLevel(logging.INFO)
logging.getLogger("uvicorn.access").setLevel(logging.INFO)
# Suppress uvicorn's "Exception in ASGI application" logs
# (our exception handlers already log with full context)
logging.getLogger("uvicorn.error").setLevel(logging.CRITICAL)

# Module logger for app_factory
logger = logging.getLogger(__name__)


class ModularApp(FastAPI):
    """Self-configuring modular FastAPI application.

    Combines application runtime and factory responsibilities into a single class.
    Uses async build_modules() method for initialization after construction.

    Example:
        factory = AppFactory()
        app = await factory.create_app(
            enabled_module_names=["broker", "datafeed"],
            enabled_provider_names=["tws"],
        )
        await app.build_modules()  # Done automatically via lifespan
    """

    def __init__(
        self,
        *,
        base_url: str,
        enabled_modules: list[str] | None = None,
        enabled_providers: list[str] | None = None,
        enabled_datastores: list[str] | None = None,
        **kwargs: Any,
    ):
        """Initialize ModularApp.

        Args:
            base_url: API prefix for all routes
            enabled_modules: List of enabled module names (None = all)
            enabled_providers: List of enabled provider names (None = all)
            enabled_datastores: List of enabled datastore names (None = all)
            **kwargs: Additional FastAPI configuration
        """
        super().__init__(**kwargs)
        self.enabled_modules = enabled_modules or []
        self.enabled_providers = enabled_providers or []
        self.enabled_datastores = enabled_datastores or []

        self.base_url = base_url
        self.__providers: list[Provider] = []
        self.asyncapi_schema: dict[str, Any] = {}
        self.openapi_tags: list[dict[str, Any]] = []
        self._modules: list[Module] = []
        self._modules_apps: list[ModuleApp] = []

        # Create fresh registries (instance-level for test isolation)
        trading_app_dir = Path(__file__).parent
        self.module_registry = ModuleRegistry(trading_app_dir / "modules")
        self.provider_registry = ProviderRegistry(trading_app_dir / "providers")
        self.datastore_registry = DatastoreRegistry(trading_app_dir / "datastores")

        # Phase 1: Auto-discover modules, providers, and datastores
        self.module_registry.auto_discover(enabled_modules=self.enabled_modules)
        self.provider_registry.auto_discover(enabled_names=self.enabled_providers)
        self.datastore_registry.auto_discover(enabled_names=self.enabled_datastores)

    async def build_modules(self) -> None:
        """Initialize runtime assets and mount module routes."""
        logger.info(
            f"🚀 Starting ModularApp [modules={self.enabled_modules}] "
            f"[providers={self.enabled_providers}] [datastores={self.enabled_datastores}]..."
        )

        # Phase 2: Get datastore instances
        datastores = await self.datastore_registry.get_datastores()

        # Phase 3: Get provider instances for required capabilities
        self.__providers = await self.provider_registry.get_providers(
            self.module_registry.required_capabilities()
        )

        # Phase 4: Instantiate modules with providers and datastores
        self._modules = self.module_registry.get_modules(
            providers=self.__providers,
            datastores=datastores,
        )

        # Build module apps
        self._modules_apps = [ModuleApp(module) for module in self._modules]

        # Collect OpenAPI tags
        self.openapi_tags = [
            tag
            for app in self.modules_apps
            for version in app.api_versions
            if version.openapi_tags
            for tag in version.openapi_tags
        ]

        # Mount module routes
        for module_app in self.modules_apps:
            for api_app in module_app.api_versions:
                mount_path = (
                    f"{self.base_url}/{api_app.version}/{module_app.module.name}"
                )
                self.mount(mount_path, api_app)
                logger.info(
                    f"📦 Mounted module app '{module_app.module.name}-{api_app.version}' at {mount_path}"
                )

        # Start modules
        for module_app in self.modules_apps:
            module_app.start()
            logger.info(f"🔹 Module started: {module_app.module.name}")

        logger.info("✅ ModularApp started.")

    @property
    def modules_apps(self) -> list[ModuleApp]:
        if not self._modules_apps:
            self._modules_apps = [ModuleApp(module) for module in self._modules]
        return self._modules_apps

    def code_gen(
        self,
        clean_first: bool = False,
        output_dir: Path | None = None,
    ) -> None:
        """Generate OpenAPI and AsyncAPI specs and clients for all modules."""
        for module_app in self.modules_apps:
            module_app.gen_specs_and_clients(
                clean_first=clean_first, output_dir=output_dir
            )

    def openapi(self) -> dict[str, Any]:
        """Generate merged OpenAPI schema including all mounted modules."""
        if self.openapi_schema:
            return self.openapi_schema

        openapi_schema = super().openapi()

        for module_app in self.modules_apps:
            for api_app in module_app.api_versions:
                mount_path = (
                    f"{self.base_url}/{api_app.version}/{module_app.module.name}"
                )
                version_schema = api_app.openapi()

                # Merge paths with mount path prefix
                for path, path_item in version_schema.get("paths", {}).items():
                    full_path = f"{mount_path}{path}"
                    openapi_schema["paths"][full_path] = path_item

                # Merge components
                module_components = version_schema.get("components", {})
                if module_components:
                    if "components" not in openapi_schema:
                        openapi_schema["components"] = {}
                    for comp_type, comp_data in module_components.items():
                        if comp_type not in openapi_schema["components"]:
                            openapi_schema["components"][comp_type] = {}
                        openapi_schema["components"][comp_type].update(comp_data)

        self.openapi_schema = openapi_schema
        return openapi_schema

    def asyncapi(self) -> dict[str, Any]:
        """Generate merged AsyncAPI schema including all module WebSocket channels."""
        if self.asyncapi_schema:
            return self.asyncapi_schema

        merged_spec: dict[str, Any] = {
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

        for module_app in self.modules_apps:
            for ws_app in module_app.ws_versions:
                module_spec = ws_app.asyncapi()
                ws_endpoint = (
                    f"{self.base_url}/{ws_app.version}/{module_app.module.name}/ws"
                )

                for channel_path, channel_spec in dict(
                    module_spec.get("channels", {})
                ).items():
                    actual_channel = (
                        ws_endpoint
                        if channel_path == "/"
                        else ws_endpoint + channel_path
                    )
                    merged_spec["channels"][actual_channel] = channel_spec

                module_schemas = dict(module_spec.get("components", {})).get(
                    "schemas", {}
                )
                for schema_name, schema_def in module_schemas.items():
                    if schema_name not in merged_spec["components"]["schemas"]:
                        merged_spec["components"]["schemas"][schema_name] = schema_def

                module_messages = dict(module_spec.get("components", {})).get(
                    "messages", {}
                )
                for message_name, message_def in module_messages.items():
                    if message_name not in merged_spec["components"]["messages"]:
                        merged_spec["components"]["messages"][
                            message_name
                        ] = message_def

        self.asyncapi_schema = merged_spec
        return merged_spec

    def validate_model(self) -> None:
        """Validate that all routes have response_model defined for OpenAPI compliance."""
        missing_models = []

        for route in self.routes:
            if isinstance(route, APIRoute):
                if route.response_model is None:
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

    def shutdown(self) -> None:
        """Shutdown modules and providers."""
        logger.info("🛑 Stopping ModularApp...")

        for module_app in self.modules_apps:
            module_app.shutdown()
            logger.info(f"🔹 Module shutdown: {module_app.module.name}")

        for provider in self.__providers:
            provider.shutdown()

        logger.info("✅ ModularApp shutdown.")


@asynccontextmanager
async def lifespan(app: ModularApp) -> AsyncGenerator[None, None]:
    """Handle application startup and shutdown events."""
    await app.build_modules()
    app.validate_model()
    app.code_gen()

    yield

    app.shutdown()
    logger.info("🛑 FastAPI application shutdown complete")


class AppFactory:
    """Factory for creating ModularApp instances with dynamic module loading."""

    async def create_app(
        self,
        enabled_module_names: list[str] | None = None,
        enabled_provider_names: list[str] | None = None,
        enabled_datastores: list[str] | None = None,
    ) -> ModularApp:
        """Create and configure the ModularApp instance."""
        base_url = settings.API_PREFIX
        app = ModularApp(
            base_url=base_url,
            enabled_modules=enabled_module_names,
            enabled_providers=enabled_provider_names,
            enabled_datastores=enabled_datastores,
            lifespan=lifespan,
            openapi_url=f"{base_url}/openapi.json",
            docs_url=f"{base_url}/docs",
            redoc_url=f"{base_url}/redoc",
            title="Trading API",
            description=(
                "A comprehensive trading API server with market data "
                "and portfolio management. Supports multiple API versions for "
                "backwards compatibility."
            ),
            version="1.0.0",
        )

        # Add exception handlers
        register_exception_handlers(app)

        # Add CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.CORS_ORIGINS,
            allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Add root endpoint
        @app.get("/", include_in_schema=False)
        async def root() -> dict[str, Any]:
            """Root endpoint with API version and navigation information."""
            return {
                "name": "Trading API",
                "version": "1.0.0",
                "current_api_version": "v1",
                "documentation": f"{base_url}/docs",
            }

        return app
