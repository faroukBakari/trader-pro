"""Multi-process server manager for backend deployment.

Orchestrates multiple uvicorn server instances with nginx gateway.
Handles process lifecycle, health checks, and graceful shutdown.
"""

import asyncio
import io
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

from trading_api.shared.deployment.config_schema import DeploymentConfig

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
        self._log_threads: list[threading.Thread] = []

        # Ensure PID and log directories exist
        self.pid_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)

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

    def _stream_output_to_unified_log(
        self, stream: io.BufferedReader, prefix: str, unified_log: TextIO
    ) -> None:
        """Stream process output to unified log with prefix.

        Runs in a background thread to continuously read from stream
        and write to unified log with server name prefix.

        Args:
            stream: Process stdout or stderr stream
            prefix: Server name prefix (e.g., 'broker-0>>')
            unified_log: Unified log file handle
        """
        try:
            for line in iter(stream.readline, b""):
                if line:
                    decoded_line = line.decode("utf-8", errors="replace").rstrip()
                    log_entry = f"{prefix} {decoded_line}\n"
                    unified_log.write(log_entry)
                    unified_log.flush()
        except Exception as e:
            logger.error(f"Error streaming output for {prefix}: {e}")

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

        if self.detached:
            # Detached mode: redirect output to log file, run in background
            log_file_path = self.log_dir / f"{name}.log"
            log_file = open(log_file_path, "a")
            unified_log = open(self.unified_log_path, "a", buffering=1)

            process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                start_new_session=True,  # Detach from parent session
            )

            # Write PID file for process tracking
            self._write_pid_file(name, process.pid)

            # Start background thread to stream output to both logs
            # Format prefix: 20 chars total (truncate if >12, pad if <12, then add >>)
            prefix_name = name[:12] if len(name) > 12 else name
            prefix = f"{prefix_name:<12}>>"

            def stream_to_logs():
                try:
                    if process.stdout:
                        for line in iter(process.stdout.readline, b""):
                            if line:
                                decoded = line.decode(
                                    "utf-8", errors="replace"
                                ).rstrip()
                                # Write to individual log
                                log_file.write(f"{decoded}\n")
                                log_file.flush()
                                # Write to unified log with prefix
                                unified_log.write(f"{prefix} {decoded}\n")
                                unified_log.flush()
                except Exception as e:
                    logger.error(f"Error streaming output for {prefix}: {e}")
                finally:
                    log_file.close()
                    unified_log.close()

            log_thread = threading.Thread(target=stream_to_logs, daemon=True)
            log_thread.start()
            self._log_threads.append(log_thread)

        else:
            # Interactive mode: keep process attached
            process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )

            # Write PID file for process tracking
            self._write_pid_file(name, process.pid)

            # Start background thread to stream output to unified log
            # Format prefix: 20 chars total (truncate if >12, pad if <12, then add >>)
            prefix_name = name[:12] if len(name) > 12 else name
            prefix = f"{prefix_name:<12}>>"
            unified_log = open(self.unified_log_path, "a", buffering=1)

            log_thread = threading.Thread(
                target=self._stream_output_to_unified_log,
                args=(process.stdout, prefix, unified_log),
                daemon=True,
            )
            log_thread.start()
            self._log_threads.append(log_thread)

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

    async def _wait_for_ports_release(self, max_wait: float = 2.0) -> None:
        """Wait for all configured ports to be released.

        Args:
            max_wait: Maximum time to wait in seconds
        """
        start_time = time.time()
        all_ports = [port for _, port in self.config.get_all_ports()]

        while time.time() - start_time < max_wait:
            # Check if all ports are free
            ports_in_use = [port for port in all_ports if is_port_in_use(port)]

            if not ports_in_use:
                logger.debug("All ports released")
                return

            # Wait a bit before checking again
            await asyncio.sleep(0.1)

        # Log warning if some ports are still in use
        ports_in_use = [port for port in all_ports if is_port_in_use(port)]
        if ports_in_use:
            logger.warning(f"Ports still in use after {max_wait}s: {ports_in_use}")

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
            time.sleep(0.1)  # Brief wait for cleanup

        except (OSError, ProcessLookupError) as e:
            logger.warning(f"Error stopping {name}: {e}")

    async def start_all(self) -> bool:
        """Start all server instances and nginx gateway.

        Returns:
            True if all servers started successfully, False otherwise
        """
        logger.info("Starting multi-process backend...")

        # Initialize unified log file (truncate if exists)
        with open(self.unified_log_path, "w") as f:
            f.write(
                f"=== Backend Unified Log - Started at {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n"
            )

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
                logger.info(f"Unified log: {self.unified_log_path}")
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
