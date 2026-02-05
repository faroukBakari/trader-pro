"""Main FastAPI application entry point.

Uses the application factory pattern to create a modular, configurable application.
Supports selective module loading via the ENABLED_MODULES environment variable.
Supports selective provider loading via the ENABLED_PROVIDERS environment variable.

The app is created at module import time. Since AppFactory.create_app() is async
(for provider lifecycle hooks), we need to run it in an event loop. When uvicorn
imports this module, it may already have an event loop running, so we handle both
cases: running loop (use existing) and no loop (create temporary one).
"""

import asyncio
import os

from trading_api.app_factory import AppFactory

# Parse ENABLED_MODULES environment variable
enabled_modules_str = os.getenv("ENABLED_MODULES", "all")

enabled_modules: list[str]
if enabled_modules_str != "all":
    enabled_modules = [m.strip() for m in enabled_modules_str.split(",")]
else:
    enabled_modules = []  # Empty list = all modules
# Parse ENABLED_PROVIDERS environment variable
enabled_providers_str = os.getenv("ENABLED_PROVIDERS", "all")

enabled_providers: list[str]
if enabled_providers_str != "all":
    enabled_providers = [p.strip() for p in enabled_providers_str.split(",")]
else:
    enabled_providers = []  # Empty list = all providers

# Create application using async factory
factory = AppFactory()

# Handle both cases: running event loop (uvicorn) and no loop (direct import)
try:
    # Try to get existing event loop
    loop = asyncio.get_event_loop()
    if loop.is_running():
        # We're being imported by uvicorn which has a running loop
        # We need to create the app in a way that doesn't block the current loop
        # Use a new thread with its own event loop
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(
                lambda: asyncio.run(
                    factory.create_app(
                        enabled_module_names=enabled_modules,
                        enabled_provider_names=enabled_providers,
                    )
                )
            )
            app = future.result()
    else:
        # No running loop - use the existing loop
        app = loop.run_until_complete(
            factory.create_app(
                enabled_module_names=enabled_modules,
                enabled_provider_names=enabled_providers,
            )
        )
except RuntimeError:
    # No event loop exists - create one
    app = asyncio.run(
        factory.create_app(
            enabled_module_names=enabled_modules,
            enabled_provider_names=enabled_providers,
        )
    )
