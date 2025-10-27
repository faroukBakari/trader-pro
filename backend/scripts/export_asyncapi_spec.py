#!/usr/bin/env python3
"""Export AsyncAPI specification without running the server.

This script generates the AsyncAPI specification directly from the
FastWS application definition without needing to start the server.
"""

import json
import sys
from pathlib import Path
from typing import Any

backend_dir = Path(__file__).parent.parent
src_dir = backend_dir / "src"
sys.path.insert(0, str(src_dir))

from trading_api.main import wsApp


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


def main() -> int:
    """Export AsyncAPI specification."""
    output_file = backend_dir / "asyncapi.json"

    if len(sys.argv) > 1:
        output_file = Path(sys.argv[1])

    try:
        asyncapi_schema = wsApp.asyncapi()

        # Validate subscription requests before exporting
        validation_errors = validate_subscription_requests(asyncapi_schema)
        if validation_errors:
            print("❌ AsyncAPI validation failed:", file=sys.stderr)
            print("", file=sys.stderr)
            for error in validation_errors:
                print(error, file=sys.stderr)
            print("", file=sys.stderr)
            print("Fix these issues before exporting AsyncAPI spec.", file=sys.stderr)
            return 1

        with open(output_file, "w") as f:
            json.dump(asyncapi_schema, f, indent=2)

        print(f"✅ AsyncAPI spec exported to: {output_file}")
        print(f"✅ All subscription requests validated successfully")
        return 0
    except Exception as e:
        print(f"❌ Failed to export AsyncAPI spec: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
