"""Client Generation Service - Automatic Python HTTP client generation.

Service for generating type-safe Python HTTP clients from OpenAPI specifications.
Used during module startup to automatically regenerate clients when specs change.
"""

import json
import logging
import subprocess
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)


def _extract_schema_name(ref: str) -> str:
    """Extract schema name from $ref string.

    Example: "#/components/schemas/PlacedOrder" -> "PlacedOrder"
    """
    return ref.split("/")[-1]


def _is_enum_type(schema: dict[str, Any], components: dict[str, Any]) -> bool:
    """Check if a schema represents an Enum type.

    Args:
        schema: OpenAPI schema dictionary
        components: OpenAPI components dictionary

    Returns:
        True if the schema is an Enum type
    """
    if "$ref" in schema:
        schema_name = _extract_schema_name(schema["$ref"])
        resolved_schema = components.get("schemas", {}).get(schema_name, {})
        return "enum" in resolved_schema

    return "enum" in schema


def _get_python_type(schema: dict[str, Any], components: dict[str, Any]) -> str:
    """Convert OpenAPI schema to Python type hint.

    Handles:
    - $ref -> Model name from trading_api.models
    - array -> list[Type]
    - object -> dict[str, Any]
    - primitives -> str, int, float, bool
    """
    if "$ref" in schema:
        model_name = _extract_schema_name(schema["$ref"])
        if model_name.startswith("Body_"):
            return "dict[str, Any]"
        return model_name

    schema_type = schema.get("type", "any")

    if schema_type == "array":
        items_type = _get_python_type(schema.get("items", {}), components)
        return f"list[{items_type}]"
    elif schema_type == "object":
        return "dict[str, Any]"
    elif schema_type == "string":
        return "str"
    elif schema_type == "integer":
        return "int"
    elif schema_type == "number":
        return "float"
    elif schema_type == "boolean":
        return "bool"
    else:
        return "Any"


def _expand_body_schema(
    body_schema_name: str, components: dict[str, Any]
) -> list[dict[str, Any]] | None:
    """Expand Body_ schema into individual parameters.

    Args:
        body_schema_name: Name of the Body_ schema (e.g., "Body_editPositionBrackets")
        components: OpenAPI components dictionary

    Returns:
        List of parameter dicts or None if not a Body_ schema
    """
    if not body_schema_name.startswith("Body_"):
        return None

    schemas = components.get("schemas", {})
    body_schema = schemas.get(body_schema_name)
    if not body_schema:
        return None

    properties = body_schema.get("properties", {})
    required_fields = set(body_schema.get("required", []))
    body_params = []

    for field_name, field_schema in properties.items():
        field_type = _get_python_type(field_schema, components)
        is_enum = _is_enum_type(field_schema, components)
        body_params.append(
            {
                "name": field_name,
                "in": "body",
                "required": field_name in required_fields,
                "type": field_type,
                "description": field_schema.get("description", ""),
                "is_enum": is_enum,
            }
        )

    return body_params


def _extract_operations(spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract all operations from OpenAPI spec.

    Returns list of operation dicts with:
    - operation_id: str
    - method: str (get, post, put, delete, etc.)
    - path: str
    - parameters: list[dict]
    - request_body: dict | None
    - response_type: str (Python type hint)
    """
    operations = []
    paths = spec.get("paths", {})
    components = spec.get("components", {})

    for path, path_item in paths.items():
        for method, operation in path_item.items():
            if method not in ["get", "post", "put", "delete", "patch"]:
                continue

            operation_id = operation.get(
                "operationId", f"{method}_{path.replace('/', '_')}"
            )

            parameters = []
            for param in operation.get("parameters", []):
                param_schema = param.get("schema", {})
                param_type = _get_python_type(param_schema, components)
                is_enum = _is_enum_type(param_schema, components)
                parameters.append(
                    {
                        "name": param["name"],
                        "in": param.get("in", "query"),
                        "required": param.get("required", False),
                        "type": param_type,
                        "description": param.get("description", ""),
                        "is_enum": is_enum,
                    }
                )

            request_body = None
            if "requestBody" in operation:
                content = operation["requestBody"].get("content", {})
                json_content = content.get("application/json", {})
                if "schema" in json_content:
                    schema = json_content["schema"]

                    if "$ref" in schema:
                        schema_name = _extract_schema_name(schema["$ref"])
                        if schema_name.startswith("Body_"):
                            body_params = _expand_body_schema(schema_name, components)
                            if body_params:
                                parameters.extend(body_params)
                                request_body = {
                                    "type": "expanded",
                                    "required": True,
                                    "fields": [p["name"] for p in body_params],
                                }
                        else:
                            request_body = {
                                "type": schema_name,
                                "required": operation["requestBody"].get(
                                    "required", True
                                ),
                            }
                    else:
                        body_type = _get_python_type(schema, components)
                        request_body = {
                            "type": body_type,
                            "required": operation["requestBody"].get("required", True),
                        }

            response_type = "Any"
            responses = operation.get("responses", {})
            success_response = responses.get("200", responses.get("201", {}))
            if "content" in success_response:
                json_content = success_response["content"].get("application/json", {})
                if "schema" in json_content:
                    response_type = _get_python_type(json_content["schema"], components)

            operations.append(
                {
                    "operation_id": operation_id,
                    "method": method.upper(),
                    "path": path,
                    "parameters": parameters,
                    "request_body": request_body,
                    "response_type": response_type,
                    "description": operation.get(
                        "description", operation.get("summary", "")
                    ),
                }
            )

    return operations


def _collect_model_imports(operations: list[dict[str, Any]]) -> set[str]:
    """Collect all model names used in operations for import statements."""
    models = set()

    for op in operations:
        response_type = op["response_type"]
        if "list[" in response_type:
            model = response_type.replace("list[", "").replace("]", "")
            if model not in [
                "str",
                "int",
                "float",
                "bool",
                "Any",
                "dict[str, Any]",
            ] and not model.startswith("Body_"):
                models.add(model)
        elif response_type not in [
            "str",
            "int",
            "float",
            "bool",
            "Any",
            "dict[str, Any]",
        ] and not response_type.startswith("Body_"):
            models.add(response_type)

        if op["request_body"]:
            body_type = op["request_body"]["type"]
            if (
                body_type != "expanded"
                and body_type
                not in [
                    "str",
                    "int",
                    "float",
                    "bool",
                    "Any",
                    "dict[str, Any]",
                ]
                and not body_type.startswith("Body_")
            ):
                models.add(body_type)

        for param in op["parameters"]:
            param_type = param["type"]
            if param_type not in [
                "str",
                "int",
                "float",
                "bool",
                "Any",
                "dict[str, Any]",
            ] and not param_type.startswith("Body_"):
                models.add(param_type)

    return models


class ClientGenerationService:
    """Service for generating Python HTTP clients from OpenAPI specifications."""

    def __init__(self, clients_dir: Path, templates_dir: Path):
        """Initialize the client generation service.

        Args:
            clients_dir: Directory where generated clients will be written
            templates_dir: Directory containing Jinja2 templates
        """
        self.clients_dir = clients_dir
        self.templates_dir = templates_dir

        self.clients_dir.mkdir(parents=True, exist_ok=True)

        self.template_env = Environment(
            loader=FileSystemLoader(templates_dir),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def generate_module_client(self, spec_path: Path) -> tuple[bool, list[str]]:
        """Generate Python HTTP client for a single module.

        Args:
            module_name: Name of the module (e.g., "broker", "datafeed")
            spec_path: Path to the module's OpenAPI spec file

        Returns:
            Tuple of (success, missing_routes)
        """
        module_name_version = spec_path.stem.replace("_openapi", "")
        module_name = module_name_version.rsplit("_", 1)[0]
        module_version = module_name_version.rsplit("_", 1)[1]
        try:
            with open(spec_path) as f:
                spec: dict[str, Any] = json.load(f)

            operations = _extract_operations(spec)
            models = _collect_model_imports(operations)

            template = self.template_env.get_template("python_client.py.j2")

            client_code = template.render(
                module_name=module_name,
                class_name=f"{module_name.capitalize()}Client",
                operations=operations,
                models=sorted(models),
            )

            output_file = self.clients_dir / f"{module_name}_{module_version}_client.py"
            output_file.write_text(client_code)

            success, missing_routes = self._verify_all_routes_generated(
                spec, operations
            )

            return success, missing_routes

        except Exception as e:
            logger.error(f"Failed to generate client for '{module_name}': {e}")
            return False, []

    def update_clients_index(self) -> None:
        """Update __init__.py with exports for all generated clients.

        Scans the clients directory for all *_client.py files and regenerates
        the __init__.py file with proper imports and exports.
        """
        try:
            client_files = sorted(self.clients_dir.glob("*_client.py"))

            if not client_files:
                logger.warning("No client files found to export in __init__.py")
                return

            imports = []
            exports = []

            for client_file in client_files:
                module_name = client_file.stem.replace("_client", "")
                class_name = f"{module_name.capitalize()}Client"
                imports.append(f"from .{client_file.stem} import {class_name}")
                exports.append(f'    "{class_name}",')

            init_content = f'''"""
Generated Python HTTP clients for inter-module communication.

These clients enable type-safe HTTP communication when modules run as
separate processes/services (multi-process architecture).

Auto-generated during module startup when OpenAPI specs change.
DO NOT EDIT MANUALLY.
"""

{chr(10).join(imports)}

__all__ = [
{chr(10).join(exports)}
]
'''

            output_file = self.clients_dir / "__init__.py"
            output_file.write_text(init_content)

            logger.info(f"✅ Updated clients index: {len(client_files)} clients")

        except Exception as e:
            logger.error(f"Failed to update clients __init__.py: {e}")

    def format_generated_code(self, module_name: str) -> bool:
        """Format generated client code using autoflake, black, and isort.

        Args:
            module_name: Name of the module whose client should be formatted

        Returns:
            True if formatting succeeded, False otherwise
        """
        client_file = self.clients_dir / f"{module_name}_client.py"
        if not client_file.exists():
            return False

        try:
            subprocess.run(
                [
                    "autoflake",
                    "--remove-all-unused-imports",
                    "--remove-unused-variables",
                    "--in-place",
                    str(client_file),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            subprocess.run(
                ["black", str(client_file)],
                check=True,
                capture_output=True,
                text=True,
            )

            subprocess.run(
                ["isort", str(client_file)],
                check=True,
                capture_output=True,
                text=True,
            )

            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to format client for '{module_name}': {e}")
            return False
        except FileNotFoundError:
            logger.warning(
                "Code formatting tools not found (autoflake, black, isort). "
                "Skipping formatting."
            )
            return True

    def _verify_all_routes_generated(
        self, spec: dict[str, Any], operations: list[dict[str, Any]]
    ) -> tuple[bool, list[str]]:
        """Verify that all routes from OpenAPI spec were generated.

        Args:
            spec: OpenAPI specification
            operations: Generated operations list

        Returns:
            Tuple of (all_routes_present, missing_routes)
        """
        spec_operation_ids = set()

        for path, path_item in spec.get("paths", {}).items():
            for method in ["get", "post", "put", "delete", "patch"]:
                if method in path_item:
                    operation = path_item[method]
                    operation_id = operation.get(
                        "operationId", f"{method}_{path.replace('/', '_')}"
                    )
                    spec_operation_ids.add(operation_id)

        generated_operation_ids = {op["operation_id"] for op in operations}

        missing = sorted(spec_operation_ids - generated_operation_ids)

        return len(missing) == 0, missing
