"""Root conftest for all backend tests.

This conftest configures pytest-asyncio for session-scoped event loops.
pytest-asyncio 1.1+ uses asyncio.Runner internally which properly:
- Cancels pending tasks before loop close
- Shuts down async generators
- Shuts down the default executor

Configuration is in pyproject.toml:
  asyncio_default_fixture_loop_scope = "session"
"""

# No custom event_loop fixture needed - pytest-asyncio 1.1+ handles cleanup properly
