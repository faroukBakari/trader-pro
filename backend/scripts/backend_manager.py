#!/usr/bin/env python3
"""Backend Manager - Unified CLI for multi-process backend management.

Consolidates all backend process management functionality:
- Start/stop/restart multi-process backend with nginx gateway
- Generate and validate nginx configuration
- Check status of running processes

Commands:
    backend-manager start [config]     Start multi-process backend
    backend-manager stop               Stop all running processes
    backend-manager status             Show status of running processes
    backend-manager restart [config]   Restart all processes
    backend-manager gen-nginx-conf     Generate nginx configuration (debug)

Examples:
    backend-manager start
    backend-manager start dev-config.yaml --no-reload
    backend-manager status
    backend-manager stop
    backend-manager restart
    backend-manager gen-nginx-conf dev-config.yaml -o nginx-dev.conf
"""

import argparse
import asyncio
import json
import logging
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, TextIO

import httpx

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from trading_api.shared.deployment import DeploymentConfig, load_config  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ============================================================================
# Server Manager - Process Management
# ============================================================================


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a port is already in use by an active process.

    Uses SO_REUSEADDR to match uvicorn's behavior, allowing ports
    in TIME_WAIT state to be considered available.

    Args:
        port: Port number to check
        host: Host address to check (default: 127.0.0.1)

    Returns:
        True if port is in use by active process, False otherwise
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            # Match uvicorn's socket options
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
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

    def __init__(
        self, config: DeploymentConfig, nginx_config_path: Path, detached: bool = False
    ):
        """Initialize server manager.

        Args:
            config: Deployment configuration
            nginx_config_path: Path to nginx configuration file
            detached: Run servers in detached background mode (like nohup)
        """
        self.config = config
        self.nginx_config_path = nginx_config_path
        self.nginx_pid_file = nginx_config_path.parent / "nginx.pid"
        self.pid_dir = nginx_config_path.parent / ".pids"
        self.log_dir = nginx_config_path.parent / ".local" / "logs"
        self.unified_log_path = self.log_dir / "backend-unified.log"
        self.detached = detached
        self.processes: dict[str, subprocess.Popen[bytes]] = {}
        self.nginx_process: subprocess.Popen[bytes] | None = None
        self._shutdown_requested = False

        # Ensure PID and log directories exist
        self.pid_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def _generate_specs_and_clients(self) -> None:
        """Generate OpenAPI/AsyncAPI specs and Python clients before startup.

        This ensures specs and clients are always fresh on server start.
        Runs synchronously before uvicorn starts to avoid race conditions.
        """
        backend_dir = Path(__file__).parent.parent

        try:
            # Export OpenAPI spec
            logger.info("Generating OpenAPI specification...")
            subprocess.run(
                [sys.executable, str(backend_dir / "scripts/export_openapi_spec.py")],
                check=True,
                capture_output=True,
            )

            # Export AsyncAPI spec
            logger.info("Generating AsyncAPI specification...")
            subprocess.run(
                [sys.executable, str(backend_dir / "scripts/export_asyncapi_spec.py")],
                check=True,
                capture_output=True,
            )

            # Generate Python clients
            logger.info("Generating Python HTTP clients...")
            subprocess.run(
                [
                    sys.executable,
                    str(backend_dir / "scripts/generate_python_clients.py"),
                ],
                check=True,
                capture_output=True,
            )

            logger.info("✅ Specs and clients generated successfully")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to generate specs/clients: {e}")
            # Continue anyway - server can start without fresh clients

    def _get_nginx_binary(self) -> str:
        """Get nginx binary path (local or system).

        Returns:
            Path to nginx binary

        Raises:
            FileNotFoundError: If nginx is not found
        """
        # Try local nginx first
        local_nginx = Path(__file__).parent.parent / ".local" / "bin" / "nginx"
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

    def _create_uvicorn_log_config(self, log_file_path: Path) -> Path:
        """Create uvicorn logging configuration file.

        Configures uvicorn to write logs directly to files, which works
        reliably with reload mode (unlike threading-based approaches).

        Args:
            log_file_path: Path to individual server log file

        Returns:
            Path to generated log config JSON file
        """
        log_config = {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                },
            },
            "handlers": {
                "file": {
                    "class": "logging.FileHandler",
                    "filename": str(log_file_path),
                    "mode": "a",
                    "formatter": "default",
                },
            },
            "loggers": {
                "uvicorn": {"handlers": ["file"], "level": "INFO"},
                "uvicorn.error": {"handlers": ["file"], "level": "INFO"},
                "uvicorn.access": {"handlers": ["file"], "level": "INFO"},
            },
        }

        # Write config to temporary file
        config_path = self.log_dir / f"{log_file_path.stem}-logging.json"
        with open(config_path, "w") as f:
            json.dump(log_config, f, indent=2)

        return config_path

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

        # Create log file path and uvicorn logging config
        log_file_path = self.log_dir / f"{name}.log"
        log_config_path = self._create_uvicorn_log_config(log_file_path)

        cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "trading_api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-config",
            str(log_config_path),
        ]

        if reload:
            cmd.append("--reload")
            # Exclude generated files and management scripts to prevent reload loops
            cmd.extend(
                [
                    "--reload-exclude",
                    "*/openapi.json",
                    "--reload-exclude",
                    "*/asyncapi.json",
                    "--reload-exclude",
                    "*/clients/*",
                    "--reload-exclude",
                    "*/.local/*",
                    "--reload-exclude",
                    "*/.pids/*",
                    "--reload-exclude",
                    "*/scripts/*",
                    "--reload-exclude",
                    "*/__pycache__/*",
                    "--reload-exclude",
                    "*.pyc",
                ]
            )

        logger.info(
            f"Starting {name} on port {port} with modules: {modules or 'none (core only)'}"
        )
        logger.info(f"Logs: {log_file_path}")

        # Start process (detached or interactive)
        if self.detached:
            # Detached mode: let uvicorn handle all logging via log config
            process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,  # Detach from parent session
            )
        else:
            # Interactive mode: also let uvicorn handle logging
            # Process output goes to configured log file
            process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
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

        if self.detached:
            # Detached mode: nginx manages its own logs
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        else:
            # Interactive mode
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

    async def _force_kill_port_holders(self, ports: list[int]) -> None:
        """Force kill processes holding specified ports.

        Args:
            ports: List of ports to free
        """
        killed_any = False

        try:
            # Use lsof to find processes holding the ports
            for port in ports:
                result = subprocess.run(
                    ["lsof", "-ti", f":{port}"],
                    capture_output=True,
                    text=True,
                    check=False,
                )

                if result.returncode == 0 and result.stdout.strip():
                    pids = [int(pid) for pid in result.stdout.strip().split()]
                    for pid in pids:
                        if self._is_process_running(pid):
                            logger.warning(
                                f"Force killing PID {pid} holding port {port}"
                            )
                            try:
                                os.kill(pid, signal.SIGKILL)
                                killed_any = True
                                time.sleep(0.1)  # Brief wait per process
                            except (OSError, ProcessLookupError) as e:
                                logger.warning(f"Failed to kill PID {pid}: {e}")
                else:
                    logger.debug(f"No process found using port {port} via lsof")

        except FileNotFoundError:
            logger.warning("lsof command not available, cannot identify port holders")
        except Exception as e:
            logger.warning(f"Error identifying port holders: {e}")

        if killed_any:
            # Give kernel more time to release ports after kills
            await asyncio.sleep(0.3)

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

        # Wait for ports to be released
        await self._wait_for_ports_release()

    async def _wait_for_ports_release(
        self, max_wait: float = 2.0, max_retries: int = 3
    ) -> None:
        """Wait for all configured ports to be released with retry and force kill.

        Args:
            max_wait: Maximum time to wait per retry in seconds
            max_retries: Number of retries before giving up
        """
        all_ports = [port for _, port in self.config.get_all_ports()]

        for retry in range(max_retries):
            start_time = time.time()

            # Wait for ports to be released
            while time.time() - start_time < max_wait:
                ports_in_use = [port for port in all_ports if is_port_in_use(port)]

                if not ports_in_use:
                    if retry > 0:
                        logger.info(f"All ports released after retry {retry}")
                    else:
                        logger.debug("All ports released")
                    return

                await asyncio.sleep(0.1)

            # Check which ports are still in use
            ports_in_use = [port for port in all_ports if is_port_in_use(port)]

            if not ports_in_use:
                logger.debug("All ports released")
                return

            # Try force killing processes holding ports
            logger.warning(
                f"Ports still in use after {max_wait}s (retry {retry + 1}/{max_retries}): {ports_in_use}"
            )
            logger.warning("Identifying and force killing processes holding ports...")
            await self._force_kill_port_holders(ports_in_use)

            # Wait after force kill
            await asyncio.sleep(0.5)

            # Check if ports are now released
            remaining_ports = [port for port in all_ports if is_port_in_use(port)]

            if not remaining_ports:
                logger.info(f"All ports released after force kill (retry {retry + 1})")
                return

            if retry < max_retries - 1:
                logger.warning(
                    f"Some ports still in use after force kill, will retry: {remaining_ports}"
                )
            else:
                # Final retry exhausted
                logger.error(
                    f"FAILED to release ports after {max_retries} retries: {remaining_ports}"
                )
                logger.error("Manual intervention may be required")
                logger.error("Try: sudo lsof -ti :<port> | xargs kill -9")

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
                time.sleep(0.05)  # Check more frequently

            # Force kill if timeout exceeded
            logger.warning(f"{name} did not stop gracefully, force killing")
            os.kill(pid, signal.SIGKILL)
            time.sleep(0.2)  # Wait for OS to clean up resources

        except (OSError, ProcessLookupError) as e:
            logger.warning(f"Error stopping {name}: {e}")

    async def start_all(self) -> bool:
        """Start all server instances and nginx gateway.

        Returns:
            True if all servers started successfully, False otherwise
        """
        logger.info("Starting multi-process backend...")

        # Generate specs and clients before starting servers
        self._generate_specs_and_clients()

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
                time.sleep(0.05)  # Check more frequently

            # Force kill if timeout exceeded
            logger.warning(f"{name} did not stop gracefully, force killing")
            process.kill()
            process.wait(timeout=1)  # Reduced from 2s
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
                        time.sleep(0.05)  # Check more frequently
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

            if self.detached:
                # Detached mode: return immediately after servers start
                logger.info("All servers running in background (detached mode)")
                logger.info(f"Server logs: {self.log_dir}/*.log")
                logger.info(f"Tail logs: make logs-tail")
                logger.info(f"Stop servers: make backend-manager-stop")
                return 0
            else:
                # Interactive mode: wait for shutdown signal
                logger.info("Press Ctrl+C to stop all servers")
                self.wait_for_shutdown_signal()

                # Stop all servers
                await self.stop_all()
                return 0

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            await self.stop_all()
            return 1


# ============================================================================
# Nginx Configuration Generation
# ============================================================================


def generate_upstream_blocks(config: DeploymentConfig) -> str:
    """Generate nginx upstream blocks for all servers.

    Args:
        config: Deployment configuration

    Returns:
        Nginx upstream configuration blocks
    """
    upstreams = []

    for server_name, server_config in config.servers.items():
        # Create upstream block for this server
        upstream_servers = []
        for instance_idx in range(server_config.instances):
            port = server_config.port + instance_idx
            upstream_servers.append(f"        server 127.0.0.1:{port};")

        upstream_block = f"""    upstream {server_name}_backend {{
{chr(10).join(upstream_servers)}
    }}"""
        upstreams.append(upstream_block)

    return "\n\n".join(upstreams)


def generate_rest_location_blocks(config: DeploymentConfig) -> str:
    """Generate nginx location blocks for REST API routing.

    Args:
        config: Deployment configuration

    Returns:
        Nginx location configuration blocks
    """
    locations = []

    # Core server handles shared endpoints (health, versions, docs)
    # If no core server, use the first available server as fallback
    fallback_server = (
        "core" if "core" in config.servers else list(config.servers.keys())[0]
    )

    core_location = f"""        # Core endpoints (health, versions, docs)
        location ~ ^/api/v1/(health|version|versions|docs|redoc|openapi.json)$ {{
            proxy_pass http://{fallback_server}_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }}"""
    locations.append(core_location)

    # Module-specific endpoints
    for server_name, server_config in config.servers.items():
        if server_name == "core":
            continue

        for module in server_config.modules:
            module_location = f"""        # {module.capitalize()} module endpoints
        location /api/v1/{module}/ {{
            proxy_pass http://{server_name}_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }}"""
            locations.append(module_location)

    return "\n\n".join(locations)


def generate_websocket_location_block(config: DeploymentConfig) -> str:
    """Generate nginx location block for WebSocket routing.

    For query parameter routing, we route based on the 'type' query parameter
    which is extracted from the WebSocket upgrade request.

    For path-based routing, we route based on the module path in the URL
    (e.g., /api/v1/broker/ws, /api/v1/datafeed/ws).

    Args:
        config: Deployment configuration

    Returns:
        Nginx WebSocket location configuration
    """
    if config.websocket.routing_strategy == "query_param":
        # Build map directive for WebSocket routing
        route_mappings = []
        for route, server_name in config.websocket_routes.items():
            route_mappings.append(f'        "~^{route}" {server_name}_backend;')

        # Default to core if no match
        route_mappings.append("        default core_backend;")

        map_block = f"""    # Map WebSocket route to upstream server
    map $arg_{config.websocket.query_param_name} $ws_backend {{
{chr(10).join(route_mappings)}
    }}"""

        location_block = """        # WebSocket endpoint with query param routing
        location /api/v1/ws {
            proxy_pass http://$ws_backend;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_read_timeout 3600s;
            proxy_send_timeout 3600s;
        }"""

        return map_block + "\n\n" + location_block
    else:
        # Path-based routing: /api/v1/{module}/ws -> {server}_backend
        locations = []
        for module, server_name in config.websocket_routes.items():
            location = f"""        # WebSocket route: {module} module
        location /api/v1/{module}/ws {{
            proxy_pass http://{server_name}_backend;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_read_timeout 3600s;
            proxy_send_timeout 3600s;
        }}"""
            locations.append(location)

        return "\n\n".join(locations)


def generate_nginx_config(config: DeploymentConfig, output_file: TextIO) -> None:
    """Generate complete nginx configuration.

    Args:
        config: Deployment configuration
        output_file: Output file handle
    """
    # Generate all configuration sections
    upstreams = generate_upstream_blocks(config)
    rest_locations = generate_rest_location_blocks(config)

    # WebSocket routing includes map directive if using query params
    ws_config = generate_websocket_location_block(config)
    if config.websocket.routing_strategy == "query_param":
        ws_map, ws_location = ws_config.split("\n\n", 1)
    else:
        ws_map = ""
        ws_location = ws_config

    # Worker processes configuration
    worker_processes = (
        config.nginx.worker_processes
        if isinstance(config.nginx.worker_processes, str)
        else str(config.nginx.worker_processes)
    )

    # Use local log paths for development
    backend_dir = Path(__file__).parent.parent
    log_dir = backend_dir / ".local" / "logs"
    access_log = log_dir / "nginx-access.log"
    error_log = log_dir / "nginx-error.log"

    # PID file path
    pid_file = backend_dir / "nginx.pid"

    # Generate complete configuration
    nginx_config = f"""# Auto-generated nginx configuration for multi-process backend
# Generated from deployment configuration
# DO NOT EDIT MANUALLY - regenerate using backend-manager gen-nginx-conf

pid {pid_file};
worker_processes {worker_processes};

events {{
    worker_connections {config.nginx.worker_connections};
}}

http {{
    # Upstream server definitions
{upstreams}

{ws_map if ws_map else ""}

    # Main server block
    server {{
        listen {config.nginx.port};
        server_name localhost;

        # Access and error logs (local paths for development)
        access_log {access_log};
        error_log {error_log};

        # REST API routing
{rest_locations}

{ws_location}

        # Root location (redirect to docs)
        location = / {{
            return 302 /api/v1/docs;
        }}
    }}
}}
"""

    output_file.write(nginx_config)


def validate_nginx_config(config_path: Path) -> bool:
    """Validate nginx configuration.

    Args:
        config_path: Path to nginx configuration file

    Returns:
        True if valid, False otherwise
    """
    # Ensure log directory exists
    log_dir = Path(__file__).parent.parent / ".local" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    # Check for local nginx binary first
    local_nginx = Path(__file__).parent.parent / ".local" / "bin" / "nginx"
    nginx_cmd = str(local_nginx) if local_nginx.exists() else "nginx"

    try:
        abs_config_path = config_path.resolve()
        result = subprocess.run(
            [nginx_cmd, "-t", "-c", str(abs_config_path)],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            logger.info(f"✅ Nginx configuration is valid: {abs_config_path}")
            logger.info(result.stderr.strip())
            return True
        else:
            logger.error(f"❌ Nginx configuration validation failed")
            logger.error(result.stderr.strip())
            return False

    except FileNotFoundError:
        logger.error("❌ nginx command not found!")
        logger.error("Install options:")
        logger.error("  1. Standalone (no sudo): make install-nginx")
        logger.error("  2. System package: sudo apt install nginx")
        return False


# ============================================================================
# Command Implementations
# ============================================================================


async def cmd_start(args: argparse.Namespace) -> int:
    """Start multi-process backend.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # Load deployment configuration
    try:
        config = load_config(args.config)
        logger.info(f"Loaded configuration from {args.config}")
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        return 1

    # Determine nginx config path
    nginx_config_path = args.nginx_config
    if not nginx_config_path:
        nginx_config_path = Path("nginx-dev.conf")

    # Generate nginx config if it doesn't exist or if requested
    if args.generate_nginx or not nginx_config_path.exists():
        logger.info("Generating nginx configuration...")
        try:
            with open(nginx_config_path, "w") as f:
                generate_nginx_config(config, f)
            logger.info(f"Generated nginx config: {nginx_config_path}")
        except Exception as e:
            logger.error(f"Failed to generate nginx config: {e}")
            return 1

    # Verify nginx config exists
    if not nginx_config_path.exists():
        logger.error(f"Nginx config not found: {nginx_config_path}")
        logger.error("Run with --generate-nginx to create it")
        return 1

    # Validate nginx config if requested
    if args.validate:
        if not validate_nginx_config(nginx_config_path):
            return 1

    # Create and run server manager (detached mode by default)
    detached = not args.foreground  # Detached unless --foreground is specified
    manager = ServerManager(config, nginx_config_path, detached=detached)

    logger.info("=" * 60)
    logger.info("Starting multi-process backend...")
    logger.info("=" * 60)
    logger.info(f"Nginx gateway: http://127.0.0.1:{config.nginx.port}")
    logger.info("Backend servers:")

    for server_name, server_config in config.servers.items():
        modules_str = (
            ", ".join(server_config.modules) if server_config.modules else "core only"
        )
        for instance_idx in range(server_config.instances):
            port = server_config.port + instance_idx
            logger.info(
                f"  {server_name}-{instance_idx}: "
                f"http://127.0.0.1:{port} ({modules_str})"
            )

    logger.info("=" * 60)

    return await manager.run()


async def cmd_stop(args: argparse.Namespace) -> int:
    """Stop running backend processes.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # Load deployment configuration
    try:
        config = load_config(args.config)
        logger.info(f"Loaded configuration from {args.config}")
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        return 1

    # Determine nginx config path
    nginx_config_path = args.nginx_config
    if not nginx_config_path:
        nginx_config_path = Path("nginx-dev.conf")

    # Create server manager (without starting)
    manager = ServerManager(config, nginx_config_path)

    logger.info("Stopping backend processes...")

    # Use stop_all_by_pid to stop processes tracked by PID files
    await manager.stop_all_by_pid(timeout=args.timeout)

    return 0


async def cmd_status(args: argparse.Namespace) -> int:
    """Show status of running backend processes.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # Load deployment configuration
    try:
        config = load_config(args.config)
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        return 1

    # Determine nginx config path
    nginx_config_path = args.nginx_config
    if not nginx_config_path:
        nginx_config_path = Path("nginx-dev.conf")

    # Create server manager (without starting)
    manager = ServerManager(config, nginx_config_path)

    # Get and display status
    status = await manager.get_status()

    logger.info("=" * 60)
    logger.info("Backend Status")
    logger.info("=" * 60)

    if not status["running"]:
        logger.info("Status: STOPPED")
        logger.info("=" * 60)
        return 0

    logger.info("Status: RUNNING")
    logger.info("")

    # Display nginx status
    nginx_info = status["nginx"]
    if nginx_info["running"]:
        logger.info(f"Nginx Gateway: http://127.0.0.1:{nginx_info['port']}")
        logger.info(f"  PID: {nginx_info['pid']}")
        logger.info(
            f"  Status: {'✅ Healthy' if nginx_info['healthy'] else '❌ Unhealthy'}"
        )
    else:
        logger.info("Nginx Gateway: NOT RUNNING")

    logger.info("")
    logger.info("Backend Servers:")

    # Display server statuses
    for server_name, instances in status["servers"].items():
        for instance_info in instances:
            instance_name = instance_info["name"]
            if instance_info["running"]:
                logger.info(
                    f"  {instance_name}: http://127.0.0.1:{instance_info['port']}"
                )
                logger.info(f"    PID: {instance_info['pid']}")
                logger.info(
                    f"    Status: {'✅ Healthy' if instance_info['healthy'] else '❌ Unhealthy'}"
                )
                modules = instance_info.get("modules", [])
                modules_str = ", ".join(modules) if modules else "core only"
                logger.info(f"    Modules: {modules_str}")
            else:
                logger.info(f"  {instance_name}: NOT RUNNING")

    logger.info("=" * 60)

    return 0


async def cmd_restart(args: argparse.Namespace) -> int:
    """Restart backend processes.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    logger.info("Restarting backend...")

    # Stop first
    stop_result = await cmd_stop(args)
    if stop_result != 0:
        logger.error("Failed to stop backend")
        return 1

    # Port release wait is now handled in stop_all_by_pid()
    # No manual sleep needed

    # Start
    start_result = await cmd_start(args)
    if start_result != 0:
        logger.error("Failed to start backend")
        return 1

    logger.info("Backend restarted successfully")
    return 0


def cmd_gen_nginx_conf(args: argparse.Namespace) -> int:
    """Generate nginx configuration (debug command).

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # Load deployment configuration
    try:
        config = load_config(args.config)
        logger.info(f"Loaded configuration from {args.config}")
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        return 1

    # Generate nginx configuration
    try:
        with open(args.output, "w") as f:
            generate_nginx_config(config, f)
        logger.info(f"✅ Generated nginx configuration: {args.output}")
    except Exception as e:
        logger.error(f"❌ Failed to generate nginx configuration: {e}")
        return 1

    # Validate if requested
    if args.validate:
        if not validate_nginx_config(args.output):
            return 1

    return 0


# ============================================================================
# CLI Setup
# ============================================================================


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser with subcommands.

    Returns:
        Configured argument parser
    """
    parser = argparse.ArgumentParser(
        description="Backend Manager - Multi-process backend control",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s start                          Start backend with dev-config.yaml
  %(prog)s start prod-config.yaml         Start with custom config
  %(prog)s stop                           Stop all running processes
  %(prog)s status                         Show process status
  %(prog)s restart                        Restart all processes
  %(prog)s gen-nginx-conf                 Generate nginx config (debug)
        """,
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Start command
    start_parser = subparsers.add_parser(
        "start",
        help="Start multi-process backend",
    )
    start_parser.add_argument(
        "config",
        type=Path,
        nargs="?",
        default=Path("dev-config.yaml"),
        help="Deployment configuration file (default: dev-config.yaml)",
    )
    start_parser.add_argument(
        "--nginx-config",
        type=Path,
        help="Nginx configuration file (default: nginx-dev.conf)",
    )
    start_parser.add_argument(
        "--generate-nginx",
        action="store_true",
        help="Force regenerate nginx config",
    )
    start_parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate nginx config before starting",
    )
    start_parser.add_argument(
        "--foreground",
        action="store_true",
        help="Run in foreground (default: run detached in background)",
    )

    # Stop command
    stop_parser = subparsers.add_parser(
        "stop",
        help="Stop all running backend processes",
    )
    stop_parser.add_argument(
        "config",
        type=Path,
        nargs="?",
        default=Path("dev-config.yaml"),
        help="Deployment configuration file (default: dev-config.yaml)",
    )
    stop_parser.add_argument(
        "--nginx-config",
        type=Path,
        help="Nginx configuration file (default: nginx-dev.conf)",
    )
    stop_parser.add_argument(
        "--timeout",
        type=float,
        default=3.0,
        help="Shutdown timeout in seconds (default: 3)",
    )

    # Status command
    status_parser = subparsers.add_parser(
        "status",
        help="Show status of backend processes",
    )
    status_parser.add_argument(
        "config",
        type=Path,
        nargs="?",
        default=Path("dev-config.yaml"),
        help="Deployment configuration file (default: dev-config.yaml)",
    )
    status_parser.add_argument(
        "--nginx-config",
        type=Path,
        help="Nginx configuration file (default: nginx-dev.conf)",
    )

    # Restart command
    restart_parser = subparsers.add_parser(
        "restart",
        help="Restart all backend processes",
    )
    restart_parser.add_argument(
        "config",
        type=Path,
        nargs="?",
        default=Path("dev-config.yaml"),
        help="Deployment configuration file (default: dev-config.yaml)",
    )
    restart_parser.add_argument(
        "--nginx-config",
        type=Path,
        help="Nginx configuration file (default: nginx-dev.conf)",
    )
    restart_parser.add_argument(
        "--timeout",
        type=float,
        default=3.0,
        help="Shutdown timeout in seconds (default: 3)",
    )
    restart_parser.add_argument(
        "--generate-nginx",
        action="store_true",
        help="Force regenerate nginx config",
    )
    restart_parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate nginx config before starting",
    )
    restart_parser.add_argument(
        "--foreground",
        action="store_true",
        help="Run in foreground (default: run detached in background)",
    )

    # Gen-nginx-conf command (debug)
    gen_nginx_parser = subparsers.add_parser(
        "gen-nginx-conf",
        help="Generate nginx configuration (debug)",
    )
    gen_nginx_parser.add_argument(
        "config",
        type=Path,
        nargs="?",
        default=Path("dev-config.yaml"),
        help="Deployment configuration file (default: dev-config.yaml)",
    )
    gen_nginx_parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("nginx-dev.conf"),
        help="Output nginx configuration file (default: nginx-dev.conf)",
    )
    gen_nginx_parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate generated configuration",
    )

    return parser


async def async_main() -> int:
    """Async main entry point.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    parser = create_parser()
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Dispatch to command handler
    if args.command == "start":
        return await cmd_start(args)
    elif args.command == "stop":
        return await cmd_stop(args)
    elif args.command == "status":
        return await cmd_status(args)
    elif args.command == "restart":
        return await cmd_restart(args)
    elif args.command == "gen-nginx-conf":
        return cmd_gen_nginx_conf(args)
    else:
        parser.print_help()
        return 1


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        return asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
