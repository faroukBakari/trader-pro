"""Main FastAPI application entry point.

Uses the application factory pattern to create a modular, configurable application.
Supports selective module loading via the ENABLED_MODULES environment variable.
"""

import os

from trading_api.app_factory import AppFactory

# Parse ENABLED_MODULES environment variable
# Examples:
#   ENABLED_MODULES=all (default) - loads all modules
#   ENABLED_MODULES=datafeed - loads only datafeed module
#   ENABLED_MODULES=broker - loads only broker module
#   ENABLED_MODULES=datafeed,broker - loads specific modules
enabled_modules_str = os.getenv("ENABLED_MODULES", "all")

enabled_modules: list[str] | None
if enabled_modules_str != "all":
    enabled_modules = [m.strip() for m in enabled_modules_str.split(",")]
else:
    enabled_modules = None  # None = all modules

# Create application using factory
factory = AppFactory()
app = factory.create_app(enabled_module_names=enabled_modules)
