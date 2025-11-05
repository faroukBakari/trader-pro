"""
Integration tests for Python HTTP clients in multi-process architecture.

Tests inter-module communication when broker and datafeed run as separate services.

This test automatically generates Python clients before running tests.
"""

import asyncio
import multiprocessing
import socket
import sys
from collections.abc import Generator
from pathlib import Path

import httpx
import psutil
import pytest
import uvicorn

from trading_api.shared.module_interface import Module


def _find_free_port() -> int:
    """Find a free port by binding to port 0 and letting OS assign one.

    Returns:
        int: An available port number
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        port: int = s.getsockname()[1]
    return port


def _ensure_clients_generated() -> None:
    """Ensure Python HTTP clients are freshly generated before tests run.

    Uses the module's gen_specs_and_clients() method to generate specs and
    clients without needing external processes or starting the full backend.
    """
    # Add backend to path for imports
    backend_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(backend_root / "src"))

    from trading_api.shared.utils import discover_modules

    print("\n📝 Generating specs and clients for all modules...")

    # Discover and instantiate modules
    modules_dir = backend_root / "src" / "trading_api" / "modules"
    module_names = discover_modules(modules_dir)
    generated_count = 0

    for module_name in module_names:
        try:
            # Import the module class from __init__.py
            module_package = f"trading_api.modules.{module_name}"
            module_module = __import__(module_package, fromlist=["*"])
            module_class: type[Module] = getattr(
                module_module, f"{module_name.capitalize()}Module"
            )

            # Instantiate the module
            module_instance = module_class()

            # Create app first (required for gen_specs_and_clients)
            print(f"\n  Generating for {module_name}...")
            api_app, ws_app = module_instance.create_apps()

            # Generate specs and clients using the created app
            module_instance.gen_specs_and_clients(
                api_app=api_app, ws_app=ws_app, clean_first=True
            )
            generated_count += 1
            print(f"  ✅ Generated specs and client for {module_name}")

        except Exception as e:
            print(f"  ⚠️  Failed to generate for {module_name}: {e}")
            import traceback

            traceback.print_exc()

    if generated_count == 0:
        raise RuntimeError("Failed to generate specs and clients for any module")

    print(
        f"\n✅ Successfully generated specs and clients for {generated_count} module(s)"
    )


# Generate clients before any tests run
_ensure_clients_generated()

# Now import the clients (they should exist after generation)
from trading_api.modules.broker.client_generated import BrokerClient  # noqa: E402
from trading_api.modules.datafeed.client_generated import DatafeedClient  # noqa: E402


def run_service(module_name: str, port: int) -> None:
    """Run a single module as a separate service.

    Args:
        module_name: Name of the module to run (broker or datafeed)
        port: Port to bind the service to
    """
    import os

    # Set environment variable to enable only this module
    os.environ["ENABLED_MODULES"] = module_name

    # Run uvicorn server
    uvicorn.run(
        "trading_api.main:app",
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False,
    )


def _cleanup_process(process: multiprocessing.Process, timeout: int = 5) -> None:
    """Safely cleanup a multiprocessing.Process and its entire process tree.

    Handles daemon processes, detached processes, and child processes spawned
    by the main process (e.g., uvicorn workers).

    Args:
        process: The process to cleanup
        timeout: Timeout in seconds for graceful termination
    """
    if not process.is_alive():
        return

    try:
        # Get the psutil Process object for the multiprocessing.Process
        parent = psutil.Process(process.pid)

        # Get all child processes (including detached/daemon children)
        children = parent.children(recursive=True)

        # Terminate parent process gracefully
        process.terminate()

        # Also terminate all children
        for child in children:
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass

        # Wait for graceful shutdown with timeout
        try:
            process.join(timeout=timeout)
        except Exception:
            pass

        # Force kill if still alive
        if process.is_alive():
            # Kill parent
            try:
                parent.kill()
            except psutil.NoSuchProcess:
                pass

            # Kill all children that are still alive
            for child in children:
                try:
                    if child.is_running():
                        child.kill()
                except psutil.NoSuchProcess:
                    pass

            # Final join attempt
            try:
                process.join(timeout=1)
            except Exception:
                # Process may not join properly, which is acceptable
                # as it has been forcefully terminated
                pass

    except psutil.NoSuchProcess:
        # Process already terminated
        pass
    except Exception as e:
        # Log but don't fail on cleanup errors
        print(f"Warning: Error during process cleanup: {e}")
        # Attempt basic cleanup as fallback
        try:
            if process.is_alive():
                process.kill()
        except Exception:
            pass


async def wait_for_service(
    base_url: str, module_name: str, max_attempts: int = 30
) -> bool:
    """Wait for a service to become available.

    Args:
        base_url: Base URL of the service
        module_name: Name of the module (broker, datafeed, etc.)
        max_attempts: Maximum number of connection attempts

    Returns:
        True if service is available, False otherwise
    """
    async with httpx.AsyncClient() as client:
        for _ in range(max_attempts):
            try:
                # Health endpoint is at server level, not module level
                response = await client.get(f"{base_url}/api/v1/core/health")
                if response.status_code == 200:
                    return True
            except (httpx.ConnectError, httpx.RemoteProtocolError):
                await asyncio.sleep(0.5)
    return False


@pytest.fixture
def broker_service(
    request: pytest.FixtureRequest,
) -> Generator[tuple[str, int], None, None]:
    """Start a broker service on a free port and ensure cleanup.

    Yields:
        tuple: (base_url, port) of the running broker service
    """
    port = _find_free_port()
    process = multiprocessing.Process(target=run_service, args=("broker", port))
    process.start()

    # Register cleanup using request.addfinalizer
    request.addfinalizer(lambda: _cleanup_process(process))

    yield f"http://127.0.0.1:{port}", port


@pytest.fixture
def datafeed_service(
    request: pytest.FixtureRequest,
) -> Generator[tuple[str, int], None, None]:
    """Start a datafeed service on a free port and ensure cleanup.

    Yields:
        tuple: (base_url, port) of the running datafeed service
    """
    port = _find_free_port()
    process = multiprocessing.Process(target=run_service, args=("datafeed", port))
    process.start()

    # Register cleanup using request.addfinalizer
    request.addfinalizer(lambda: _cleanup_process(process))

    yield f"http://127.0.0.1:{port}", port


@pytest.mark.integration
@pytest.mark.asyncio
async def test_broker_client_http_communication(
    broker_service: tuple[str, int],
) -> None:
    """Test BrokerClient can communicate with separate broker service via HTTP."""
    broker_url, broker_port = broker_service

    # Wait for service to start
    service_ready = await wait_for_service(broker_url, "broker")
    assert service_ready, f"Broker service failed to start on port {broker_port}"

    # Test HTTP client communication
    # Client expects paths without /api/v1/broker prefix, so we add it to base_url
    async with BrokerClient(base_url=f"{broker_url}/api/v1/broker") as client:
        # Test getting orders
        orders = await client.getOrders()
        assert isinstance(orders, list)

        # Test getting positions
        positions = await client.getPositions()
        assert isinstance(positions, list)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_datafeed_client_http_communication(
    datafeed_service: tuple[str, int],
) -> None:
    """Test DatafeedClient can communicate with separate datafeed service via HTTP."""
    datafeed_url, datafeed_port = datafeed_service

    # Wait for service to start
    service_ready = await wait_for_service(datafeed_url, "datafeed")
    assert service_ready, f"Datafeed service failed to start on port {datafeed_port}"

    # Test HTTP client communication
    # Client expects paths without /api/v1/datafeed prefix, so we add it to base_url
    async with DatafeedClient(base_url=f"{datafeed_url}/api/v1/datafeed") as client:
        # Test getting config
        config = await client.getConfig()
        assert config.supported_resolutions is not None

        # Test searching symbols
        results = await client.searchSymbols(user_input="AAPL")
        assert isinstance(results, list)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_broker_calls_datafeed_multi_process(
    broker_service: tuple[str, int],
    datafeed_service: tuple[str, int],
) -> None:
    """Test broker service can call datafeed service in multi-process setup.

    Simulates the real-world scenario where:
    - Broker service runs on a dynamically assigned port
    - Datafeed service runs on a dynamically assigned port
    - Broker uses DatafeedClient to fetch symbols from datafeed
    """
    broker_url, broker_port = broker_service
    datafeed_url, datafeed_port = datafeed_service

    # Wait for both services to start
    broker_ready = await wait_for_service(broker_url, "broker")
    datafeed_ready = await wait_for_service(datafeed_url, "datafeed")

    assert broker_ready, f"Broker service failed to start on port {broker_port}"
    assert datafeed_ready, f"Datafeed service failed to start on port {datafeed_port}"

    # Simulate broker calling datafeed
    # Client expects paths without /api/v1/datafeed prefix, so we add it to base_url
    async with DatafeedClient(
        base_url=f"{datafeed_url}/api/v1/datafeed"
    ) as datafeed_client:
        # Broker would use this to fetch symbols for order validation
        symbols = await datafeed_client.searchSymbols(user_input="AAPL")
        assert len(symbols) > 0
        assert symbols[0].symbol == "AAPL"

        # Broker would use this to resolve symbol details
        symbol_detail = await datafeed_client.resolveSymbol(symbol="AAPL")
        assert symbol_detail.name == "AAPL"
        assert symbol_detail.ticker == "AAPL"

    # Verify broker service is also running independently
    # Client expects paths without /api/v1/broker prefix, so we add it to base_url
    async with BrokerClient(base_url=f"{broker_url}/api/v1/broker") as broker_client:
        orders = await broker_client.getOrders()
        assert isinstance(orders, list)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_client_context_manager(
    datafeed_service: tuple[str, int],
) -> None:
    """Test clients work correctly with async context manager."""
    datafeed_url, datafeed_port = datafeed_service

    # Wait for service to start
    service_ready = await wait_for_service(datafeed_url, "datafeed")
    assert service_ready, f"Datafeed service failed to start on port {datafeed_port}"

    # Test context manager properly closes client
    # Client expects paths without /api/v1/datafeed prefix, so we add it to base_url
    async with DatafeedClient(base_url=f"{datafeed_url}/api/v1/datafeed") as client:
        # Test module-specific endpoint
        config = await client.getConfig()
        assert config.supported_resolutions is not None
        assert client._client is not None

    # Client should be closed after context
    # (we can't easily verify this without accessing private state)
