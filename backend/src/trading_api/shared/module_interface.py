"""Module Protocol - Contract for pluggable modules.

Defines the interface that all modules (datafeed, broker, etc.) must implement
to integrate with the application factory pattern.
"""

import importlib
import json
import logging
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Annotated, Any, Type

from fastapi import Depends, FastAPI

from external_packages.fastws import Client
from trading_api.models.auth import UserData
from trading_api.shared.api import APIRouterInterface
from trading_api.shared.client_generation_service import ClientGenerationService
from trading_api.shared.middleware.auth import get_current_user_ws
from trading_api.shared.service_interface import ServiceInterface
from trading_api.shared.ws.fastws_adapter import FastWSAdapter
from trading_api.shared.ws.ws_route_interface import WsRouterInterface

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
    Abstract base class defining the interface for pluggable modules.
    """

    def __init__(self, versions: list[str] | None = None) -> None:
        self._enabled: bool = False

        # Auto-discover available versions if not specified
        if versions is None:
            versions = self._discover_versions()

        self._versions = versions

        # Import shared service (version-agnostic)
        self._service = self._import_service()

        # Import version-specific API and WS routers
        # Structure: {"v1": [router1, router2], "v2": [router1, router2]}
        self._api_routers: dict[str, APIRouterInterface] = {}
        self._ws_routers: dict[str, WsRouterInterface] = {}

        for version in versions:
            self._api_routers[version] = self._import_api_routers_for_version(version)
            ws_router = self._import_ws_routers_for_version(version)
            if ws_router is not None:
                self._ws_routers[version] = ws_router

    def _discover_versions(self) -> list[str]:
        """Auto-discover available versions from api/ and ws/ directories."""

        versions: set[str] = set()

        # Check api/ directory
        api_router = self.module_dir / "api"
        if api_router.exists():
            versions.update(
                d.stem for d in api_router.iterdir() if d.stem.startswith("v")
            )

        # Check ws/ directory
        ws_dir = self.module_dir / "ws"
        if ws_dir.exists():
            ws_versions = {
                d.stem
                for d in ws_dir.iterdir()
                if d.is_dir() and d.stem.startswith("v")
            }
            # Union: a version is valid if it exists in either api/ or ws/
            versions |= ws_versions

        if not versions:
            raise ValueError(f"No versions found for module {self.name}")

        return sorted(versions)  # ["v1", "v2", ...]

    def _get_import_path(self, name: str | list[str]) -> str:
        """Get the import path for this module."""
        if isinstance(name, list):
            name = ".".join(name)
        return (
            str(self.module_dir)
            .replace(str(Path.cwd() / "src"), "")
            .lstrip("/")
            .replace("/", ".")
            + f".{name}"
        )

    def _import_service(self) -> ServiceInterface:
        """Import version-agnostic service."""
        try:
            service_module = importlib.import_module(
                self._get_import_path("service"), package=__package__
            )
            # Get first exported class from module (convention: single service class)
            for attr_name in dir(service_module):
                attr = getattr(service_module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, ServiceInterface)
                    and attr is not ServiceInterface
                    and not attr_name.startswith("_")
                    and attr.__module__ == service_module.__name__
                ):
                    service_class: Type[ServiceInterface] = attr
                    return service_class(self.module_dir)

            raise ValueError(f"No service class found in {self.name}.service module")

        except ImportError as e:
            raise ValueError(f"Unable to load service for {self.name}: {e}")

    def _import_api_routers_for_version(self, version: str) -> APIRouterInterface:
        """Import API routers for a specific version."""
        try:
            # Import: from .api.{version} import *
            api_module_path = self._get_import_path(["api", version])
            api_module = importlib.import_module(api_module_path, package=__package__)

            # Get the API class (convention: first APIRouterInterface subclass exported)
            for attr_name in dir(api_module):
                if attr_name.startswith("_"):
                    continue
                attr = getattr(api_module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, APIRouterInterface)
                    and attr is not APIRouterInterface
                ):
                    api_class = attr
                    router = api_class(
                        service=self._service,
                        version=version,
                        prefix="",  # CRITICAL: Module mounting adds prefix
                        tags=[self.name],
                    )
                    return router

            raise ValueError(f"No APIRouterInterface class found in api.{version}")

        except ImportError as e:
            raise ValueError(
                f"Failed to load API {version} for {self.name}: "
                f"Module 'api.{version}' not found. Error: {e}"
            )

    def _import_ws_routers_for_version(self, version: str) -> WsRouterInterface | None:
        """Import WebSocket routers for a specific version."""
        try:
            ws_module_path = self._get_import_path(["ws", version])
            ws_module = importlib.import_module(ws_module_path, package=__package__)

            # Get the WS class (convention: first WsRouteInterface implementation)
            for attr_name in dir(ws_module):
                if attr_name.startswith("_"):
                    continue
                attr = getattr(ws_module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, WsRouterInterface)
                    and attr is not WsRouterInterface
                ):
                    ws_class = attr
                    return ws_class(service=self._service)

            return None
        except ImportError:
            # WebSocket support is optional
            return None

    @property
    def api_routers(self) -> dict[str, APIRouterInterface]:
        """API routers organized by version."""
        return self._api_routers

    @property
    def ws_routers(self) -> dict[str, WsRouterInterface]:
        """WebSocket routers organized by version."""
        return self._ws_routers

    @property
    def versions(self) -> list[str]:
        """Available versions for this module."""
        return self._versions

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
    def name(self) -> str:
        """Return the unique name identifier for this module.

        Returns:
            str: "broker"
        """
        return self.module_dir.name

    @property
    def service(self) -> ServiceInterface:
        """Return the service instance for this module.

        This should be lazy-loaded on first access.

        Returns:
            Any: Service instance (e.g., BrokerService, DatafeedService)
        """
        return self._service

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
    def tags(self) -> list[dict[str, str]]:
        """Get OpenAPI tags for this module.

        Returns:
            list[dict[str, str]]: List of OpenAPI tag dictionaries with 'name'
        """
        ...

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

        # Use module_dir if output_dir not provided
        if output_dir is None:
            output_dir = self.module_dir

        specs_dir = output_dir / "specs_generated"
        clients_dir = output_dir / "client_generated"
        templates_dir = self.module_dir.parent.parent / "shared" / "templates"

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

                success, missing = client_gen.generate_module_client(openapi_file)

                if success:
                    # Format generated code
                    # Note: Module.gen_specs_and_clients creates non-versioned files
                    # Extract module_name from spec filename (no version)
                    openapi_file.stem.replace("_openapi", "")
                    # Since no version in filename, pass empty version to skip formatting
                    # This method appears deprecated - ModuleApp.gen_specs_and_clients is used instead
                    logger.info(f"✅ Generated Python client for '{self.name}'")
                    logger.warning(
                        "⚠️  Module.gen_specs_and_clients may be deprecated - "
                        "use ModuleApp.gen_specs_and_clients for versioned generation"
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


class ModuleApp:
    """Encapsulates FastAPI and FastWSAdapter apps for a module."""

    def __init__(self, module: Module):
        self.module = module
        self.versions: dict[str, tuple[FastAPI, FastWSAdapter | None]] = {}
        # Register module's API routers with module_path prefix
        # so OpenAPI spec reflects the real accessible routes
        for version, api_router in module.api_routers.items():
            api_app = FastAPI(
                title=f"{module.name.title()} API",
                description=f"REST API app for {module.name} module",
                version=version,
                openapi_url="/openapi.json",
                docs_url="/docs",
                redoc_url="/redoc",
                openapi_tags=module.tags,
            )
            api_app.include_router(api_router)

            ws_app: FastWSAdapter | None = None
            if module.ws_routers:
                _ws_app = FastWSAdapter(
                    title=f"{module.name.title()} WebSockets",
                    description=f"Real-time WebSocket app for {module.name} module",
                    version=version,
                    asyncapi_url="/ws/asyncapi.json",
                    asyncapi_docs_url="/ws/asyncapi",
                    heartbeat_interval=30.0,
                    max_connection_lifespan=3600.0,
                )

                for version, ws_routers in module.ws_routers.items():
                    for ws_router in ws_routers:
                        _ws_app.include_router(ws_router)

                @api_app.websocket("/ws")
                async def _(
                    user_data: Annotated[UserData, Depends(get_current_user_ws)],
                    client: Annotated[Client, Depends(_ws_app.manage)],
                ) -> None:
                    f"""WebSocket endpoint for {module.name} real-time streaming"""
                    client.user_data = user_data
                    await _ws_app.serve(client)

                ws_app = _ws_app

            self.versions[version] = (api_app, ws_app)

    @property
    def api_versions(self) -> list[FastAPI]:
        return [version[0] for version in self.versions.values()]

    @property
    def ws_versions(self) -> list[FastWSAdapter]:
        return [
            version[1] for version in self.versions.values() if version[1] is not None
        ]

    def gen_specs_and_clients(
        self,
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

        moduleName: str = self.module.name
        # Use module_dir if output_dir not provided
        if output_dir is None:
            output_dir = self.module.module_dir

        specs_dir = output_dir / "specs_generated"
        clients_dir = output_dir / "client_generated"
        templates_dir = self.module.module_dir.parent.parent / "shared" / "templates"

        # Clean existing files if requested
        if clean_first:
            if specs_dir.exists():
                shutil.rmtree(specs_dir)
                logger.info(f"🧹 Cleaned specs for '{moduleName}'")

            # Clean this module's client directory
            if clients_dir.exists():
                shutil.rmtree(clients_dir)
                logger.info(f"🧹 Cleaned clients for '{moduleName}'")

        # Generate OpenAPI spec from the provided app
        for version, (api_app, ws_app) in self.versions.items():
            openapi_schema = api_app.openapi()
            specs_dir.mkdir(parents=True, exist_ok=True)
            openapi_file = specs_dir / f"{moduleName}_{version}_openapi.json"

            # Compare with existing spec (same logic as lifespan)
            should_update_openapi: bool = True
            if openapi_file.exists() and not clean_first:
                try:
                    with open(openapi_file, "r") as f:
                        existing_openapi = json.load(f)
                        differences = _compare_specs(existing_openapi, openapi_schema)
                        if len(differences) > 0:
                            logger.info(
                                f"🔄 OpenAPI spec changes detected for '{moduleName}':"
                            )
                            for diff in differences:
                                logger.info(f"   • {diff}")
                        else:
                            should_update_openapi = False
                            logger.info(
                                f"✅ No changes in OpenAPI spec for '{moduleName}'"
                            )
                except Exception as e:
                    logger.warning(f"⚠️  Could not read existing OpenAPI spec: {e}")
            else:
                logger.info(f"📝 Creating new OpenAPI spec for '{moduleName}'")

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

                    success, missing = client_gen.generate_module_client(openapi_file)

                    if success:
                        # Format generated code
                        if client_gen.format_generated_code(moduleName, version):
                            logger.info(
                                f"✅ Generated Python client for '{moduleName} {version}'"
                            )
                        else:
                            logger.warning(
                                f"⚠️  Generated Python client for '{moduleName} {version}' "
                                "(formatting failed)"
                            )

                        # Update clients __init__.py with all available clients
                        client_gen.update_clients_index()
                    else:
                        logger.warning(
                            f"⚠️  Python client for '{moduleName} {version}' missing routes: {missing}"
                        )
                except Exception as e:
                    logger.error(
                        f"⚠️  Failed to generate Python client for '{moduleName} {version}': {e}"
                    )
                    raise

            # Generate AsyncAPI spec if ws_app is provided (same logic as lifespan)
            if ws_app is not None:
                asyncapi_schema = ws_app.asyncapi()
                asyncapi_file = specs_dir / f"{moduleName}_{version}_asyncapi.json"

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
                                        f"🔄 AsyncAPI spec changes detected for '{moduleName}':"
                                    )
                                    for diff in differences:
                                        logger.info(f"   • {diff}")
                                else:
                                    should_update_asyncapi = False
                                    logger.info(
                                        f"✅ No changes in AsyncAPI spec for '{moduleName}'"
                                    )
                        except Exception as e:
                            logger.warning(
                                f"⚠️  Could not read existing AsyncAPI spec: {e}"
                            )
                    else:
                        logger.info(f"📝 Creating new AsyncAPI spec for '{moduleName}'")

                    # Write spec only if needed
                    if should_update_asyncapi:
                        with open(asyncapi_file, "w") as f:
                            json.dump(asyncapi_schema, f, indent=2)
                        logger.info(f"✅ Updated AsyncAPI spec: {asyncapi_file}")

                except Exception as e:
                    logger.error(
                        f"⚠️  Failed to process AsyncAPI spec for '{moduleName}': {e}"
                    )

    def start(self) -> None:
        """Start the WebSocket app if available."""
        for api_app, ws_app in self.versions.values():
            if ws_app is not None:
                ws_app.setup(api_app)
