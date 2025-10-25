#!/usr/bin/env python3
"""
WebSocket Router Verification Script

Verifies that all generated WebSocket routers can be imported and instantiated
with their appropriate services.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def verify_router(router_class_name: str, service_type: str) -> tuple[bool, str]:
    """
    Verify a single router can be imported and instantiated.

    Args:
        router_class_name: Name of the router class (e.g., 'BarWsRouter')
        service_type: Either 'datafeed' or 'broker'

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        # Import the router class
        from trading_api.ws import generated
        from trading_api.ws.router_interface import WsRouteService

        router_class = getattr(generated, router_class_name)

        # Import the appropriate service
        service: WsRouteService
        if service_type == "datafeed":
            from trading_api.core.datafeed_service import DatafeedService

            service = DatafeedService()
        elif service_type == "broker":
            from trading_api.core.broker_service import BrokerService

            service = BrokerService()
        else:
            return False, f"Unknown service type: {service_type}"

        # Instantiate the router
        router = router_class(route="test", tags=["test"], service=service)

        # Verify required methods exist
        if not hasattr(router, "topic_builder"):
            return False, "topic_builder method missing"

        return True, f"✓ {router_class_name} verified with {service_type} service"

    except ImportError as e:
        return False, f"✗ Import failed: {e}"
    except Exception as e:
        return False, f"✗ Verification failed: {e}"


def determine_service_type(router_class_name: str) -> str:
    """
    Determine which service type a router requires based on its name.

    Args:
        router_class_name: Name of the router class

    Returns:
        'datafeed' or 'broker'
    """
    # Datafeed routers
    datafeed_routers = {"BarWsRouter", "QuoteWsRouter"}

    # Everything else is broker
    if router_class_name in datafeed_routers:
        return "datafeed"
    return "broker"


def main():
    """Verify all generated routers."""
    print("🧪 Verifying WebSocket Routers\n")

    # Import to get all router classes
    try:
        from trading_api.ws import generated
    except ImportError as e:
        print(f"✗ Failed to import generated routers: {e}")
        sys.exit(1)

    # Get all router class names from __all__
    router_classes = getattr(generated, "__all__", [])

    if not router_classes:
        print("✗ No router classes found in generated package")
        sys.exit(1)

    print(f"Found {len(router_classes)} router(s) to verify:\n")

    # Track results
    results = []
    failed = []

    # Verify each router
    for router_class_name in router_classes:
        service_type = determine_service_type(router_class_name)
        success, message = verify_router(router_class_name, service_type)

        results.append((router_class_name, success, message))

        if success:
            print(f"  {message}")
        else:
            print(f"  {message}")
            failed.append(router_class_name)

    # Print summary
    print(f"\n{'=' * 60}")
    if failed:
        print(f"❌ Verification failed for {len(failed)} router(s):")
        for name in failed:
            print(f"  - {name}")
        print(f"{'=' * 60}")
        sys.exit(1)
    else:
        print(f"✅ All {len(router_classes)} router(s) verified successfully!")
        print(f"{'=' * 60}")
        sys.exit(0)


if __name__ == "__main__":
    main()
