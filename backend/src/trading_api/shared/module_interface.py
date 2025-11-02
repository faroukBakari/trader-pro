"""Module Protocol - Contract for pluggable modules.

Defines the interface that all modules (datafeed, broker, etc.) must implement
to integrate with the application factory pattern.
"""

import json
import logging
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any, AsyncGenerator

from fastapi import Depends, FastAPI
from fastapi.routing import APIRouter

from external_packages.fastws import Client
from trading_api.shared.client_generation_service import ClientGenerationService
from trading_api.shared.plugins.fastws_adapter import FastWSAdapter
from trading_api.shared.ws.router_interface import WsRouteInterface, WsRouteService

# Module logger for app_factory
logger = logging.getLogger(__name__)


def _compare_specs(old_spec: dict[str, Any], new_spec: dict[str, Any]) -> list[str]:
    """Compare two API specification dictionaries for meaningful differences.

    Ignores metadata fields like timestamps and focuses on structural changes.
    Works with both OpenAPI and AsyncAPI specifications.

    Args:
        old_spec: The existing specification
        new_spec: The newly generated specification

    Returns:
        List of difference descriptions (empty list if no changes)
    """
    differences = []

    # Compare version
    old_version = old_spec.get("info", {}).get("version")
    new_version = new_spec.get("info", {}).get("version")
    if old_version != new_version:
        differences.append(f"Version changed: {old_version} → {new_version}")

    # Compare paths (OpenAPI - REST endpoints)
    if "paths" in new_spec or "paths" in old_spec:
        old_paths = set(old_spec.get("paths", {}).keys())
        new_paths = set(new_spec.get("paths", {}).keys())

        added_paths = new_paths - old_paths
        removed_paths = old_paths - new_paths

        if added_paths:
            differences.append(f"Added endpoints: {', '.join(sorted(added_paths))}")
        if removed_paths:
            differences.append(f"Removed endpoints: {', '.join(sorted(removed_paths))}")

        # Compare path operations for common endpoints
        common_paths = old_paths & new_paths
        for path in common_paths:
            old_methods = set(old_spec.get("paths", {}).get(path, {}).keys())
            new_methods = set(new_spec.get("paths", {}).get(path, {}).keys())

            if old_methods != new_methods:
                differences.append(
                    f"Methods changed for {path}: {old_methods} → {new_methods}"
                )

    # Compare channels (AsyncAPI - WebSocket channels)
    if "channels" in new_spec or "channels" in old_spec:
        old_channels = set(old_spec.get("channels", {}).keys())
        new_channels = set(new_spec.get("channels", {}).keys())

        added_channels = new_channels - old_channels
        removed_channels = old_channels - new_channels

        if added_channels:
            differences.append(f"Added channels: {', '.join(sorted(added_channels))}")
        if removed_channels:
            differences.append(
                f"Removed channels: {', '.join(sorted(removed_channels))}"
            )

    # Compare schemas/components
    old_schemas = old_spec.get("components", {}).get("schemas", {})
    new_schemas = new_spec.get("components", {}).get("schemas", {})

    old_schema_names = set(old_schemas.keys())
    new_schema_names = set(new_schemas.keys())

    added_schemas = new_schema_names - old_schema_names
    removed_schemas = old_schema_names - new_schema_names

    if added_schemas:
        differences.append(f"Added models: {', '.join(sorted(added_schemas))}")
    if removed_schemas:
        differences.append(f"Removed models: {', '.join(sorted(removed_schemas))}")

    # Check for schema changes in common models
    common_schemas = old_schema_names & new_schema_names
    for schema_name in common_schemas:
        old_props = set(old_schemas[schema_name].get("properties", {}).keys())
        new_props = set(new_schemas[schema_name].get("properties", {}).keys())

        if old_props != new_props:
            differences.append(f"Schema '{schema_name}' properties changed")

    return differences


class Module(ABC):
    """
    TBD
    """

    def __init__(self) -> None:
        self._enabled: bool = False

    def gen_specs_and_clients(
        self,
        api_app: FastAPI,
        ws_app: FastWSAdapter | None = None,
        clean_first: bool = False,
        output_dir: Path | None = None,
    ) -> None:
        """Generate OpenAPI/AsyncAPI specs and Python HTTP client for this module.

        This method generates the module's OpenAPI specification and corresponding
        Python HTTP client from the provided FastAPI app instance.
        If ws_app is provided, also generates AsyncAPI specification.
        Uses the same logic as the lifespan event for consistency.

        Note: WebSocket routers are generated automatically at module initialization
        (see ws.py files), so this method does not need to generate them.

        Args:
            api_app: FastAPI app instance with all routers registered
            ws_app: Optional FastWSAdapter instance for WebSocket spec generation
            clean_first: If True, removes existing specs and clients before generation
            output_dir: Optional directory for output files (defaults to self.module_dir)
                       Generates:
                       - ${output_dir}/specs_generated/${module_name}_openapi.json
                       - ${output_dir}/specs_generated/${module_name}_asyncapi.json
                       - ${output_dir}/client_generated/${module_name}_client.py
                       - ${output_dir}/client_generated/__init__.py
        """
        import shutil

        # Use module_dir if output_dir not provided
        if output_dir is None:
            output_dir = self.module_dir

        specs_dir = output_dir / "specs_generated"
        clients_dir = output_dir / "client_generated"
        templates_dir = Path(__file__).parent / "templates"

        # Clean existing files if requested
        if clean_first:
            if specs_dir.exists():
                shutil.rmtree(specs_dir)
                logger.info(f"🧹 Cleaned specs for '{self.name}'")

            # Clean this module's client directory
            if clients_dir.exists():
                shutil.rmtree(clients_dir)
                logger.info(f"🧹 Cleaned clients for '{self.name}'")

        # Generate OpenAPI spec from the provided app
        openapi_schema = api_app.openapi()
        specs_dir.mkdir(parents=True, exist_ok=True)
        openapi_file = specs_dir / f"{self.name}_openapi.json"

        # Compare with existing spec (same logic as lifespan)
        should_update_openapi: bool = True
        if openapi_file.exists() and not clean_first:
            try:
                with open(openapi_file, "r") as f:
                    existing_openapi = json.load(f)
                    differences = _compare_specs(existing_openapi, openapi_schema)
                    if len(differences) > 0:
                        logger.info(
                            f"🔄 OpenAPI spec changes detected for '{self.name}':"
                        )
                        for diff in differences:
                            logger.info(f"   • {diff}")
                    else:
                        should_update_openapi = False
                        logger.info(f"✅ No changes in OpenAPI spec for '{self.name}'")
            except Exception as e:
                logger.warning(f"⚠️  Could not read existing OpenAPI spec: {e}")
        else:
            logger.info(f"📝 Creating new OpenAPI spec for '{self.name}'")

        # Write spec only if needed
        if should_update_openapi:
            with open(openapi_file, "w") as f:
                json.dump(openapi_schema, f, indent=2)
            logger.info(f"✅ Updated OpenAPI spec: {openapi_file}")

            # Generate Python HTTP client from updated spec (same logic as lifespan)
            try:
                client_gen = ClientGenerationService(
                    clients_dir=clients_dir, templates_dir=templates_dir
                )

                success, missing = client_gen.generate_module_client(
                    self.name, openapi_file
                )

                if success:
                    # Format generated code
                    if client_gen.format_generated_code(self.name):
                        logger.info(f"✅ Generated Python client for '{self.name}'")
                    else:
                        logger.warning(
                            f"⚠️  Generated Python client for '{self.name}' "
                            "(formatting failed)"
                        )

                    # Update clients __init__.py with all available clients
                    client_gen.update_clients_index()
                else:
                    logger.warning(
                        f"⚠️  Python client for '{self.name}' missing routes: {missing}"
                    )
            except Exception as e:
                logger.error(
                    f"⚠️  Failed to generate Python client for '{self.name}': {e}"
                )
                raise

        # Generate AsyncAPI spec if ws_app is provided (same logic as lifespan)
        if ws_app is not None:
            asyncapi_schema = ws_app.asyncapi()
            asyncapi_file = specs_dir / f"{self.name}_asyncapi.json"

            try:
                # Compare specs if existing spec was loaded
                should_update_asyncapi: bool = True
                if asyncapi_file.exists() and not clean_first:
                    try:
                        with open(asyncapi_file, "r") as f:
                            existing_asyncapi = json.load(f)
                            differences = _compare_specs(
                                existing_asyncapi, asyncapi_schema
                            )
                            if len(differences) > 0:
                                logger.info(
                                    f"🔄 AsyncAPI spec changes detected for '{self.name}':"
                                )
                                for diff in differences:
                                    logger.info(f"   • {diff}")
                            else:
                                should_update_asyncapi = False
                                logger.info(
                                    f"✅ No changes in AsyncAPI spec for '{self.name}'"
                                )
                    except Exception as e:
                        logger.warning(
                            f"⚠️  Could not read existing AsyncAPI spec: {e}"
                        )
                else:
                    logger.info(f"📝 Creating new AsyncAPI spec for '{self.name}'")

                # Write spec only if needed
                if should_update_asyncapi:
                    with open(asyncapi_file, "w") as f:
                        json.dump(asyncapi_schema, f, indent=2)
                    logger.info(f"✅ Updated AsyncAPI spec: {asyncapi_file}")

            except Exception as e:
                logger.error(
                    f"⚠️  Failed to process AsyncAPI spec for '{self.name}': {e}"
                )

    def create_app(
        self,
    ) -> tuple[FastAPI, FastWSAdapter | None]:
        """Get or create the module's FastAPI application.

        Lazy loads the app on first access for resource efficiency.

        Returns:
            tuple[FastAPI, FastWSAdapter | None]: The FastAPI application
            instance and optional WebSocket adapter
        """

        ws_app: FastWSAdapter | None = None

        @asynccontextmanager
        async def lifespan(api_app: FastAPI) -> AsyncGenerator[None, None]:
            nonlocal ws_app
            """Handle module application startup and shutdown events."""

            # Generate specs and clients using the app being created
            # This ensures consistent logic and avoids redundant app creation
            self.gen_specs_and_clients(api_app=api_app, ws_app=ws_app)

            if ws_app is not None:
                ws_app.setup(api_app)

            yield

            # Shutdown: Cleanup is handled by FastAPIAdapter
            logger.info(f"🛑 FastAPI <{self.name}> application shutdown complete")

        app = FastAPI(
            title=f"{self.name.title()} API",
            description=f"REST API app for {self.name} module",
            version="1.0.0",
            openapi_url="/openapi.json",
            docs_url="/docs",
            redoc_url="/redoc",
            openapi_tags=self.openapi_tags,
            lifespan=lifespan,
        )
        # Register module's API routers with module_path prefix
        # so OpenAPI spec reflects the real accessible routes
        for api_router in self.api_routers:
            app.include_router(api_router)

        if self.ws_routers:
            ws_app = FastWSAdapter(
                title=f"{self.name.title()} WebSockets",
                description=f"Real-time WebSocket app for {self.name} module",
                version="1.0.0",
                asyncapi_url="ws/asyncapi.json",
                asyncapi_docs_url="ws/asyncapi",
                heartbeat_interval=30.0,
                max_connection_lifespan=3600.0,
            )

            for ws_router in self.ws_routers:
                ws_app.include_router(ws_router)

            @app.websocket("/ws")
            async def _(
                client: Annotated[Client, Depends(ws_app.manage)],
            ) -> None:
                f"""WebSocket endpoint for {self.name} real-time streaming"""
                await ws_app.serve(client)

        return app, ws_app

    def enable(self) -> None:
        """Enable the module for loading."""
        self._enabled = True

    @property
    def enabled(self) -> bool:
        """Check if the module is enabled.

        Returns:
            bool: True if the module is enabled, False otherwise
        """
        return self._enabled

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the unique name identifier for this module.

        Returns:
            str: Module name (e.g., "datafeed", "broker")
        """
        ...

    @property
    @abstractmethod
    def module_dir(self) -> Path:
        """Return the directory path for this module.

        Returns:
            Path: Module directory path
        """
        ...

    @property
    @abstractmethod
    def service(self, *args: Any, **kwargs: Any) -> WsRouteService:
        """Return the service instance for this module.

        This should be lazy-loaded on first access.

        Returns:
            Any: Service instance (e.g., BrokerService, DatafeedService)
        """
        ...

    @property
    @abstractmethod
    def api_routers(self, *args: Any, **kwargs: Any) -> list[APIRouter]:
        """Get the FastAPI routers for this module's REST API endpoints.

        Returns:
            list[APIRouter]: Module's FastAPI router instances
        """
        ...

    @property
    @abstractmethod
    def ws_routers(self, *args: Any, **kwargs: Any) -> list[WsRouteInterface]:
        """Get all WebSocket routers for this module's real-time endpoints.

        Returns:
            list[WsRouteInterface]: List of WebSocket router instances
        """
        ...

    @property
    @abstractmethod
    def openapi_tags(self) -> list[dict[str, str]]:
        """Get OpenAPI tags for this module.

        Returns:
            list[dict[str, str]]: List of OpenAPI tag dictionaries with 'name'
        """
        ...
