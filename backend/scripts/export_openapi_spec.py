#!/usr/bin/env python3
"""Export OpenAPI specification without running the server.

This script generates the OpenAPI specification directly from the
FastAPI application definition without needing to start the server.
"""

import json
import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
src_dir = backend_dir / "src"
sys.path.insert(0, str(src_dir))

from trading_api.main import apiApp


def main() -> int:
    """Export OpenAPI specification."""
    output_file = backend_dir / "openapi.json"

    if len(sys.argv) > 1:
        output_file = Path(sys.argv[1])

    try:
        openapi_schema = apiApp.openapi()

        with open(output_file, "w") as f:
            json.dump(openapi_schema, f, indent=2)

        print(f"✅ OpenAPI spec exported to: {output_file}")
        return 0
    except Exception as e:
        print(f"❌ Failed to export OpenAPI spec: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
