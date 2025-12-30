"""Root conftest for all backend tests.

This conftest provides the session-scoped event_loop fixture that is shared
across all test directories (tests/, src/trading_api/).

Having a single event_loop fixture at the root level prevents scope conflicts
when running tests from multiple directories together.
"""

import asyncio
from collections.abc import Generator

import pytest


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for session-scoped async tests.

    This is the SINGLE source of event loop for all test suites.
    All async tests and fixtures will use this loop.

    CRITICAL: Must properly shutdown async generators and close the loop
    to prevent "Event loop is closed" errors during fixture teardown.
    """
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop

    # Proper cleanup sequence for pytest-asyncio 0.21.x
    try:
        # Shutdown async generators before closing loop
        loop.run_until_complete(loop.shutdown_asyncgens())
        # Shutdown default executor
        loop.run_until_complete(loop.shutdown_default_executor())
    except AttributeError:
        # shutdown_default_executor added in Python 3.9
        pass
    finally:
        # Close the loop
        loop.close()
