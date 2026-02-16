#!/usr/bin/env python3
"""Generate specs and clients for a specific module.

This script is used by the Makefile 'generate' target to generate
OpenAPI/AsyncAPI specs and Python clients for a module.
"""
import asyncio
import sys
from pathlib import Path

# Add src to path for module imports
sys.path.insert(0, str(Path.cwd() / "src"))


async def main_async() -> None:
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
        # Import dependencies
        from trading_api.datastores import create_memory_datastore
        from trading_api.shared.module_interface import ModuleApp
        from trading_api.shared.provider_registry import ProviderRegistry

        # Import module class
        module_pkg = __import__(module_path, fromlist=[module_class_name])
        module_class = getattr(module_pkg, module_class_name)

        # Initialize provider registry and auto-discover providers
        provider_registry = ProviderRegistry()
        provider_registry.auto_discover()

        # Get service class to determine required capabilities (static analysis)
        service_class = module_class._service_class()
        required_capabilities = service_class.capabilities()

        # Get providers for those capabilities
        providers = await provider_registry.get_providers(required_capabilities)

        # Create shared datastore for modules that need it
        datastore = create_memory_datastore()

        # NOTE: WS routers are automatically generated during module instantiation!
        # When module_class() is called, the module's __init__ creates WsRouters,
        # which triggers generate_module_routers() to generate concrete router classes
        # from TypeAlias declarations in the module's ws.py file.
        module = module_class(providers=providers, datastores=[datastore])

        # Create apps using ModuleApp wrapper
        module_app = ModuleApp(module)

        # Generate specs and clients
        if output_dir:
            print(f"📁 Using custom output directory: {output_dir}")
            module_app.gen_specs_and_clients(clean_first=False, output_dir=output_dir)
        else:
            module_app.gen_specs_and_clients(clean_first=False)

        print(f"✅ Successfully generated for {module_name}")

    except Exception as e:
        print(f"❌ Failed for {module_name}: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


def main() -> None:
    """Entry point that runs async main."""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
