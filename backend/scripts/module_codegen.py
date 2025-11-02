#!/usr/bin/env python3
"""Generate specs and clients for a specific module.

This script is used by the Makefile 'generate' target to generate
OpenAPI/AsyncAPI specs and Python clients for a module.
"""
import sys
from pathlib import Path

# Add src to path for module imports
sys.path.insert(0, str(Path.cwd() / "src"))


def main() -> None:
    """Generate specs and clients for the specified module."""
    if len(sys.argv) < 2:
        print("Usage: module_codegen.py <module_name> [output_dir]", file=sys.stderr)
        sys.exit(1)

    module_name = sys.argv[1]
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else None

    # Build module class name (e.g., 'broker' -> 'BrokerModule')
    module_class_name = (
        "".join(word.capitalize() for word in module_name.split("_")) + "Module"
    )
    module_path = f"trading_api.modules.{module_name}"

    try:
        # Import and instantiate module
        module_pkg = __import__(module_path, fromlist=[module_class_name])
        module_class = getattr(module_pkg, module_class_name)
        module = module_class()

        # Create apps
        api_app, ws_app = module.create_app(base_path="/api/v1")

        # Build kwargs
        kwargs = {
            "api_app": api_app,
            "ws_app": ws_app,
            "clean_first": False,
        }

        if output_dir:
            kwargs["output_dir"] = output_dir
            print(f"📁 Using custom output directory: {output_dir}")

        # Generate specs and clients
        module.gen_specs_and_clients(**kwargs)

        print(f"✅ Successfully generated for {module_name}")

    except Exception as e:
        print(f"❌ Failed for {module_name}: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
