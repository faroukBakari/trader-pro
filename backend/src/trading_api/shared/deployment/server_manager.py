"""Multi-process server manager for backend deployment.

Orchestrates multiple uvicorn server instances with nginx gateway.
Handles process lifecycle, health checks, and graceful shutdown.
"""

import asyncio
import logging
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import httpx

from .config_schema import DeploymentConfig

logger = logging.getLogger(__name__)


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a port is already in use.

    Args:
        port: Port number to check
        host: Host address to check (default: 127.0.0.1)

    Returns:
        True if port is in use, False otherwise
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, port))
            return False
        except OSError:
            return True


def check_all_ports(config: DeploymentConfig) -> tuple[bool, list[tuple[str, int]]]:
    """Check if all required ports are available.

    Args:
        config: Deployment configuration

    Returns:
        Tuple of (all_available, blocked_ports)
        where blocked_ports is list of (name, port) tuples
    """
    blocked_ports: list[tuple[str, int]] = []

    for name, port in config.get_all_ports():
        if is_port_in_use(port):
            blocked_ports.append((name, port))

    return len(blocked_ports) == 0, blocked_ports


async def wait_for_health(
    base_url: str, max_attempts: int = 30, delay: float = 0.5
) -> bool:
    """Wait for a service to become healthy.

    Args:
        base_url: Base URL of the service
        max_attempts: Maximum number of connection attempts
        delay: Delay between attempts in seconds

    Returns:
        True if service is healthy, False otherwise
    """
    async with httpx.AsyncClient() as client:
        for attempt in range(max_attempts):
            try:
                response = await client.get(f"{base_url}/api/v1/health", timeout=2.0)
                if response.status_code == 200:
                    logger.info(f"Service at {base_url} is healthy")
                    return True
            except (
                httpx.ConnectError,
                httpx.RemoteProtocolError,
                httpx.TimeoutException,
            ):
                if attempt < max_attempts - 1:
                    await asyncio.sleep(delay)
            except Exception as e:
                logger.warning(f"Unexpected error checking health at {base_url}: {e}")
                if attempt < max_attempts - 1:
                    await asyncio.sleep(delay)

    logger.error(
        f"Service at {base_url} failed to become healthy after {max_attempts} attempts"
    )
    return False


class ServerManager:
    """Manages multiple backend server processes and nginx gateway.

    Handles process lifecycle, health checks, and graceful shutdown.
    """

    def __init__(self, config: DeploymentConfig, nginx_config_path: Path):
        """Initialize server manager.

        Args:
            config: Deployment configuration
            nginx_config_path: Path to nginx configuration file
        """
        self.config = config
        self.nginx_config_path = nginx_config_path
        self.nginx_pid_file = nginx_config_path.parent / "nginx.pid"
        self.pid_dir = nginx_config_path.parent / ".pids"
        self.processes: dict[str, subprocess.Popen[bytes]] = {}
        self.nginx_process: subprocess.Popen[bytes] | None = None
        self._shutdown_requested = False

        # Ensure PID directory exists
        self.pid_dir.mkdir(parents=True, exist_ok=True)

    def _get_nginx_binary(self) -> str:
        """Get nginx binary path (local or system).

        Returns:
            Path to nginx binary

        Raises:
            FileNotFoundError: If nginx is not found
        """
        # Try local nginx first
        local_nginx = (
            Path(__file__).parent.parent.parent.parent.parent
            / ".local"
            / "bin"
            / "nginx"
        )
        if local_nginx.exists():
            return str(local_nginx)

        # Fall back to system nginx
        try:
            result = subprocess.run(
                ["which", "nginx"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            raise FileNotFoundError("nginx not found. Install with: make install-nginx")

    def _start_server_instance(
        self, name: str, port: int, modules: list[str], reload: bool = True
    ) -> subprocess.Popen[bytes]:
        """Start a single uvicorn server instance.

        Args:
            name: Server instance name
            port: Port to bind to
            modules: List of enabled modules
            reload: Enable auto-reload

        Returns:
            Started process
        """
        env = os.environ.copy()
        env["ENABLED_MODULES"] = ",".join(modules) if modules else ""

        cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "trading_api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "info",
        ]

        if reload:
            cmd.append("--reload")

        logger.info(
            f"Starting {name} on port {port} with modules: {modules or 'none (core only)'}"
        )

        process = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Write PID file for process tracking
        self._write_pid_file(name, process.pid)

        return process

    def _start_nginx(self) -> subprocess.Popen[bytes]:
        """Start nginx gateway.

        Returns:
            Started nginx process
        """
        nginx_binary = self._get_nginx_binary()

        cmd = [
            nginx_binary,
            "-c",
            str(self.nginx_config_path.absolute()),
        ]

        logger.info(f"Starting nginx on port {self.config.nginx.port}")

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        return process

    def _get_pid_file(self, instance_name: str) -> Path:
        """Get PID file path for a server instance.

        Args:
            instance_name: Server instance name

        Returns:
            Path to PID file
        """
        return self.pid_dir / f"{instance_name}.pid"

    def _write_pid_file(self, instance_name: str, pid: int) -> None:
        """Write PID to file for process tracking.

        Args:
            instance_name: Server instance name
            pid: Process ID
        """
        pid_file = self._get_pid_file(instance_name)
        pid_file.write_text(str(pid))

    def _read_pid_file(self, instance_name: str) -> int | None:
        """Read PID from file.

        Args:
            instance_name: Server instance name

        Returns:
            Process ID or None if file doesn't exist
        """
        pid_file = self._get_pid_file(instance_name)
        if not pid_file.exists():
            return None

        try:
            return int(pid_file.read_text().strip())
        except (ValueError, OSError):
            return None

    def _remove_pid_file(self, instance_name: str) -> None:
        """Remove PID file.

        Args:
            instance_name: Server instance name
        """
        pid_file = self._get_pid_file(instance_name)
        if pid_file.exists():
            pid_file.unlink()

    def _is_process_running(self, pid: int) -> bool:
        """Check if a process is running.

        Args:
            pid: Process ID

        Returns:
            True if process is running, False otherwise
        """
        try:
            os.kill(pid, 0)  # Signal 0 just checks if process exists
            return True
        except (OSError, ProcessLookupError):
            return False

    async def _check_health(self, port: int) -> bool:
        """Check if a service is healthy.

        Args:
            port: Port to check

        Returns:
            True if healthy, False otherwise
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"http://127.0.0.1:{port}/api/v1/health", timeout=2.0
                )
                return response.status_code == 200
            except Exception:
                return False

    async def get_status(self) -> dict[str, Any]:
        """Get status of all backend processes.

        Returns:
            Status dictionary with process information
        """
        status: dict[str, Any] = {
            "running": False,
            "nginx": {"running": False, "pid": None, "port": None, "healthy": False},
            "servers": {},
        }

        # Check nginx status
        if self.nginx_pid_file.exists():
            try:
                nginx_pid = int(self.nginx_pid_file.read_text().strip())
                if self._is_process_running(nginx_pid):
                    nginx_port = self.config.nginx.port
                    status["nginx"] = {
                        "running": True,
                        "pid": nginx_pid,
                        "port": nginx_port,
                        "healthy": await self._check_health(nginx_port),
                    }
                    status["running"] = True
            except (ValueError, OSError):
                pass

        # Check server instance statuses
        for server_name, server_config in self.config.servers.items():
            server_instances = []

            for instance_idx in range(server_config.instances):
                port = server_config.port + instance_idx
                instance_name = f"{server_name}-{instance_idx}"
                pid = self._read_pid_file(instance_name)

                instance_info = {
                    "name": instance_name,
                    "port": port,
                    "modules": server_config.modules,
                    "running": False,
                    "pid": None,
                    "healthy": False,
                }

                if pid and self._is_process_running(pid):
                    instance_info["running"] = True
                    instance_info["pid"] = pid
                    instance_info["healthy"] = await self._check_health(port)
                    status["running"] = True

                server_instances.append(instance_info)

            status["servers"][server_name] = server_instances

        return status

    async def stop_all_by_pid(self, timeout: float = 10.0) -> None:
        """Stop all processes using PID files.

        This allows stopping processes that were started by another instance
        of the manager.

        Args:
            timeout: Maximum time to wait for graceful shutdown
        """
        logger.info("Stopping backend processes using PID files...")

        # Step 1: Stop nginx
        if self.nginx_pid_file.exists():
            try:
                nginx_pid = int(self.nginx_pid_file.read_text().strip())
                if self._is_process_running(nginx_pid):
                    logger.info(f"Stopping nginx (PID: {nginx_pid})...")
                    self._stop_process_by_pid(nginx_pid, "nginx", timeout)
                self.nginx_pid_file.unlink()
            except (ValueError, OSError) as e:
                logger.warning(f"Failed to stop nginx: {e}")

        # Step 2: Stop server instances
        for server_name, server_config in self.config.servers.items():
            for instance_idx in range(server_config.instances):
                instance_name = f"{server_name}-{instance_idx}"
                pid = self._read_pid_file(instance_name)

                if pid and self._is_process_running(pid):
                    logger.info(f"Stopping {instance_name} (PID: {pid})...")
                    self._stop_process_by_pid(pid, instance_name, timeout)

                self._remove_pid_file(instance_name)

        logger.info("All processes stopped")

    def _stop_process_by_pid(self, pid: int, name: str, timeout: float) -> None:
        """Stop a process by PID.

        Args:
            pid: Process ID
            name: Process name for logging
            timeout: Maximum time to wait before force kill
        """
        if not self._is_process_running(pid):
            logger.info(f"{name} already stopped")
            return

        try:
            # Try graceful shutdown
            os.kill(pid, signal.SIGTERM)
            start_time = time.time()

            while time.time() - start_time < timeout:
                if not self._is_process_running(pid):
                    logger.info(f"{name} stopped gracefully")
                    return
                time.sleep(0.1)

            # Force kill if timeout exceeded
            logger.warning(f"{name} did not stop gracefully, force killing")
            os.kill(pid, signal.SIGKILL)
            time.sleep(0.5)  # Give it a moment to die

        except (OSError, ProcessLookupError) as e:
            logger.warning(f"Error stopping {name}: {e}")

    async def start_all(self) -> bool:
        """Start all server instances and nginx gateway.

        Returns:
            True if all servers started successfully, False otherwise
        """
        logger.info("Starting multi-process backend...")

        # Check all ports are available
        all_available, blocked_ports = check_all_ports(self.config)
        if not all_available:
            logger.error("Cannot start servers - ports already in use:")
            for name, port in blocked_ports:
                logger.error(f"  {name}: port {port}")
            return False

        # Start all server instances
        for server_name, server_config in self.config.servers.items():
            for instance_idx in range(server_config.instances):
                port = server_config.port + instance_idx
                instance_name = f"{server_name}-{instance_idx}"

                try:
                    process = self._start_server_instance(
                        instance_name,
                        port,
                        server_config.modules,
                        server_config.reload,
                    )
                    self.processes[instance_name] = process

                except Exception as e:
                    logger.error(f"Failed to start {instance_name}: {e}")
                    await self.stop_all()
                    return False

        # Wait for all servers to become healthy
        logger.info("Waiting for all servers to become healthy...")
        all_healthy = True

        for server_name, server_config in self.config.servers.items():
            for instance_idx in range(server_config.instances):
                port = server_config.port + instance_idx
                instance_name = f"{server_name}-{instance_idx}"
                base_url = f"http://127.0.0.1:{port}"

                healthy = await wait_for_health(base_url)
                if not healthy:
                    logger.error(f"{instance_name} failed to become healthy")
                    all_healthy = False

        if not all_healthy:
            logger.error("Not all servers became healthy - shutting down")
            await self.stop_all()
            return False

        # Start nginx
        try:
            self.nginx_process = self._start_nginx()
            logger.info("Nginx started successfully")
        except Exception as e:
            logger.error(f"Failed to start nginx: {e}")
            await self.stop_all()
            return False

        # Wait for nginx to become healthy
        nginx_url = f"http://127.0.0.1:{self.config.nginx.port}"
        nginx_healthy = await wait_for_health(nginx_url)

        if not nginx_healthy:
            logger.error("Nginx failed to become healthy - shutting down")
            await self.stop_all()
            return False

        logger.info("All servers started successfully!")
        logger.info(f"Backend available at: {nginx_url}")
        return True

    async def stop_all(self, timeout: float = 10.0) -> None:
        """Stop all servers gracefully.

        Shutdown order: nginx → functional modules → core

        Args:
            timeout: Maximum time to wait for graceful shutdown before force kill
        """
        if self._shutdown_requested:
            return

        self._shutdown_requested = True
        logger.info("Shutting down all servers...")

        # Step 1: Stop nginx first using its PID file (if available)
        if self.nginx_process:
            logger.info("Stopping nginx...")
            self._stop_nginx(timeout)
            self.nginx_process = None

        # Step 2: Stop functional module servers
        # Step 3: Stop core server last (if exists)
        # For now, stop all server processes in reverse order
        for instance_name in reversed(list(self.processes.keys())):
            process = self.processes[instance_name]
            logger.info(f"Stopping {instance_name}...")
            self._stop_process(process, instance_name, timeout)

        self.processes.clear()
        logger.info("All servers stopped")

    def _stop_process(
        self, process: subprocess.Popen[bytes], name: str, timeout: float
    ) -> None:
        """Stop a single process gracefully with timeout.

        Args:
            process: Process to stop
            name: Process name for logging
            timeout: Maximum time to wait before force kill
        """
        if process.poll() is not None:
            logger.info(f"{name} already stopped")
            self._remove_pid_file(name)
            return

        # Try graceful shutdown
        try:
            process.send_signal(signal.SIGTERM)
            start_time = time.time()

            while time.time() - start_time < timeout:
                if process.poll() is not None:
                    logger.info(f"{name} stopped gracefully")
                    self._remove_pid_file(name)
                    return
                time.sleep(0.1)

            # Force kill if timeout exceeded
            logger.warning(f"{name} did not stop gracefully, force killing")
            process.kill()
            process.wait(timeout=2)
            self._remove_pid_file(name)

        except Exception as e:
            logger.error(f"Error stopping {name}: {e}")
            try:
                process.kill()
                self._remove_pid_file(name)
            except Exception:
                pass

    def _stop_nginx(self, timeout: float) -> None:
        """Stop nginx using its PID file for proper shutdown.

        Args:
            timeout: Maximum time to wait before force kill
        """
        # Try using nginx's quit signal via PID file first
        if self.nginx_pid_file.exists():
            try:
                with open(self.nginx_pid_file, "r") as f:
                    nginx_pid = int(f.read().strip())

                logger.info(f"Stopping nginx using PID file (PID: {nginx_pid})...")

                # Send QUIT signal for graceful shutdown
                os.kill(nginx_pid, signal.SIGQUIT)

                start_time = time.time()
                while time.time() - start_time < timeout:
                    # Check if PID file still exists
                    if not self.nginx_pid_file.exists():
                        logger.info("nginx stopped gracefully")
                        return

                    # Check if process is still running
                    try:
                        os.kill(nginx_pid, 0)  # Check if process exists
                        time.sleep(0.1)
                    except OSError:
                        # Process no longer exists
                        logger.info("nginx stopped gracefully")
                        # Clean up PID file if it still exists
                        if self.nginx_pid_file.exists():
                            self.nginx_pid_file.unlink()
                        return

                # Timeout - force kill
                logger.warning("nginx did not stop gracefully, force killing")
                try:
                    os.kill(nginx_pid, signal.SIGKILL)
                    if self.nginx_pid_file.exists():
                        self.nginx_pid_file.unlink()
                except OSError:
                    pass

            except (ValueError, OSError, FileNotFoundError) as e:
                logger.warning(f"Failed to stop nginx using PID file: {e}")
                # Fall back to stopping the process directly
                if self.nginx_process:
                    self._stop_process(self.nginx_process, "nginx", timeout)

        else:
            # PID file doesn't exist, fall back to process-based stop
            logger.warning("nginx PID file not found, using process-based stop")
            if self.nginx_process:
                self._stop_process(self.nginx_process, "nginx", timeout)

    def wait_for_shutdown_signal(self) -> None:
        """Wait for shutdown signal (Ctrl+C).

        Blocks until SIGINT or SIGTERM is received.
        """
        shutdown_event = threading.Event()

        def signal_handler(sig: int, frame: Any) -> None:
            logger.info(f"Received signal {sig}, initiating shutdown...")
            shutdown_event.set()

        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Wait for shutdown signal
        try:
            shutdown_event.wait()
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
            shutdown_event.set()

    async def run(self) -> int:
        """Run the multi-process backend.

        Returns:
            Exit code (0 for success, 1 for failure)
        """
        try:
            # Start all servers
            success = await self.start_all()
            if not success:
                return 1

            # Wait for shutdown signal
            logger.info("Press Ctrl+C to stop all servers")
            self.wait_for_shutdown_signal()

            # Stop all servers
            await self.stop_all()
            return 0

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            await self.stop_all()
            return 1
