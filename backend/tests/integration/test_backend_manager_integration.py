"""Integration tests for backend_manager.py with real processes.

These tests start actual backend processes to verify multi-process behavior,
nginx routing, and end-to-end functionality. They are SLOWER but provide
comprehensive coverage of real-world scenarios.

Test Flow (two-class design for isolation):
1. ReadOnly tests: Session-scoped backend, fast, never stop servers
2. Lifecycle tests: Function-scoped fixtures, full isolation, test stop/restart

Test Categories:
- ReadOnly: Health checks, routing, module isolation, WebSocket probing
- Lifecycle: Start/stop/restart workflows, error handling, status checks
"""

import asyncio
import atexit
import hashlib
import os
import signal
import socket
import time
from collections.abc import AsyncGenerator
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from jose import jwt
from pytest import TempPathFactory

from scripts.backend_manager import ServerManager, generate_nginx_config, is_port_in_use
from trading_api.shared.config import Settings
from trading_api.shared.deployment import (
    DeploymentConfig,
    NginxConfig,
    ServerConfig,
    WebSocketConfig,
)

# Track all managers for emergency cleanup
_active_managers: list[ServerManager] = []


def _emergency_cleanup() -> None:
    """Emergency cleanup handler - kills any leftover processes on exit.

    Registered with atexit to handle cases where tests are killed (Ctrl+C, timeout)
    or fixtures don't clean up properly.
    """
    for manager in _active_managers:
        try:
            # Force kill all processes using ports
            all_ports = [port for _, port in manager.config.get_all_ports()]
            for port in all_ports:
                if is_port_in_use(port):
                    # Use fuser to kill process holding port (Linux)
                    os.system(f"fuser -k {port}/tcp 2>/dev/null")

            # Also kill by PID files if they exist
            if hasattr(manager, "nginx_pid_file") and manager.nginx_pid_file.exists():
                try:
                    pid = int(manager.nginx_pid_file.read_text().strip())
                    os.kill(pid, signal.SIGKILL)
                except (ValueError, OSError, ProcessLookupError):
                    pass

            for name in manager.processes:
                pid_file = manager.pid_dir / f"{name}.pid"
                if pid_file.exists():
                    try:
                        pid = int(pid_file.read_text().strip())
                        os.kill(pid, signal.SIGKILL)
                    except (ValueError, OSError, ProcessLookupError):
                        pass
        except Exception as e:
            print(f"Error in emergency cleanup: {e}")

    _active_managers.clear()


# Register emergency cleanup
atexit.register(_emergency_cleanup)


def get_unique_port_base(seed: str) -> int:
    """Generate a unique port base from a seed string.

    Uses hash to distribute ports across available range (10000-60000).
    Each test session/fixture gets 10 consecutive ports.

    Args:
        seed: Unique string (e.g., tmp_path, test name)

    Returns:
        Base port number (use base, base+1, base+2, etc.)
    """
    # Hash seed to get deterministic but distributed port
    hash_bytes = hashlib.sha256(seed.encode()).digest()
    hash_int = int.from_bytes(hash_bytes[:4], byteorder="big")
    # Range: 10000-59990 (leaves room for 10 ports per test)
    return 10000 + (hash_int % 5000) * 10


# ============================================================================
# Fixtures and Helpers
# ============================================================================


@pytest.fixture(scope="session")
def valid_jwt_token() -> str:
    """Generate a valid JWT token for testing (session-scoped)."""
    settings = Settings()
    payload = {
        "user_id": "TEST-USER-001",
        "email": "test@example.com",
        "full_name": "Test User",
        "picture": "https://example.com/avatar.jpg",
        "exp": int(time.time()) + 300,
        "iat": int(time.time()),
    }
    return jwt.encode(
        payload, settings.jwt_private_key, algorithm=settings.JWT_ALGORITHM
    )


@pytest.fixture(scope="session")
def auth_cookies(valid_jwt_token: str) -> dict[str, str]:
    """Generate authentication cookies for testing (session-scoped)."""
    return {"access_token": valid_jwt_token}


async def ensure_started(manager: ServerManager) -> None:
    """Ensure backend is fully started and healthy.

    Checks status and restarts if needed. Makes tests autonomous.

    Args:
        manager: ServerManager instance to check/start
    """
    status = await manager.get_status()

    # If fully running and healthy, nothing to do
    if status["running"] and status["nginx"]["healthy"]:
        all_healthy = True
        for server_name in manager.config.servers.keys():
            instances = status["servers"].get(server_name, [])
            # Updated to use new status format with overall_healthy
            if not instances or not all(inst["overall_healthy"] for inst in instances):
                all_healthy = False
                break

        if all_healthy:
            return  # All good, backend is ready

    # Need to restart - clean up first
    await manager.stop_all(timeout=0.5)
    await asyncio.sleep(0.5)  # Wait for ports to be released

    # Clear state and restart
    manager.processes.clear()

    success = await manager.start_all()
    if not success:
        raise RuntimeError("Failed to start backend in ensure_started")


async def _ensure_all_processes_killed(manager: ServerManager) -> None:
    """Ensure all backend processes are killed, including detached daemons.

    This performs comprehensive cleanup:
    1. Normal stop_all() with graceful shutdown
    2. Force kill any remaining processes holding ports
    3. Clean up PID files

    Args:
        manager: ServerManager instance to clean up
    """
    # Step 1: Try normal stop
    try:
        await manager.stop_all(timeout=0.5)
    except Exception as e:
        print(f"Warning during stop_all: {e}")

    # Step 2: Force kill any processes still holding ports
    all_ports = [port for _, port in manager.config.get_all_ports()]
    ports_in_use = [port for port in all_ports if is_port_in_use(port)]

    if ports_in_use:
        print(f"Force killing processes holding ports: {ports_in_use}")
        await manager._force_kill_port_holders(ports_in_use)
        await asyncio.sleep(0.5)

    # Step 3: Kill nginx by PID file if it still exists
    if manager.nginx_pid_file.exists():
        try:
            nginx_pid = int(manager.nginx_pid_file.read_text().strip())
            try:
                os.kill(nginx_pid, signal.SIGKILL)
                print(f"Force killed nginx PID {nginx_pid}")
            except (OSError, ProcessLookupError):
                pass  # Already dead
            manager.nginx_pid_file.unlink()
        except (ValueError, OSError):
            pass

    # Step 4: Clean up any remaining PID files
    for server_name, server_config in manager.config.servers.items():
        for instance_idx in range(server_config.instances):
            instance_name = f"{server_name}-{instance_idx}"
            pid_file = manager.pid_dir / f"{instance_name}.pid"

            if pid_file.exists():
                try:
                    pid = int(pid_file.read_text().strip())
                    try:
                        os.kill(pid, signal.SIGKILL)
                        print(f"Force killed {instance_name} PID {pid}")
                    except (OSError, ProcessLookupError):
                        pass  # Already dead
                    pid_file.unlink()
                except (ValueError, OSError):
                    pass

    # Step 5: Final verification
    await asyncio.sleep(0.3)
    remaining_ports = [port for port in all_ports if is_port_in_use(port)]
    if remaining_ports:
        print(f"WARNING: Ports still in use after cleanup: {remaining_ports}")


@pytest.fixture(scope="session")
def session_test_config(
    test_settings: Settings, tmp_path_factory: TempPathFactory
) -> DeploymentConfig:
    """Create test deployment configuration with unique ports (session-scoped).

    Depends on test_settings to ensure testcontainers PostgreSQL is running
    and DATASTORE_POSTGRES_DSN env var is set before spawning backend processes.
    """
    _ = test_settings  # Trigger DB setup via conftest.py (env var inheritance)

    # Use tmp_path for truly unique port allocation (survives parallel runs)
    tmp_path = tmp_path_factory.mktemp("port_seed")
    base_port = get_unique_port_base(str(tmp_path))

    return DeploymentConfig(
        nginx=NginxConfig(port=base_port, worker_processes=1, worker_connections=1024),
        servers={
            "broker": ServerConfig(
                port=base_port + 1,
                instances=1,
                modules=["broker"],
                providers=["fakebroker"],
                reload=False,
            ),
            "datafeed": ServerConfig(
                port=base_port + 2, instances=1, modules=["datafeed"], reload=False
            ),
        },
        websocket=WebSocketConfig(routing_strategy="path", query_param_name="type"),
        websocket_routes={"broker": "broker", "datafeed": "datafeed"},
    )


@pytest_asyncio.fixture(scope="module")
async def session_backend_manager(
    session_test_config: DeploymentConfig, tmp_path_factory: TempPathFactory
) -> AsyncGenerator[ServerManager, None]:
    """Session-scoped backend manager - single instance for all tests.

    Starts once, shared by all tests for maximum efficiency.
    Tests use ensure_started() helper for autonomy.
    """
    tmp_path = tmp_path_factory.mktemp("backend_manager_session")
    nginx_config_path = tmp_path / "nginx-test.conf"
    nginx_pid_file = tmp_path / "nginx.pid"

    # Generate nginx config with custom PID file path
    with open(nginx_config_path, "w") as f:
        generate_nginx_config(session_test_config, f, pid_file=nginx_pid_file)

    # Create manager with new API (nginx_config_path is auto-generated in __init__)
    manager = ServerManager(session_test_config)

    # Override directories and config path to use tmp_path (shared by all tests)
    manager.nginx_config_path = nginx_config_path
    manager.pid_dir = tmp_path / ".pids"
    manager.log_dir = tmp_path / ".logs"
    manager.nginx_pid_file = nginx_pid_file
    manager.pid_dir.mkdir(parents=True, exist_ok=True)
    manager.log_dir.mkdir(parents=True, exist_ok=True)

    # Start once for the entire test session
    success = await manager.start_all()
    if not success:
        raise RuntimeError("Failed to start backend for test session")

    # Register for emergency cleanup
    _active_managers.append(manager)

    yield manager

    # Comprehensive cleanup at end of session
    await _ensure_all_processes_killed(manager)

    # Unregister from emergency cleanup
    if manager in _active_managers:
        _active_managers.remove(manager)


# ============================================================================
# Read-Only Integration Tests (Session-Scoped Backend)
# ============================================================================


@pytest.mark.skip(reason="Flaky - under investigation (cleanup/port issues)")
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
@pytest.mark.xdist_group(name="readonly_backend")
class TestBackendManagerReadOnly:
    """Read-only integration tests using session-scoped backend.

    These tests never stop or restart the backend, making them:
    - Fast (single startup for all tests)
    - Reliable (no state mutation between tests)
    - Independent (can run in any order)

    Tests cover: health checks, routing, module isolation, WebSocket probing

    Note: Uses xdist_group to ensure all tests share one worker's session fixture.
    """

    async def test_servers_running_after_startup(
        self, session_backend_manager: ServerManager
    ) -> None:
        """Test that all backend servers and nginx are running."""
        # Verify nginx is running via PID file
        assert session_backend_manager.nginx_pid_file.exists()
        nginx_pid = int(session_backend_manager.nginx_pid_file.read_text().strip())
        assert session_backend_manager._is_process_running(nginx_pid)

        # Verify server processes are running via PID files
        assert len(session_backend_manager.processes) > 0
        for name, process in session_backend_manager.processes.items():
            assert process.poll() is None, f"Process {name} died unexpectedly"

    async def test_health_checks_pass(
        self, session_backend_manager: ServerManager
    ) -> None:
        """Test that health checks pass for all servers."""
        # Check nginx health through broker module
        nginx_port = session_backend_manager.config.nginx.port
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://127.0.0.1:{nginx_port}/api/v1/broker/health", timeout=2.0
            )
            assert response.status_code == 200

        # Check individual server health
        async with httpx.AsyncClient() as client:
            broker_port = session_backend_manager.config.servers["broker"].port
            response = await client.get(
                f"http://127.0.0.1:{broker_port}/api/v1/broker/health", timeout=2.0
            )
            assert response.status_code == 200

            datafeed_port = session_backend_manager.config.servers["datafeed"].port
            response = await client.get(
                f"http://127.0.0.1:{datafeed_port}/api/v1/datafeed/health", timeout=2.0
            )
            assert response.status_code == 200

    async def test_ports_are_bound(
        self, session_backend_manager: ServerManager
    ) -> None:
        """Test that all expected ports are bound and in use."""
        ports = [port for _, port in session_backend_manager.config.get_all_ports()]
        for port in ports:
            assert is_port_in_use(port), f"Port {port} should be in use but is not"

    async def test_broker_routes_through_nginx(
        self, session_backend_manager: ServerManager, auth_cookies: dict[str, str]
    ) -> None:
        """Test that broker routes are accessible through nginx."""
        nginx_port = session_backend_manager.config.nginx.port

        async with httpx.AsyncClient() as client:
            responses: list[httpx.Response] = await asyncio.gather(
                *[
                    client.get(
                        f"http://127.0.0.1:{nginx_port}/api/v1/broker/orders",
                        cookies=auth_cookies,
                        timeout=2.0,
                    ),
                    client.get(
                        f"http://127.0.0.1:{nginx_port}/api/v1/broker/positions",
                        cookies=auth_cookies,
                        timeout=2.0,
                    ),
                ]
            )
            # Both endpoints should return 200 with list (empty if no data)
            for i, response in enumerate(responses):
                assert (
                    response.status_code == 200
                ), f"Request {i} failed: {response.status_code} - {response.text[:200]}"

    async def test_datafeed_routes_through_nginx(
        self, session_backend_manager: ServerManager, auth_cookies: dict[str, str]
    ) -> None:
        """Test that datafeed routes are accessible through nginx."""
        nginx_port = session_backend_manager.config.nginx.port

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://127.0.0.1:{nginx_port}/api/v1/datafeed/config",
                cookies=auth_cookies,
                timeout=2.0,
            )
            assert response.status_code == 200

    async def test_broker_health_endpoint_format(
        self, session_backend_manager: ServerManager
    ) -> None:
        """Test broker health endpoint returns correct format."""
        nginx_port = session_backend_manager.config.nginx.port

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://127.0.0.1:{nginx_port}/api/v1/broker/health", timeout=2.0
            )
            assert response.status_code == 200
            data = response.json()
            assert "module_name" in data
            assert data["module_name"] == "broker"

            response = await client.get(
                f"http://127.0.0.1:{nginx_port}/api/v1/broker/versions", timeout=2.0
            )
            assert response.status_code == 200

    async def test_direct_server_access_broker(
        self, session_backend_manager: ServerManager, auth_cookies: dict[str, str]
    ) -> None:
        """Test direct access to broker server (bypassing nginx)."""
        broker_port = session_backend_manager.config.servers["broker"].port

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://127.0.0.1:{broker_port}/api/v1/broker/health", timeout=2.0
            )
            assert response.status_code == 200

            response = await client.get(
                f"http://127.0.0.1:{broker_port}/api/v1/broker/orders",
                cookies=auth_cookies,
                timeout=2.0,
            )
            # Should return 200 with list (empty if no orders)
            assert (
                response.status_code == 200
            ), f"Expected 200, got {response.status_code}: {response.text[:200]}"

    async def test_direct_server_access_datafeed(
        self, session_backend_manager: ServerManager, auth_cookies: dict[str, str]
    ) -> None:
        """Test direct access to datafeed server (bypassing nginx)."""
        datafeed_port = session_backend_manager.config.servers["datafeed"].port

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://127.0.0.1:{datafeed_port}/api/v1/datafeed/health", timeout=2.0
            )
            assert response.status_code == 200

            response = await client.get(
                f"http://127.0.0.1:{datafeed_port}/api/v1/datafeed/config",
                cookies=auth_cookies,
                timeout=2.0,
            )
            assert response.status_code == 200

    async def test_module_isolation_broker_server(
        self, session_backend_manager: ServerManager, auth_cookies: dict[str, str]
    ) -> None:
        """Test that broker server does NOT serve datafeed routes."""
        broker_port = session_backend_manager.config.servers["broker"].port

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://127.0.0.1:{broker_port}/api/v1/datafeed/config",
                cookies=auth_cookies,
                timeout=2.0,
            )
            assert response.status_code == 404

    async def test_module_isolation_datafeed_server(
        self, session_backend_manager: ServerManager, auth_cookies: dict[str, str]
    ) -> None:
        """Test that datafeed server does NOT serve broker routes."""
        datafeed_port = session_backend_manager.config.servers["datafeed"].port

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://127.0.0.1:{datafeed_port}/api/v1/broker/orders",
                cookies=auth_cookies,
                timeout=2.0,
            )
            assert response.status_code == 404

    async def test_websocket_endpoint_broker(
        self, session_backend_manager: ServerManager
    ) -> None:
        """Test WebSocket endpoint exists on broker module through nginx.

        Uses actual WebSocket connection to verify endpoint is reachable.
        HTTP GET to WS endpoints returns 404 (expected - WS requires protocol upgrade).
        """
        from websockets import connect
        from websockets.exceptions import InvalidHandshake, InvalidStatus

        nginx_port = session_backend_manager.config.nginx.port
        ws_url = f"ws://127.0.0.1:{nginx_port}/api/v1/broker/ws"

        try:
            # Attempt actual WebSocket connection
            # Connection should succeed or fail with auth/validation error (not 404)
            async with connect(ws_url, close_timeout=2):
                # If we get here, the endpoint exists and accepted the connection
                pass
        except InvalidStatus as e:
            # 401/403 = endpoint exists but requires auth (expected in tests)
            # Anything other than 404 means the route is properly configured
            assert e.response.status_code != 404, f"WS endpoint not found: {ws_url}"
        except InvalidHandshake:
            # Server responded but didn't complete handshake - endpoint exists
            pass

    async def test_websocket_endpoint_datafeed(
        self, session_backend_manager: ServerManager
    ) -> None:
        """Test WebSocket endpoint exists on datafeed module through nginx.

        Uses actual WebSocket connection to verify endpoint is reachable.
        HTTP GET to WS endpoints returns 404 (expected - WS requires protocol upgrade).
        """
        from websockets import connect
        from websockets.exceptions import InvalidHandshake, InvalidStatus

        nginx_port = session_backend_manager.config.nginx.port
        ws_url = f"ws://127.0.0.1:{nginx_port}/api/v1/datafeed/ws"

        try:
            # Attempt actual WebSocket connection
            async with connect(ws_url, close_timeout=2):
                # If we get here, the endpoint exists and accepted the connection
                pass
        except InvalidStatus as e:
            # 401/403 = endpoint exists but requires auth (expected in tests)
            assert e.response.status_code != 404, f"WS endpoint not found: {ws_url}"
        except InvalidHandshake:
            # Server responded but didn't complete handshake - endpoint exists
            pass


# ============================================================================
# Lifecycle Integration Tests (Function-Scoped, Full Isolation)
# ============================================================================


@pytest_asyncio.fixture
async def lifecycle_manager(
    test_settings: Settings, tmp_path: Path
) -> AsyncGenerator[ServerManager, None]:
    """Function-scoped backend manager for lifecycle tests.

    Each test gets its own manager with unique ports.
    Provides full isolation for stop/restart testing.
    """
    _ = test_settings  # Ensure DB is set up

    # Unique ports for this test instance
    base_port = get_unique_port_base(str(tmp_path))

    config = DeploymentConfig(
        nginx=NginxConfig(port=base_port, worker_processes=1, worker_connections=1024),
        servers={
            "broker": ServerConfig(
                port=base_port + 1,
                instances=1,
                modules=["broker"],
                providers=["fakebroker"],
                reload=False,
            ),
        },
        websocket=WebSocketConfig(routing_strategy="path", query_param_name="type"),
        websocket_routes={"broker": "broker"},
    )

    nginx_config_path = tmp_path / "nginx-test.conf"
    nginx_pid_file = tmp_path / "nginx.pid"

    with open(nginx_config_path, "w") as f:
        generate_nginx_config(config, f, pid_file=nginx_pid_file)

    manager = ServerManager(config)
    manager.nginx_config_path = nginx_config_path
    manager.pid_dir = tmp_path / ".pids"
    manager.log_dir = tmp_path / ".logs"
    manager.nginx_pid_file = nginx_pid_file
    manager.pid_dir.mkdir(parents=True, exist_ok=True)
    manager.log_dir.mkdir(parents=True, exist_ok=True)

    # Register for emergency cleanup
    _active_managers.append(manager)

    yield manager

    # Comprehensive cleanup
    await _ensure_all_processes_killed(manager)

    # Unregister from emergency cleanup
    if manager in _active_managers:
        _active_managers.remove(manager)


@pytest.mark.skip(reason="Flaky - under investigation (cleanup/port issues)")
@pytest.mark.asyncio
@pytest.mark.xdist_group(name="lifecycle_backend")
class TestBackendManagerLifecycle:
    """Lifecycle tests with function-scoped fixtures.

    Each test gets its own backend manager instance with unique ports.
    Tests cover: start, stop, restart, error handling, status checks.

    Note: Uses xdist_group so tests share one worker's testcontainers DB session.
    """

    async def test_start_and_stop(self, lifecycle_manager: ServerManager) -> None:
        """Test basic start and stop workflow."""
        # Start
        success = await lifecycle_manager.start_all()
        assert success, "Failed to start backend"

        # Verify running
        status = await lifecycle_manager.get_status()
        assert status["running"]
        assert status["nginx"]["healthy"]

        # Get ports for verification
        ports = [port for _, port in lifecycle_manager.config.get_all_ports()]

        # Stop
        await lifecycle_manager.stop_all(timeout=2.0)

        # Verify stopped
        await asyncio.sleep(0.5)
        for port in ports:
            assert not is_port_in_use(port), f"Port {port} still in use after stop"

    async def test_restart_workflow(self, lifecycle_manager: ServerManager) -> None:
        """Test complete restart workflow with PID verification."""
        # Initial start
        success = await lifecycle_manager.start_all()
        assert success

        # Capture initial PIDs
        initial_pids = {
            name: proc.pid for name, proc in lifecycle_manager.processes.items()
        }

        # Stop
        await lifecycle_manager.stop_all(timeout=2.0)
        await asyncio.sleep(1.0)  # Generous wait for port release

        # Clear process references and restart
        lifecycle_manager.processes.clear()
        success = await lifecycle_manager.start_all()
        assert success

        # Verify new PIDs
        new_pids = {
            name: proc.pid for name, proc in lifecycle_manager.processes.items()
        }

        for name in initial_pids:
            if name in new_pids:
                assert (
                    initial_pids[name] != new_pids[name]
                ), f"Process {name} has same PID after restart"

    async def test_start_with_blocked_port(
        self, test_settings: Settings, tmp_path: Path
    ) -> None:
        """Test that start fails gracefully when ports are blocked."""
        _ = test_settings

        # Use unique port for this test
        base_port = get_unique_port_base(str(tmp_path) + "_blocked")

        config = DeploymentConfig(
            nginx=NginxConfig(
                port=base_port, worker_processes=1, worker_connections=1024
            ),
            servers={
                "broker": ServerConfig(
                    port=base_port + 1,
                    instances=1,
                    modules=["broker"],
                    providers=["fakebroker"],
                    reload=False,
                ),
            },
            websocket=WebSocketConfig(routing_strategy="path", query_param_name="type"),
            websocket_routes={"broker": "broker"},
        )

        nginx_config_path = tmp_path / "nginx-test.conf"
        nginx_pid_file = tmp_path / "nginx.pid"

        with open(nginx_config_path, "w") as f:
            generate_nginx_config(config, f, pid_file=nginx_pid_file)

        manager = ServerManager(config)
        manager.nginx_config_path = nginx_config_path
        manager.pid_dir = tmp_path / ".pids"
        manager.log_dir = tmp_path / ".logs"
        manager.nginx_pid_file = nginx_pid_file
        manager.pid_dir.mkdir(parents=True, exist_ok=True)
        manager.log_dir.mkdir(parents=True, exist_ok=True)

        # Block the SERVER port (not nginx) - this makes start_all fail early
        # before any process is spawned, avoiding cleanup issues
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as blocker:
            blocker.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            blocker.bind(("127.0.0.1", config.servers["broker"].port))
            blocker.listen(1)

            success = await manager.start_all()
            # Should fail due to blocked server port (checked before starting)
            assert not success, "Start should fail with blocked port"

    async def test_stop_by_pid_files(self, lifecycle_manager: ServerManager) -> None:
        """Test stopping processes using PID files (detached mode simulation)."""
        # Start backend
        success = await lifecycle_manager.start_all()
        assert success

        # Create new manager instance (simulates CLI in separate process)
        new_manager = ServerManager(lifecycle_manager.config)
        new_manager.nginx_config_path = lifecycle_manager.nginx_config_path
        new_manager.pid_dir = lifecycle_manager.pid_dir
        new_manager.log_dir = lifecycle_manager.log_dir
        new_manager.nginx_pid_file = lifecycle_manager.nginx_pid_file

        # Stop using PID files only
        await new_manager.stop_all(timeout=2.0)

        # Verify original processes stopped
        await asyncio.sleep(0.5)
        for name, process in lifecycle_manager.processes.items():
            assert process.poll() is not None, f"Process {name} still running"

    async def test_get_status_stopped(self, lifecycle_manager: ServerManager) -> None:
        """Test get_status when backend is stopped."""
        # Don't start - just check status of non-running backend
        status = await lifecycle_manager.get_status()

        assert not status["running"]
        assert not status["nginx"]["running"]

    async def test_get_status_running(self, lifecycle_manager: ServerManager) -> None:
        """Test get_status when backend is running."""
        success = await lifecycle_manager.start_all()
        assert success

        status = await lifecycle_manager.get_status()

        assert status["running"]
        assert status["nginx"]["running"]
        assert status["nginx"]["healthy"]
        assert "broker" in status["servers"]
        assert len(status["servers"]["broker"]) > 0
        assert status["servers"]["broker"][0]["overall_healthy"]
