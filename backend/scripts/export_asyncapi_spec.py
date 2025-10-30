#!/usr/bin/env python3
"""Export AsyncAPI specification without running the server.

This script generates the AsyncAPI specification directly from the
FastWS application definition without needing to start the server.

Supports per-module spec generation for modular architecture.
"""

import json
import sys
from pathlib import Path
from typing import Any

backend_dir = Path(__file__).parent.parent
src_dir = backend_dir / "src"
sys.path.insert(0, str(src_dir))

from trading_api.app_factory import create_app
from trading_api.shared.utils import discover_modules_with_websockets


def validate_subscription_requests(asyncapi_schema: dict[str, Any]) -> list[str]:
    """Validate that subscription request models don't have optional parameters.

    Optional parameters in subscription requests cause topic mismatch issues
    between frontend and backend, as the backend may include default values
    in the response topic string that weren't in the original request.

    Returns:
        List of error messages for models with optional parameters.
    """
    errors = []
    schemas = asyncapi_schema.get("components", {}).get("schemas", {})

    for schema_name, schema_def in schemas.items():
        # Check only subscription request models
        if "SubscriptionRequest" in schema_name:
            properties = schema_def.get("properties", {})
            required = set(schema_def.get("required", []))

            # Find optional properties (properties not in required list)
            optional_props = [
                prop for prop in properties.keys() if prop not in required
            ]

            if optional_props:
                errors.append(
                    f"  ❌ {schema_name} has optional parameters: {', '.join(optional_props)}\n"
                    f"     Optional parameters cause topic mismatch between request and response.\n"
                    f"     Make all parameters required or remove them."
                )

    return errors


def export_single_module(module_name: str | None, output_file: Path) -> int:
    """Export AsyncAPI spec for a single module or all modules.

    Args:
        module_name: Name of module to export, or None for all modules
        output_file: Path to output file

    Returns:
        0 on success, 1 on failure
    """
    try:
        # Create app with only the specified module (or all if None)
        enabled_modules = [module_name] if module_name else None
        _, ws_app = create_app(enabled_modules=enabled_modules)

        asyncapi_schema = ws_app.asyncapi()

        # Validate subscription requests before exporting
        validation_errors = validate_subscription_requests(asyncapi_schema)
        if validation_errors:
            module_desc = module_name if module_name else "all modules"
            print(f"❌ AsyncAPI validation failed for {module_desc}:", file=sys.stderr)
            print("", file=sys.stderr)
            for error in validation_errors:
                print(error, file=sys.stderr)
            print("", file=sys.stderr)
            print("Fix these issues before exporting AsyncAPI spec.", file=sys.stderr)
            return 1

        with open(output_file, "w") as f:
            json.dump(asyncapi_schema, f, indent=2)

        module_desc = module_name if module_name else "all modules"
        print(f"✅ AsyncAPI spec exported for {module_desc}: {output_file}")
        print(f"✅ All subscription requests validated successfully")
        return 0
    except Exception as e:
        module_desc = module_name if module_name else "all modules"
        print(
            f"❌ Failed to export AsyncAPI spec for {module_desc}: {e}",
            file=sys.stderr,
        )
        return 1


def main() -> int:
    """Export AsyncAPI specification.

    Usage:
        # Export all modules to default location
        python export_asyncapi_spec.py

        # Export specific module
        python export_asyncapi_spec.py broker

        # Export to custom location
        python export_asyncapi_spec.py custom/path/asyncapi.json

        # Export all modules to specs/ directory (per-module)
        python export_asyncapi_spec.py --per-module
    """
    # Check for per-module flag
    if len(sys.argv) > 1 and sys.argv[1] == "--per-module":
        # Export specs for each module separately to modules/{module}/specs/
        modules_dir = src_dir / "trading_api" / "modules"

        modules = discover_modules_with_websockets()
        if not modules:
            print("⚠️  No modules with WebSocket support found", file=sys.stderr)
            return 1

        print(f"📦 Discovered WebSocket modules: {', '.join(modules)}")

        failed_modules = []
        for module_name in modules:
            module_specs_dir = modules_dir / module_name / "specs"
            module_specs_dir.mkdir(parents=True, exist_ok=True)
            output_file = module_specs_dir / "asyncapi.json"
            result = export_single_module(module_name, output_file)
            if result != 0:
                failed_modules.append(module_name)

        if failed_modules:
            print(
                f"❌ Failed to export specs for: {', '.join(failed_modules)}",
                file=sys.stderr,
            )
            return 1

        print(f"✅ Successfully exported {len(modules)} WebSocket module specs")
        return 0

    # Legacy behavior: single spec export
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        # Check if it's a module name or a file path
        if "/" in arg or arg.endswith(".json"):
            # It's a file path
            output_file = Path(arg)
            return export_single_module(None, output_file)
        else:
            # It's a module name
            module_name = arg
            output_file = backend_dir / f"asyncapi-{module_name}.json"
            return export_single_module(module_name, output_file)
    else:
        # Default: export all modules to asyncapi.json
        output_file = backend_dir / "asyncapi.json"
        return export_single_module(None, output_file)


if __name__ == "__main__":
    sys.exit(main())
