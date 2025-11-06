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
import time
from math import pi
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
    base_url: str, modules: list[str], max_attempts: int = 30, delay: float = 0.5
) -> bool:
    """Wait for all modules on a service to become healthy.

    Args:
        base_url: Base URL of the service
        modules: List of module names to check
        max_attempts: Maximum number of connection attempts
        delay: Delay between attempts in seconds

    Returns:
        True if all modules are healthy, False otherwise
    """
    async with httpx.AsyncClient() as client:
        for attempt in range(max_attempts):
            all_healthy = True

            for module in modules:
                try:
                    response = await client.get(
                        f"{base_url}/api/v1/{module}/health", timeout=2.0
                    )
                    if response.status_code != 200:
                        all_healthy = False
                        break
                except (
                    httpx.ConnectError,
                    httpx.RemoteProtocolError,
                    httpx.TimeoutException,
                ):
                    all_healthy = False
                    break
                except Exception as e:
                    logger.warning(
                        f"Unexpected error checking health for {module} at {base_url}: {e}"
                    )
                    all_healthy = False
                    break

            if all_healthy:
                logger.info(
                    f"All modules at {base_url} are healthy: {', '.join(modules)}"
                )
                return True

            if attempt < max_attempts - 1:
                await asyncio.sleep(delay)

    logger.error(
        f"Service at {base_url} failed to become healthy after {max_attempts} attempts"
    )
    return False


class ServerManager:
    """Manages multiple backend server processes and nginx gateway.

    Handles process lifecycle, health checks, and graceful shutdown.
    All processes run in detached background mode.
    """

    def __init__(self, config: DeploymentConfig):
        """Initialize server manager.

        Args:
            config: Deployment configuration
            nginx_config_path: Path to nginx configuration file (relative to working directory)
        """
        self.config = config

        self.local_dir = Path(".local")
        self.pid_dir = self.local_dir / "pids"
        self.log_dir = self.local_dir / "logs"

        self.nginx_config_path = self.local_dir / "nginx.conf"
        self.nginx_pid_file = self.local_dir / "nginx.pid"
        self.unified_log_path = self.log_dir / "backend-unified.log"

        self.processes: dict[str, subprocess.Popen[bytes]] = {}

        # Ensure PID and log directories exist
        self.pid_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        if not self.nginx_config_path.exists():
            logger.info("Generating nginx configuration...")
            try:
                with open(self.nginx_config_path, "w") as f:
                    generate_nginx_config(config, f, pid_file=self.nginx_pid_file)
                logger.info(f"Generated nginx config: {self.nginx_config_path}")
            except Exception as e:
                logger.error(f"Failed to generate nginx config: {e}")
        else:
            if not validate_nginx_config(self.nginx_config_path):
                raise ValueError("Invalid nginx configuration")

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
            modules: List of enabled modules (core is always added if not present)
            reload: Enable auto-reload

        Returns:
            Started process
        """
        env = os.environ.copy()

        env["ENABLED_MODULES"] = ",".join(modules)

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
                    "*/ws_generated/*",
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

        # Start process in detached mode
        # Let uvicorn handle all logging via log config
        process = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,  # Detach from parent session
        )

        # Write PID file for process tracking
        self._write_pid_file(name, process.pid)

        return process

    def _start_nginx(self) -> subprocess.Popen[bytes]:
        """Start nginx gateway.

        Returns:
            Started nginx process (may become invalid after nginx daemonizes)
        """
        nginx_binary = self._get_nginx_binary()

        cmd = [
            nginx_binary,
            "-c",
            str(self.nginx_config_path.absolute()),
        ]

        logger.info(f"Starting nginx on port {self.config.nginx.port}")

        # Start nginx in detached mode
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        # Wait for nginx to write its PID file (nginx daemonizes quickly)
        max_attempts = 20
        for _ in range(max_attempts):
            if self.nginx_pid_file.exists():
                logger.debug(f"Nginx PID file created: {self.nginx_pid_file}")
                break
            time.sleep(0.05)
        else:
            logger.warning("Nginx PID file not created within timeout")

        return process

    def _write_pid_file(self, instance_name: str, pid: int) -> None:
        pid_file = self.pid_dir / f"{instance_name}.pid"
        pid_file.write_text(str(pid))

    def _read_pid_file(self, instance_name: str) -> int | None:
        pid_file = self.pid_dir / f"{instance_name}.pid"
        try:
            return int(pid_file.read_text().strip())
        except (ValueError, OSError):
            return None

    def _is_process_running(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)  # Signal 0 just checks if process exists
            return True
        except (OSError, ProcessLookupError):
            return False

    async def _force_kill_port_holders(self, ports: list[int]) -> None:
        # Step 1: Try SIGTERM first (graceful)
        terminated_any = False

        try:
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
                                f"Sending SIGTERM to PID {pid} holding port {port}"
                            )
                            try:
                                os.kill(pid, signal.SIGTERM)
                                terminated_any = True
                            except (OSError, ProcessLookupError) as e:
                                logger.warning(f"Failed to terminate PID {pid}: {e}")

        except FileNotFoundError:
            logger.warning("lsof command not available, cannot identify port holders")
        except Exception as e:
            logger.warning(f"Error identifying port holders: {e}")

        if terminated_any:
            # Wait for graceful termination
            await asyncio.sleep(1.0)

            # Check which ports are still in use
            remaining_ports = [port for port in ports if is_port_in_use(port)]

            if not remaining_ports:
                logger.info("All ports freed after SIGTERM")
                return

            logger.warning(f"Some ports still in use after SIGTERM: {remaining_ports}")
            ports = remaining_ports

        # Step 2: Force kill with SIGKILL as last resort
        killed_any = False

        try:
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
                                f"Force killing (SIGKILL) PID {pid} holding port {port}"
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

    async def _check_module_health(
        self, port: int, modules: list[str]
    ) -> dict[str, Any]:
        """Check health of all modules on a server instance.

        Args:
            port: Server port
            modules: List of module names to check

        Returns:
            Dictionary with module health details:
            {
                "overall_healthy": bool,
                "modules": {
                    "module_name": {
                        "healthy": bool,
                        "url": str,
                        "api_version": str,
                        "response_time_ms": float,
                        "error": str  # Only if unhealthy
                    }
                }
            }
        """
        base_url = f"http://127.0.0.1:{port}"
        module_health: dict[str, Any] = {}
        all_healthy = True

        async with httpx.AsyncClient() as client:
            for module_name in modules:
                health_url = f"{base_url}/api/v1/{module_name}/health"

                try:
                    start_time = time.time()
                    response = await client.get(health_url, timeout=2.0)
                    response_time = (time.time() - start_time) * 1000

                    if response.status_code == 200:
                        data = response.json()
                        module_health[module_name] = {
                            "healthy": True,
                            "url": health_url,
                            "api_version": data.get("api_version", "unknown"),
                            "response_time_ms": round(response_time, 2),
                        }
                    else:
                        module_health[module_name] = {
                            "healthy": False,
                            "url": health_url,
                            "status_code": response.status_code,
                        }
                        all_healthy = False

                except Exception as e:
                    module_health[module_name] = {
                        "healthy": False,
                        "url": health_url,
                        "error": str(e),
                    }
                    all_healthy = False

        return {"overall_healthy": all_healthy, "modules": module_health}

    async def _wait_for_ports_release(
        self, max_wait: float = 2.0, max_retries: int = 3
    ) -> None:
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

    def _stop_process(self, pid: int, name: str, timeout: float) -> None:
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
                time.sleep(0.1)  # Check more frequently

            # Force kill if timeout exceeded
            logger.warning(f"{name} did not stop gracefully, force killing")
            os.kill(pid, signal.SIGKILL)
            time.sleep(0.2)  # Wait for OS to clean up resources

        except (OSError, ProcessLookupError) as e:
            logger.warning(f"Error stopping {name}: {e}")

    def _stop_nginx(self, timeout: float) -> None:
        # Always try nginx PID file first (nginx daemonizes, so Popen object is unreliable)
        if self.nginx_pid_file.exists():
            with open(self.nginx_pid_file, "r") as f:
                nginx_pid = int(f.read().strip())

            logger.info(f"Stopping nginx using PID file (PID: {nginx_pid})...")

            # Send QUIT signal for graceful shutdown
            os.kill(nginx_pid, signal.SIGQUIT)

            start_time = time.time()
            while time.time() - start_time < timeout:
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
            os.kill(nginx_pid, signal.SIGKILL)
            time.sleep(0.1)  # Brief wait for cleanup
            if self.nginx_pid_file.exists():
                self.nginx_pid_file.unlink()
            logger.info("nginx force killed")
        else:
            raise RuntimeError("Nginx PID file not found, cannot stop nginx")

    async def start_all(self) -> bool:
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

                healthy = await wait_for_health(base_url, modules=server_config.modules)
                if not healthy:
                    logger.error(f"{instance_name} failed to become healthy")
                    all_healthy = False

        if not all_healthy:
            logger.error("Not all servers became healthy - shutting down")
            await self.stop_all()
            return False

        # Start nginx
        try:
            self._start_nginx()
            logger.info("Nginx started successfully")
        except Exception as e:
            logger.error(f"Failed to start nginx: {e}")
            await self.stop_all()
            return False

        # Wait for nginx to become healthy
        # Check nginx by probing first available module through it
        nginx_url = f"http://127.0.0.1:{self.config.nginx.port}"
        # Get first server's modules for nginx health check
        first_server_modules = next(iter(self.config.servers.values())).modules
        nginx_healthy = await wait_for_health(
            nginx_url, modules=first_server_modules[:1]
        )  # Check just first module

        if not nginx_healthy:
            logger.error("Nginx failed to become healthy - shutting down")
            await self.stop_all()
            return False

        logger.info("All servers started successfully!")
        logger.info(f"Backend available at: {nginx_url}")
        return True

    async def stop_all(self, timeout: float = 10.0) -> None:
        logger.info("Stopping backend processes using PID files...")

        # Step 1: Stop nginx
        if self.nginx_pid_file.exists():
            try:
                nginx_pid = int(self.nginx_pid_file.read_text().strip())
                if self._is_process_running(nginx_pid):
                    logger.info(f"Stopping nginx (PID: {nginx_pid})...")
                    self._stop_process(nginx_pid, "nginx", timeout)
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
                    self._stop_process(pid, instance_name, timeout)

        logger.info("All processes stopped")

        # Wait for ports to be released
        await self._wait_for_ports_release()

    async def get_status(self) -> dict[str, Any]:
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
                    # Check nginx health by probing through it to first server's first module
                    first_server_modules = next(
                        iter(self.config.servers.values())
                    ).modules
                    nginx_health = await self._check_module_health(
                        nginx_port, first_server_modules[:1]
                    )
                    status["nginx"] = {
                        "running": True,
                        "pid": nginx_pid,
                        "port": nginx_port,
                        "healthy": nginx_health["overall_healthy"],
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

                instance_info: dict[str, Any] = {
                    "name": instance_name,
                    "port": port,
                    "configured_modules": server_config.modules,
                    "running": False,
                    "pid": None,
                    "overall_healthy": False,
                    "module_health": {},
                }

                if pid and self._is_process_running(pid):
                    instance_info["running"] = True
                    instance_info["pid"] = pid

                    # Check health of all modules
                    health_result = await self._check_module_health(
                        port, server_config.modules
                    )
                    instance_info["overall_healthy"] = health_result["overall_healthy"]
                    instance_info["module_health"] = health_result["modules"]

                    status["running"] = True

                server_instances.append(instance_info)

            status["servers"][server_name] = server_instances

        return status

    async def run(self) -> int:
        """Run the multi-process backend in detached mode.

        Returns:
            Exit code (0 for success, 1 for failure)
        """
        try:
            # Start all servers
            success = await self.start_all()
            if not success:
                return 1

            # Return immediately after servers start (detached mode)
            logger.info("All servers running in background (detached mode)")
            logger.info(f"Server logs: {self.log_dir}/*.log")
            logger.info(f"Tail logs: make logs-tail")
            logger.info(f"Stop servers: make backend-manager-stop")
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

    All servers host the core module automatically (provides health checks,
    version info, and docs). Each server also hosts its configured modules.

    Routing strategy: Simple prefix matching by module name.
    - {api_base_url}/core/* routes to first available server (all have core)
    - {api_base_url}/{module}/* routes to server hosting that module

    Args:
        config: Deployment configuration

    Returns:
        Nginx location configuration blocks
    """
    locations = []
    processed_modules = set()

    # Route each server's modules
    for server_name, server_config in config.servers.items():
        for module in server_config.modules:
            # Skip if we've already routed this module
            if module in processed_modules:
                continue

            processed_modules.add(module)

            module_location = f"""        # {module.capitalize()} module endpoints
        location {config.api_base_url}/{module}/ {{
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

        location_block = f"""        # WebSocket endpoint with query param routing
        location {config.api_base_url}/ws {{
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
        }}"""

        return map_block + "\n\n" + location_block
    else:
        # Path-based routing: /api/v1/{module}/ws -> {server}_backend
        locations = []
        for module, server_name in config.websocket_routes.items():
            location = f"""        # WebSocket route: {module} module
        location {config.api_base_url}/{module}/ws {{
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


def generate_nginx_config(
    config: DeploymentConfig, output_file: TextIO, pid_file: Path | None = None
) -> None:
    """Generate complete nginx configuration.

    Args:
        config: Deployment configuration
        output_file: Output file handle
        pid_file: Optional custom PID file path (defaults to backend_dir/nginx.pid)
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
    local_dir = backend_dir / ".local"
    log_dir = local_dir / "logs"
    access_log = log_dir / "nginx-access.log"
    error_log = log_dir / "nginx-error.log"

    # PID file path (use custom or default)
    if pid_file is None:
        pid_file = local_dir / "nginx.pid"

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
            return 302 {config.api_base_url}/core/docs;
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

    # Create and run server manager (always runs in detached mode)
    # The ServerManager handles nginx config generation internally
    manager = ServerManager(config)

    logger.info("=" * 60)
    logger.info("Starting multi-process backend (detached mode)...")
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

    # Create server manager (without starting)
    manager = ServerManager(config)

    logger.info("Stopping backend processes...")

    # Use stop_all_by_pid to stop processes tracked by PID files
    await manager.stop_all(timeout=args.timeout)

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

    # Create server manager (without starting)
    manager = ServerManager(config)

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

                # Overall health status
                overall_status = (
                    "✅ Healthy" if instance_info["overall_healthy"] else "❌ Unhealthy"
                )
                logger.info(f"    Overall: {overall_status}")

                # Module-level health details
                logger.info("    Modules:")
                for module_name, module_health in instance_info[
                    "module_health"
                ].items():
                    if module_health["healthy"]:
                        version = module_health.get("api_version", "unknown")
                        response_time = module_health.get("response_time_ms", 0)
                        logger.info(
                            f"      - {module_name}: ✅ Healthy (v{version}, {response_time}ms)"
                        )
                    else:
                        error_msg = module_health.get("error", "")
                        status_code = module_health.get("status_code", "")
                        detail = (
                            f"error: {error_msg}"
                            if error_msg
                            else f"status: {status_code}"
                        )
                        logger.info(f"      - {module_name}: ❌ Unhealthy ({detail})")
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
        "--generate-nginx",
        action="store_true",
        help="Force regenerate nginx config",
    )
    start_parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate nginx config before starting",
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
