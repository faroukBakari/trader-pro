"""
Integration tests for Python HTTP clients in multi-process architecture.

Tests inter-module communication when broker and datafeed run as separate services.

This test automatically generates Python clients before running tests.
"""

import asyncio
import multiprocessing
import sys
from pathlib import Path

import httpx
import pytest
import uvicorn

from trading_api.shared.module_interface import Module


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
            api_app, ws_app = module_instance.create_app(base_path="/api/v1")

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
from trading_api.clients import BrokerClient, DatafeedClient  # noqa: E402


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
                response = await client.get(f"{base_url}/api/v1/health")
                if response.status_code == 200:
                    return True
            except (httpx.ConnectError, httpx.RemoteProtocolError):
                await asyncio.sleep(0.5)
    return False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_broker_client_http_communication() -> None:
    """Test BrokerClient can communicate with separate broker service via HTTP."""
    # Start broker service in separate process
    broker_port = 8001
    broker_process = multiprocessing.Process(
        target=run_service, args=("broker", broker_port)
    )
    broker_process.start()

    try:
        # Wait for service to start
        broker_url = f"http://127.0.0.1:{broker_port}"
        service_ready = await wait_for_service(broker_url, "broker")
        assert service_ready, "Broker service failed to start"

        # Test HTTP client communication
        async with BrokerClient(base_url=broker_url) as client:
            # Test getting orders
            orders = await client.getOrders()
            assert isinstance(orders, list)

            # Test getting positions
            positions = await client.getPositions()
            assert isinstance(positions, list)

    finally:
        # Cleanup: terminate broker service
        broker_process.terminate()
        broker_process.join(timeout=5)
        if broker_process.is_alive():
            broker_process.kill()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_datafeed_client_http_communication() -> None:
    """Test DatafeedClient can communicate with separate datafeed service via HTTP."""
    # Start datafeed service in separate process
    datafeed_port = 8002
    datafeed_process = multiprocessing.Process(
        target=run_service, args=("datafeed", datafeed_port)
    )
    datafeed_process.start()

    try:
        # Wait for service to start
        datafeed_url = f"http://127.0.0.1:{datafeed_port}"
        service_ready = await wait_for_service(datafeed_url, "datafeed")
        assert service_ready, "Datafeed service failed to start"

        # Test HTTP client communication
        async with DatafeedClient(base_url=datafeed_url) as client:
            # Test getting config
            config = await client.getConfig()
            assert config.supported_resolutions is not None

            # Test searching symbols
            results = await client.searchSymbols(user_input="AAPL")
            assert isinstance(results, list)

    finally:
        # Cleanup: terminate datafeed service
        datafeed_process.terminate()
        datafeed_process.join(timeout=5)
        if datafeed_process.is_alive():
            datafeed_process.kill()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_broker_calls_datafeed_multi_process() -> None:
    """Test broker service can call datafeed service in multi-process setup.

    Simulates the real-world scenario where:
    - Broker service runs on port 8001
    - Datafeed service runs on port 8002
    - Broker uses DatafeedClient to fetch symbols from datafeed
    """
    broker_port = 8001
    datafeed_port = 8002

    # Start both services
    broker_process = multiprocessing.Process(
        target=run_service, args=("broker", broker_port)
    )
    datafeed_process = multiprocessing.Process(
        target=run_service, args=("datafeed", datafeed_port)
    )

    broker_process.start()
    datafeed_process.start()

    try:
        # Wait for both services to start
        broker_url = f"http://127.0.0.1:{broker_port}"
        datafeed_url = f"http://127.0.0.1:{datafeed_port}"

        broker_ready = await wait_for_service(broker_url, "broker")
        datafeed_ready = await wait_for_service(datafeed_url, "datafeed")

        assert broker_ready, "Broker service failed to start"
        assert datafeed_ready, "Datafeed service failed to start"

        # Simulate broker calling datafeed
        async with DatafeedClient(base_url=datafeed_url) as datafeed_client:
            # Broker would use this to fetch symbols for order validation
            symbols = await datafeed_client.searchSymbols(user_input="AAPL")
            assert len(symbols) > 0
            assert symbols[0].symbol == "AAPL"

            # Broker would use this to resolve symbol details
            symbol_detail = await datafeed_client.resolveSymbol(symbol="AAPL")
            assert symbol_detail.name == "AAPL"
            assert symbol_detail.ticker == "AAPL"

        # Verify broker service is also running independently
        async with BrokerClient(base_url=broker_url) as broker_client:
            orders = await broker_client.getOrders()
            assert isinstance(orders, list)

    finally:
        # Cleanup: terminate both services
        broker_process.terminate()
        datafeed_process.terminate()

        broker_process.join(timeout=5)
        datafeed_process.join(timeout=5)

        if broker_process.is_alive():
            broker_process.kill()
        if datafeed_process.is_alive():
            datafeed_process.kill()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_client_context_manager() -> None:
    """Test clients work correctly with async context manager."""
    datafeed_port = 8003
    datafeed_process = multiprocessing.Process(
        target=run_service, args=("datafeed", datafeed_port)
    )
    datafeed_process.start()

    try:
        datafeed_url = f"http://127.0.0.1:{datafeed_port}"
        service_ready = await wait_for_service(datafeed_url, "datafeed")
        assert service_ready

        # Test context manager properly closes client
        async with DatafeedClient(base_url=datafeed_url) as client:
            # Test module-specific endpoint
            config = await client.getConfig()
            assert config.supported_resolutions is not None
            assert client._client is not None

        # Client should be closed after context
        # (we can't easily verify this without accessing private state)

    finally:
        datafeed_process.terminate()
        datafeed_process.join(timeout=5)
        if datafeed_process.is_alive():
            datafeed_process.kill()
            datafeed_process.kill()
