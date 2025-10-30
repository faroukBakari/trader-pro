#!/usr/bin/env python3
"""Export OpenAPI specification without running the server.

This script generates the OpenAPI specification directly from the
FastAPI application definition without needing to start the server.

Supports per-module spec generation for modular architecture.
"""

import json
import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
src_dir = backend_dir / "src"
sys.path.insert(0, str(src_dir))

from trading_api.app_factory import create_app
from trading_api.shared.utils import discover_modules


def export_single_module(module_name: str | None, output_file: Path) -> int:
    """Export OpenAPI spec for a single module or all modules.

    Args:
        module_name: Name of module to export, or None for all modules
        output_file: Path to output file

    Returns:
        0 on success, 1 on failure
    """
    try:
        # Create app with only the specified module (or all if None)
        enabled_modules = [module_name] if module_name else None
        api_app, _ = create_app(enabled_modules=enabled_modules)

        openapi_schema = api_app.openapi()

        with open(output_file, "w") as f:
            json.dump(openapi_schema, f, indent=2)

        module_desc = module_name if module_name else "all modules"
        print(f"✅ OpenAPI spec exported for {module_desc}: {output_file}")
        return 0
    except Exception as e:
        module_desc = module_name if module_name else "all modules"
        print(
            f"❌ Failed to export OpenAPI spec for {module_desc}: {e}",
            file=sys.stderr,
        )
        return 1


def main() -> int:
    """Export OpenAPI specification.

    Usage:
        # Export all modules to default location
        python export_openapi_spec.py

        # Export specific module
        python export_openapi_spec.py broker

        # Export to custom location
        python export_openapi_spec.py custom/path/openapi.json

        # Export all modules to specs/ directory (per-module)
        python export_openapi_spec.py --per-module
    """
    # Check for per-module flag
    if len(sys.argv) > 1 and sys.argv[1] == "--per-module":
        # Export specs for each module separately to modules/{module}/specs/
        modules_dir = src_dir / "trading_api" / "modules"

        modules = discover_modules()
        if not modules:
            print("⚠️  No modules found to export", file=sys.stderr)
            return 1

        print(f"📦 Discovered modules: {', '.join(modules)}")

        failed_modules = []
        for module_name in modules:
            module_specs_dir = modules_dir / module_name / "specs"
            module_specs_dir.mkdir(parents=True, exist_ok=True)
            output_file = module_specs_dir / "openapi.json"
            result = export_single_module(module_name, output_file)
            if result != 0:
                failed_modules.append(module_name)

        if failed_modules:
            print(
                f"❌ Failed to export specs for: {', '.join(failed_modules)}",
                file=sys.stderr,
            )
            return 1

        print(f"✅ Successfully exported {len(modules)} module specs")
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
            output_file = backend_dir / f"openapi-{module_name}.json"
            return export_single_module(module_name, output_file)
    else:
        # Default: export all modules to openapi.json
        output_file = backend_dir / "openapi.json"
        return export_single_module(None, output_file)


if __name__ == "__main__":
    sys.exit(main())
