"""Integration tests for backend_manager.py with real processes.

These tests start actual backend processes to verify multi-process behavior,
nginx routing, and end-to-end functionality. They are SLOWER but provide
comprehensive coverage of real-world scenarios.

Test Flow (optimized for minimal overhead):
1. Start servers once at session start
2. Most tests use session backend (read-only operations)
3. Tests requiring stop/restart use ensure_started helper for autonomy
4. Cleanup at session end

Test Categories:
- Multi-process lifecycle (start/stop/restart)
- Module routing and isolation in multi-process mode
- Nginx routing correctness
- Health check integration
- WebSocket routing
- Error handling
"""

import asyncio
import os
import signal
import socket
from collections.abc import AsyncGenerator
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from pytest import TempPathFactory

from scripts.backend_manager import ServerManager, generate_nginx_config, is_port_in_use
from trading_api.shared.deployment import (
    DeploymentConfig,
    NginxConfig,
    ServerConfig,
    WebSocketConfig,
)

# ============================================================================
# Fixtures and Helpers
# ============================================================================


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
    await manager.stop_all(timeout=2.0)
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
        await manager.stop_all(timeout=3.0)
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
def session_test_config() -> DeploymentConfig:
    """Create test deployment configuration with unique ports (session-scoped)."""
    # Use process-specific port offset to avoid conflicts in parallel tests
    base_port = 19000 + (os.getpid() % 100) * 10

    return DeploymentConfig(
        nginx=NginxConfig(port=base_port, worker_processes=1, worker_connections=1024),
        servers={
            "broker": ServerConfig(
                port=base_port + 1,
                instances=1,
                modules=["broker"],
                reload=False,
            ),
            "datafeed": ServerConfig(
                port=base_port + 2, instances=1, modules=["datafeed"], reload=False
            ),
        },
        websocket=WebSocketConfig(routing_strategy="path", query_param_name="type"),
        websocket_routes={"broker": "broker", "datafeed": "datafeed"},
    )


@pytest_asyncio.fixture(scope="session")
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

    yield manager

    # Comprehensive cleanup at end of session
    await _ensure_all_processes_killed(manager)


# ============================================================================
# Integration Tests (Single Session, Optimal Flow)
# ============================================================================


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
class TestBackendManagerIntegration:
    """Comprehensive integration tests for backend manager.

    Uses single session backend for maximum efficiency.
    Tests are autonomous via ensure_started() helper.

    Test execution order (pytest-order or manual numbering):
    1. Lifecycle tests (start, health, status)
    2. Restart workflow
    3. Routing tests (nginx, direct, isolation)
    4. WebSocket tests
    5. Stop tests
    6. Error handling (isolated instances)
    """

    async def test_01_start_all_servers_successfully(
        self, session_backend_manager: ServerManager
    ) -> None:
        """Test that all backend servers and nginx are running."""
        # Servers already started by session fixture
        # Verify nginx is running via PID file
        assert session_backend_manager.nginx_pid_file.exists()
        nginx_pid = int(session_backend_manager.nginx_pid_file.read_text().strip())
        assert session_backend_manager._is_process_running(nginx_pid)

        # Verify server processes are running via PID files
        assert len(session_backend_manager.processes) > 0
        for name, process in session_backend_manager.processes.items():
            assert process.poll() is None, f"Process {name} died unexpectedly"

    async def test_02_health_checks_pass_after_startup(
        self, session_backend_manager: ServerManager
    ) -> None:
        """Test that health checks pass for all servers after startup."""
        await ensure_started(session_backend_manager)

        # Check nginx health through broker module
        nginx_port = session_backend_manager.config.nginx.port
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://127.0.0.1:{nginx_port}/api/v1/broker/health", timeout=5.0
            )
            assert response.status_code == 200

        # Check individual server health using their respective modules
        async with httpx.AsyncClient() as client:
            # Broker server
            broker_port = session_backend_manager.config.servers["broker"].port
            response = await client.get(
                f"http://127.0.0.1:{broker_port}/api/v1/broker/health", timeout=5.0
            )
            assert response.status_code == 200

            # Datafeed server
            datafeed_port = session_backend_manager.config.servers["datafeed"].port
            response = await client.get(
                f"http://127.0.0.1:{datafeed_port}/api/v1/datafeed/health", timeout=5.0
            )
            assert response.status_code == 200

    async def test_03_processes_are_alive(
        self, session_backend_manager: ServerManager
    ) -> None:
        """Test that all backend processes remain alive."""
        await ensure_started(session_backend_manager)

        # Verify nginx is running using broker health endpoint
        nginx_port = session_backend_manager.config.nginx.port
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://127.0.0.1:{nginx_port}/api/v1/broker/health", timeout=5.0
            )
            assert response.status_code == 200

        # Verify all server processes are running
        for name, process in session_backend_manager.processes.items():
            assert process.poll() is None, f"Process {name} died unexpectedly"

    async def test_04_ports_are_bound(
        self, session_backend_manager: ServerManager
    ) -> None:
        """Test that all expected ports are bound and in use."""
        await ensure_started(session_backend_manager)

        # Get all configured ports
        ports = [port for _, port in session_backend_manager.config.get_all_ports()]

        # Verify all ports are in use
        for port in ports:
            assert is_port_in_use(port), f"Port {port} should be in use but is not"

    async def test_05_restart_workflow(
        self, session_backend_manager: ServerManager
    ) -> None:
        """Test complete restart workflow."""
        await ensure_started(session_backend_manager)

        # Get initial PIDs
        initial_pids = {
            name: proc.pid for name, proc in session_backend_manager.processes.items()
        }

        # Stop
        await session_backend_manager.stop_all(timeout=2.0)
        await asyncio.sleep(0.5)

        # Restart
        session_backend_manager.processes.clear()

        success = await session_backend_manager.start_all()
        assert success

        # Verify new PIDs (processes were restarted)
        new_pids = {
            name: proc.pid for name, proc in session_backend_manager.processes.items()
        }

        # PIDs should be different (new processes)
        for name in initial_pids.keys():
            if name in new_pids:
                assert (
                    initial_pids[name] != new_pids[name]
                ), f"Process {name} has same PID after restart"

    async def test_06_broker_routes_through_nginx(
        self, session_backend_manager: ServerManager
    ) -> None:
        """Test that broker routes are accessible through nginx."""
        await ensure_started(session_backend_manager)

        nginx_port = session_backend_manager.config.nginx.port

        async with httpx.AsyncClient() as client:
            # Broker endpoint
            response = await client.get(
                f"http://127.0.0.1:{nginx_port}/api/v1/broker/orders", timeout=5.0
            )
            assert response.status_code in [200, 404]

            # Positions endpoint
            response = await client.get(
                f"http://127.0.0.1:{nginx_port}/api/v1/broker/positions", timeout=5.0
            )
            assert response.status_code in [200, 404]

    async def test_07_datafeed_routes_through_nginx(
        self, session_backend_manager: ServerManager
    ) -> None:
        """Test that datafeed routes are accessible through nginx."""
        await ensure_started(session_backend_manager)

        nginx_port = session_backend_manager.config.nginx.port

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://127.0.0.1:{nginx_port}/api/v1/datafeed/config", timeout=5.0
            )
            assert response.status_code == 200

    async def test_08_broker_health_endpoint_format(
        self, session_backend_manager: ServerManager
    ) -> None:
        """Test broker health endpoint returns correct format."""
        await ensure_started(session_backend_manager)

        nginx_port = session_backend_manager.config.nginx.port

        async with httpx.AsyncClient() as client:
            # Health endpoint through nginx
            response = await client.get(
                f"http://127.0.0.1:{nginx_port}/api/v1/broker/health", timeout=5.0
            )
            assert response.status_code == 200
            data = response.json()
            assert "module_name" in data
            assert data["module_name"] == "broker"

            # Versions endpoint
            response = await client.get(
                f"http://127.0.0.1:{nginx_port}/api/v1/broker/versions", timeout=5.0
            )
            assert response.status_code == 200

    async def test_09_direct_server_access_broker(
        self, session_backend_manager: ServerManager
    ) -> None:
        """Test direct access to broker server (bypassing nginx)."""
        await ensure_started(session_backend_manager)

        broker_port = session_backend_manager.config.servers["broker"].port

        async with httpx.AsyncClient() as client:
            # Direct broker health check
            response = await client.get(
                f"http://127.0.0.1:{broker_port}/api/v1/broker/health", timeout=5.0
            )
            assert response.status_code == 200

            # Broker endpoint
            response = await client.get(
                f"http://127.0.0.1:{broker_port}/api/v1/broker/orders", timeout=5.0
            )
            assert response.status_code in [200, 404]

    async def test_10_direct_server_access_datafeed(
        self, session_backend_manager: ServerManager
    ) -> None:
        """Test direct access to datafeed server (bypassing nginx)."""
        await ensure_started(session_backend_manager)

        datafeed_port = session_backend_manager.config.servers["datafeed"].port

        async with httpx.AsyncClient() as client:
            # Direct datafeed health check
            response = await client.get(
                f"http://127.0.0.1:{datafeed_port}/api/v1/datafeed/health", timeout=5.0
            )
            assert response.status_code == 200

            # Datafeed endpoint
            response = await client.get(
                f"http://127.0.0.1:{datafeed_port}/api/v1/datafeed/config",
                timeout=5.0,
            )
            assert response.status_code == 200

    async def test_11_module_isolation_broker_server(
        self, session_backend_manager: ServerManager
    ) -> None:
        """Test that broker server does NOT serve datafeed routes."""
        await ensure_started(session_backend_manager)

        broker_port = session_backend_manager.config.servers["broker"].port

        async with httpx.AsyncClient() as client:
            # Datafeed route should NOT be available on broker server
            response = await client.get(
                f"http://127.0.0.1:{broker_port}/api/v1/datafeed/config", timeout=5.0
            )
            assert response.status_code == 404

    async def test_12_module_isolation_datafeed_server(
        self, session_backend_manager: ServerManager
    ) -> None:
        """Test that datafeed server does NOT serve broker routes."""
        await ensure_started(session_backend_manager)

        datafeed_port = session_backend_manager.config.servers["datafeed"].port

        async with httpx.AsyncClient() as client:
            # Broker route should NOT be available on datafeed server
            response = await client.get(
                f"http://127.0.0.1:{datafeed_port}/api/v1/broker/orders", timeout=5.0
            )
            assert response.status_code == 404

    async def test_13_websocket_connection_broker(
        self, session_backend_manager: ServerManager
    ) -> None:
        """Test WebSocket connection to broker module through nginx."""
        await ensure_started(session_backend_manager)

        nginx_port = session_backend_manager.config.nginx.port

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://127.0.0.1:{nginx_port}/api/v1/broker/ws", timeout=5.0
            )
            # WebSocket endpoints return various codes for regular HTTP
            assert response.status_code in [426, 400, 404, 101]

    async def test_14_websocket_connection_datafeed(
        self, session_backend_manager: ServerManager
    ) -> None:
        """Test WebSocket connection to datafeed module through nginx."""
        await ensure_started(session_backend_manager)

        nginx_port = session_backend_manager.config.nginx.port

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://127.0.0.1:{nginx_port}/api/v1/datafeed/ws", timeout=5.0
            )
            assert response.status_code in [426, 400, 404, 101]

    async def test_15_stop_all_servers_gracefully(
        self, session_backend_manager: ServerManager
    ) -> None:
        """Test graceful shutdown of all servers."""
        await ensure_started(session_backend_manager)

        # Get ports before shutdown
        ports = [port for _, port in session_backend_manager.config.get_all_ports()]

        # Stop all
        await session_backend_manager.stop_all(timeout=3.0)

        # Verify nginx stopped (PID file should be removed)
        assert not session_backend_manager.nginx_pid_file.exists() or (
            not session_backend_manager._is_process_running(
                int(session_backend_manager.nginx_pid_file.read_text().strip())
            )
        )

        for name, process in session_backend_manager.processes.items():
            assert process.poll() is not None, f"Process {name} still running"

        # Verify ports released
        await asyncio.sleep(0.5)
        for port in ports:
            assert not is_port_in_use(port), f"Port {port} still in use after shutdown"

    async def test_16_start_with_blocked_ports(self, tmp_path: Path) -> None:
        """Test that start fails gracefully when ports are blocked.

        Uses isolated manager instance with unique ports.
        """
        # Create unique test config with different ports
        # Use test-specific port range to avoid collisions with other tests
        base_port = 18100

        blocked_config = DeploymentConfig(
            nginx=NginxConfig(
                port=base_port, worker_processes=1, worker_connections=1024
            ),
            servers={
                "broker": ServerConfig(
                    port=base_port + 1,
                    instances=1,
                    modules=["broker"],
                    reload=False,
                ),
            },
            websocket=WebSocketConfig(routing_strategy="path", query_param_name="type"),
            websocket_routes={"broker": "broker"},
        )

        # Block nginx port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as blocker:
            blocker.bind(("127.0.0.1", blocked_config.nginx.port))

            # Try to start backend
            nginx_config_path = tmp_path / "nginx-test.conf"
            nginx_pid_file = tmp_path / "nginx.pid"

            with open(nginx_config_path, "w") as f:
                generate_nginx_config(blocked_config, f, pid_file=nginx_pid_file)

            manager = ServerManager(blocked_config)
            manager.nginx_config_path = nginx_config_path
            manager.pid_dir = tmp_path / ".pids"
            manager.log_dir = tmp_path / ".logs"
            manager.nginx_pid_file = nginx_pid_file
            manager.pid_dir.mkdir(parents=True, exist_ok=True)
            manager.log_dir.mkdir(parents=True, exist_ok=True)

            success = await manager.start_all()

            # Should fail due to blocked port
            assert not success

    async def test_17_stop_by_pid_files(
        self, session_backend_manager: ServerManager
    ) -> None:
        """Test stopping processes using PID files (detached mode simulation)."""
        await ensure_started(session_backend_manager)

        # Create new manager instance (simulates separate process)
        new_manager = ServerManager(session_backend_manager.config)
        new_manager.nginx_config_path = session_backend_manager.nginx_config_path
        new_manager.pid_dir = session_backend_manager.pid_dir
        new_manager.log_dir = session_backend_manager.log_dir
        new_manager.nginx_pid_file = session_backend_manager.nginx_pid_file

        # Stop using PID files
        await new_manager.stop_all(timeout=3.0)

        # Verify processes stopped
        await asyncio.sleep(0.3)
        for name, process in session_backend_manager.processes.items():
            assert process.poll() is not None, f"Process {name} still running"

    async def test_18_get_status_stopped(
        self, session_backend_manager: ServerManager
    ) -> None:
        """Test get_status when backend is stopped."""
        # Ensure stopped (test_18 or test_15 should have stopped it)
        await session_backend_manager.stop_all(timeout=2.0)
        await asyncio.sleep(0.3)

        status = await session_backend_manager.get_status()

        assert not status["running"]
        assert not status["nginx"]["running"]
