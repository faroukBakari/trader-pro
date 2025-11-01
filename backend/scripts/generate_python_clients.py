#!/usr/bin/env python3
"""
Generate Python HTTP clients from per-module OpenAPI specifications.

This script generates type-safe async HTTP clients for inter-module communication
when modules run as separate processes/services. Clients reuse existing models
from trading_api.models.* to maintain consistency.

Usage:
    poetry run python scripts/generate_python_clients.py

Output:
    - src/trading_api/clients/{module}_client.py
    - src/trading_api/clients/__init__.py
"""

import json

# Add trading_api to path for imports
import sys
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from trading_api.shared.utils import discover_modules


def load_openapi_spec(spec_path: Path) -> dict[str, Any]:
    """Load OpenAPI specification from JSON file."""
    with open(spec_path) as f:
        result: dict[str, Any] = json.load(f)
        return result


def extract_schema_name(ref: str) -> str:
    """Extract schema name from $ref string.

    Example: "#/components/schemas/PlacedOrder" -> "PlacedOrder"
    """
    return ref.split("/")[-1]


def is_enum_type(schema: dict[str, Any], components: dict[str, Any]) -> bool:
    """Check if a schema represents an Enum type.

    Args:
        schema: OpenAPI schema dictionary
        components: OpenAPI components dictionary

    Returns:
        True if the schema is an Enum type
    """
    # Check if it's a $ref
    if "$ref" in schema:
        schema_name = extract_schema_name(schema["$ref"])
        # Look up the schema in components
        resolved_schema = components.get("schemas", {}).get(schema_name, {})
        # Check if it has an "enum" field
        return "enum" in resolved_schema

    # Direct enum definition
    return "enum" in schema


def get_python_type(schema: dict[str, Any], components: dict[str, Any]) -> str:
    """Convert OpenAPI schema to Python type hint.

    Handles:
    - $ref -> Model name from trading_api.models
    - array -> list[Type]
    - object -> dict[str, Any]
    - primitives -> str, int, float, bool
    """
    if "$ref" in schema:
        model_name = extract_schema_name(schema["$ref"])
        # Skip auto-generated Body_ schemas from FastAPI
        if model_name.startswith("Body_"):
            return "dict[str, Any]"
        return model_name

    schema_type = schema.get("type", "any")

    if schema_type == "array":
        items_type = get_python_type(schema.get("items", {}), components)
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


def expand_body_schema(
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
        field_type = get_python_type(field_schema, components)
        is_enum = is_enum_type(field_schema, components)
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


def extract_operations(spec: dict[str, Any]) -> list[dict[str, Any]]:
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

            # Extract operation ID
            operation_id = operation.get(
                "operationId", f"{method}_{path.replace('/', '_')}"
            )

            # Extract parameters
            parameters = []
            for param in operation.get("parameters", []):
                param_schema = param.get("schema", {})
                param_type = get_python_type(param_schema, components)
                is_enum = is_enum_type(param_schema, components)
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

            # Extract request body
            request_body = None
            if "requestBody" in operation:
                content = operation["requestBody"].get("content", {})
                json_content = content.get("application/json", {})
                if "schema" in json_content:
                    schema = json_content["schema"]

                    # Check if this is a $ref to a Body_ schema that should be expanded
                    if "$ref" in schema:
                        schema_name = extract_schema_name(schema["$ref"])
                        if schema_name.startswith("Body_"):
                            # Expand Body_ schema into individual parameters
                            body_params = expand_body_schema(schema_name, components)
                            if body_params:
                                # Add expanded body parameters to parameters list
                                parameters.extend(body_params)
                                # Set request_body to indicate body construction is needed
                                request_body = {
                                    "type": "expanded",
                                    "required": True,
                                    "fields": [p["name"] for p in body_params],
                                }
                        else:
                            # Regular model reference
                            request_body = {
                                "type": schema_name,
                                "required": operation["requestBody"].get(
                                    "required", True
                                ),
                            }
                    else:
                        # Inline schema
                        body_type = get_python_type(schema, components)
                        request_body = {
                            "type": body_type,
                            "required": operation["requestBody"].get("required", True),
                        }

            # Extract response type
            response_type = "Any"
            responses = operation.get("responses", {})
            success_response = responses.get("200", responses.get("201", {}))
            if "content" in success_response:
                json_content = success_response["content"].get("application/json", {})
                if "schema" in json_content:
                    response_type = get_python_type(json_content["schema"], components)

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


def collect_model_imports(operations: list[dict[str, Any]]) -> set[str]:
    """Collect all model names used in operations for import statements."""
    models = set()

    for op in operations:
        # From response type
        response_type = op["response_type"]
        if "list[" in response_type:
            model = response_type.replace("list[", "").replace("]", "")
            # Skip primitives, Any, and auto-generated Body_ schemas
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

        # From request body
        if op["request_body"]:
            body_type = op["request_body"]["type"]
            # Skip 'expanded' type - those are handled via parameters
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

        # From parameters
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


def generate_client(
    module_name: str, spec_path: Path, output_dir: Path, template_env: Environment
) -> tuple[bool, list[str]]:
    """Generate Python client for a module.

    Returns:
        Tuple of (all_routes_present, missing_routes)
    """
    # Load OpenAPI spec
    spec = load_openapi_spec(spec_path)

    # Extract operations
    operations = extract_operations(spec)

    # Verify all routes were extracted
    all_routes_present, missing_routes = verify_all_routes_generated(spec, operations)

    # Collect model imports
    models = collect_model_imports(operations)

    # Load template
    template = template_env.get_template("python_client.py.j2")

    # Render template
    client_code = template.render(
        module_name=module_name,
        class_name=f"{module_name.capitalize()}Client",
        operations=operations,
        models=sorted(models),
    )

    # Write output
    output_file = output_dir / f"{module_name}_client.py"
    output_file.write_text(client_code)
    print(f"✓ Generated {output_file}")

    return all_routes_present, missing_routes


def generate_init_file(output_dir: Path, modules: list[str]) -> None:
    """Generate __init__.py with exports for all clients."""
    imports = []
    exports = []

    for module_name in sorted(modules):
        class_name = f"{module_name.capitalize()}Client"
        imports.append(f"from .{module_name}_client import {class_name}")
        exports.append(f'    "{class_name}",')

    init_content = f'''"""
Generated Python HTTP clients for inter-module communication.

These clients enable type-safe HTTP communication when modules run as
separate processes/services (multi-process architecture).
"""

{chr(10).join(imports)}

__all__ = [
{chr(10).join(exports)}
]
'''

    output_file = output_dir / "__init__.py"
    output_file.write_text(init_content)
    print(f"✓ Generated {output_file}")


def cleanup_generated_files(output_dir: Path) -> None:
    """Remove all previously generated client files.

    Args:
        output_dir: Directory containing generated clients
    """
    if not output_dir.exists():
        return

    # Remove all *_client.py files
    for client_file in output_dir.glob("*_client.py"):
        client_file.unlink()
        print(f"🗑️  Removed old file: {client_file.name}")

    # Remove __init__.py if it exists
    init_file = output_dir / "__init__.py"
    if init_file.exists():
        init_file.unlink()
        print(f"🗑️  Removed old file: {init_file.name}")


def verify_all_routes_generated(
    spec: dict[str, Any], operations: list[dict[str, Any]]
) -> tuple[bool, list[str]]:
    """Verify that all routes from OpenAPI spec were generated.

    Args:
        spec: OpenAPI specification
        operations: Generated operations list

    Returns:
        Tuple of (all_routes_present, missing_routes)
    """
    spec_operation_ids = set()

    # Extract all operation IDs from spec
    for path, path_item in spec.get("paths", {}).items():
        for method in ["get", "post", "put", "delete", "patch"]:
            if method in path_item:
                operation = path_item[method]
                operation_id = operation.get(
                    "operationId", f"{method}_{path.replace('/', '_')}"
                )
                spec_operation_ids.add(operation_id)

    # Extract all generated operation IDs
    generated_operation_ids = {op["operation_id"] for op in operations}

    # Find missing operations
    missing = sorted(spec_operation_ids - generated_operation_ids)

    return len(missing) == 0, missing


def main() -> None:
    """Main entry point."""
    # Setup paths
    backend_root = Path(__file__).parent.parent
    modules_dir = backend_root / "src" / "trading_api" / "modules"
    output_dir = backend_root / "src" / "trading_api" / "clients"
    template_dir = backend_root / "scripts" / "templates"

    # Validate package names before generation
    print("🔍 Validating backend modules...")
    import subprocess

    validation_result = subprocess.run(
        ["poetry", "run", "python", "scripts/validate_modules.py"],
        cwd=backend_root,
        capture_output=True,
        text=True,
    )

    if validation_result.returncode != 0:
        print("❌ Package name validation failed!")
        print(validation_result.stdout)
        print(validation_result.stderr)
        print()
        print("Fix package naming issues before generating clients.")
        sys.exit(1)

    print("✅ Package name validation passed")
    print()

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Cleanup existing generated files
    print("🧹 Cleaning up existing generated files...")
    cleanup_generated_files(output_dir)
    if output_dir.exists() and list(output_dir.glob("*_client.py")):
        print()  # Empty line after cleanup messages    # Setup Jinja2 environment
    template_env = Environment(
        loader=FileSystemLoader(template_dir), trim_blocks=True, lstrip_blocks=True
    )

    # Discover modules with OpenAPI specs
    all_modules = discover_modules(modules_dir)
    modules_with_specs = []

    for module_name in all_modules:
        spec_path = modules_dir / module_name / "specs" / "openapi.json"
        if spec_path.exists():
            modules_with_specs.append(module_name)

    if not modules_with_specs:
        print("⚠️  No modules with OpenAPI specs found")
        return

    print(f"Generating Python clients for modules: {', '.join(modules_with_specs)}")
    print()

    # Track verification results
    all_success = True
    verification_results = {}

    # Generate client for each module
    for module_name in modules_with_specs:
        spec_path = modules_dir / module_name / "specs" / "openapi.json"
        success, missing_routes = generate_client(
            module_name, spec_path, output_dir, template_env
        )
        verification_results[module_name] = (success, missing_routes)
        if not success:
            all_success = False

    # Generate __init__.py
    print()
    generate_init_file(output_dir, modules_with_specs)

    # Verification summary
    print()
    print("=" * 70)
    print("📋 Route Generation Verification")
    print("=" * 70)

    for module_name, (success, missing_routes) in verification_results.items():
        if success:
            print(f"✅ {module_name}: All routes generated successfully")
        else:
            print(f"❌ {module_name}: {len(missing_routes)} route(s) missing")
            for route in missing_routes:
                print(f"   - {route}")

    print("=" * 70)

    if all_success:
        print()
        print(f"✅ Generated {len(modules_with_specs)} Python clients in {output_dir}")
        print("   All routes verified successfully!")
    else:
        print()
        print(f"❌ Generation completed with errors")
        print(f"   Some routes were not generated. Please review the OpenAPI specs.")
        sys.exit(1)


if __name__ == "__main__":
    main()
