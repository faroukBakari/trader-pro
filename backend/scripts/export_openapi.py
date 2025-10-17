#!/usr/bin/env python3
"""Export OpenAPI and AsyncAPI specifications without running the server.

This script generates OpenAPI and AsyncAPI specifications directly from the
FastAPI application definition without needing to start the server.
"""

import json
import sys
from pathlib import Path

# Add src to Python path
backend_dir = Path(__file__).parent.parent
src_dir = backend_dir / "src"
sys.path.insert(0, str(src_dir))

from trading_api.main import apiApp, wsApp


def export_openapi(output_file: Path) -> bool:
    """Export OpenAPI specification to a JSON file."""
    try:
        # Generate OpenAPI schema
        openapi_schema = apiApp.openapi()

        # Write to file
        with open(output_file, "w") as f:
            json.dump(openapi_schema, f, indent=2)

        print(f"✅ OpenAPI spec exported to: {output_file}")
        return True
    except Exception as e:
        print(f"❌ Failed to export OpenAPI spec: {e}", file=sys.stderr)
        return False


def export_asyncapi(output_file: Path) -> bool:
    """Export AsyncAPI specification to a JSON file."""
    try:
        # Generate AsyncAPI schema
        asyncapi_schema = wsApp.asyncapi()

        # Write to file
        with open(output_file, "w") as f:
            json.dump(asyncapi_schema, f, indent=2)

        print(f"✅ AsyncAPI spec exported to: {output_file}")
        return True
    except Exception as e:
        print(f"❌ Failed to export AsyncAPI spec: {e}", file=sys.stderr)
        return False


def main() -> int:
    """Main entry point."""
    # Default output paths
    openapi_file = backend_dir / "openapi.json"
    asyncapi_file = backend_dir / "asyncapi.json"

    # Allow custom paths from command line
    if len(sys.argv) > 1:
        openapi_file = Path(sys.argv[1])
    if len(sys.argv) > 2:
        asyncapi_file = Path(sys.argv[2])

    print("📝 Exporting API specifications (offline mode)...")
    print()

    # Export OpenAPI
    openapi_success = export_openapi(openapi_file)

    # Export AsyncAPI
    asyncapi_success = export_asyncapi(asyncapi_file)

    print()
    if openapi_success and asyncapi_success:
        print("🎉 All specifications exported successfully!")
        return 0
    else:
        print("⚠️  Some specifications failed to export")
        return 1


if __name__ == "__main__":
    sys.exit(main())
