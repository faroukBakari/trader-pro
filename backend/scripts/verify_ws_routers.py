#!/usr/bin/env python3
"""
WebSocket Router Verification Script

Verifies that all generated WebSocket routers can be imported and instantiated
with their appropriate services.

Supports both legacy (ws/generated/) and modular (modules/*/ws_generated/) architectures.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def verify_legacy_router(router_class_name: str, service_type: str) -> tuple[bool, str]:
    """
    Verify a single router from legacy architecture.

    Args:
        router_class_name: Name of the router class (e.g., 'BarWsRouter')
        service_type: Either 'datafeed' or 'broker'

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        # Import the router class directly from generated package
        import trading_api.ws.generated as generated_module
        from trading_api.shared.ws.router_interface import WsRouteService

        router_class = getattr(generated_module, router_class_name)

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

        return True, f"✓ {router_class_name} verified (legacy)"

    except ImportError as e:
        return False, f"✗ Import failed: {e}"
    except Exception as e:
        return False, f"✗ Verification failed: {e}"


def verify_modular_router(module_name: str, router_class_name: str) -> tuple[bool, str]:
    """
    Verify a single router from modular architecture.

    Args:
        module_name: Name of the module (e.g., 'datafeed', 'broker')
        router_class_name: Name of the router class (e.g., 'BarWsRouter')

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        # Dynamically import module's generated package
        module_path = f"trading_api.modules.{module_name}.ws_generated"
        generated_module = __import__(module_path, fromlist=[router_class_name])

        # Import router class
        router_class = getattr(generated_module, router_class_name)

        # Import the module class for service
        module_class_path = f"trading_api.modules.{module_name}"
        module_pkg = __import__(
            module_class_path, fromlist=[f"{module_name.capitalize()}Module"]
        )
        module_class = getattr(module_pkg, f"{module_name.capitalize()}Module")

        # Get service from module
        module_instance = module_class()
        service = module_instance.service

        # Instantiate the router
        router = router_class(route="test", tags=["test"], service=service)

        # Verify required methods exist
        if not hasattr(router, "topic_builder"):
            return False, "topic_builder method missing"

        return True, f"✓ {router_class_name} verified (module: {module_name})"

    except ImportError as e:
        return False, f"✗ Import failed: {e}"
    except Exception as e:
        return False, f"✗ Verification failed: {e}"


def determine_legacy_service_type(router_class_name: str) -> str:
    """
    Determine which service type a router requires based on its name (legacy).

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


def find_modular_routers(base_dir: Path) -> list[tuple[str, str]]:
    """
    Find all routers in modular architecture.

    Returns:
        List of (module_name, router_class_name) tuples
    """
    modules_dir = base_dir / "src/trading_api/modules"
    if not modules_dir.exists():
        return []

    routers = []
    for module_dir in modules_dir.iterdir():
        if not module_dir.is_dir():
            continue

        ws_generated_dir = module_dir / "ws_generated"
        if not ws_generated_dir.exists():
            continue

        init_file = ws_generated_dir / "__init__.py"
        if not init_file.exists():
            continue

        # Parse __all__ from __init__.py
        try:
            content = init_file.read_text()
            # Extract router class names from __all__
            import re

            all_match = re.search(r"__all__\s*=\s*\[(.*?)\]", content, re.DOTALL)
            if all_match:
                # Extract quoted strings
                router_names = re.findall(r'"([^"]+)"', all_match.group(1))
                for router_name in router_names:
                    routers.append((module_dir.name, router_name))
        except Exception as e:
            print(f"Warning: Failed to parse {init_file}: {e}")

    return routers


def main():
    """Verify all generated routers."""
    print("🧪 Verifying WebSocket Routers\n")

    base_dir = Path.cwd()
    results = []
    failed = []

    # Check for modular architecture
    modular_routers = find_modular_routers(base_dir)

    if modular_routers:
        print(f"🏗️  Detected modular architecture")
        print(f"Found {len(modular_routers)} router(s) across modules:\n")

        for module_name, router_class_name in modular_routers:
            success, message = verify_modular_router(module_name, router_class_name)
            results.append((router_class_name, success, message))

            print(f"  {message}")
            if not success:
                failed.append(f"{module_name}/{router_class_name}")

    else:
        # Fall back to legacy architecture
        print(f"🏗️  Detected legacy architecture")

        try:
            import trading_api.ws.generated as generated
            from trading_api.ws.generated import __all__ as router_classes
        except ImportError as e:
            print(f"✗ Failed to import generated routers: {e}")
            sys.exit(1)

        # Get all router class names from __all__
        router_classes = getattr(generated, "__all__", [])

        if not router_classes:
            print("✗ No router classes found in generated package")
            sys.exit(1)

        print(f"Found {len(router_classes)} router(s) to verify:\n")

        # Verify each router
        for router_class_name in router_classes:
            service_type = determine_legacy_service_type(router_class_name)
            success, message = verify_legacy_router(router_class_name, service_type)

            results.append((router_class_name, success, message))

            print(f"  {message}")
            if not success:
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
        total_routers = len(results)
        print(f"✅ All {total_routers} router(s) verified successfully!")
        print(f"{'=' * 60}")
        sys.exit(0)


if __name__ == "__main__":
    main()
