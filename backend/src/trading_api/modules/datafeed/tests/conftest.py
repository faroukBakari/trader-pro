"""Test fixtures for datafeed module tests.

Inherits all fixtures (apps, app, ws_app, client, async_client) from root conftest.
The full application with all modules is used for datafeed tests.
"""

# This file is intentionally minimal - all fixtures are inherited from:
# - backend/tests/conftest.py (apps fixture with all modules)
# - backend/src/trading_api/conftest.py (app, ws_apps, ws_app, client, async_client)
