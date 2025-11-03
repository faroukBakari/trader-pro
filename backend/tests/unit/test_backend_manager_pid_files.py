"""Unit tests for backend_manager.py PID file management functionality.

These tests validate PID file operations used for process tracking in
detached mode. They use temporary directories and don't start real processes.

Test Coverage:
- _write_pid_file() - Write PID to file for process tracking
- _read_pid_file() - Read PID from file
- _is_process_running() - Check if a process is running by PID
"""

import os
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from scripts.backend_manager import ServerManager
from trading_api.shared.deployment import (
    DeploymentConfig,
    NginxConfig,
    ServerConfig,
    WebSocketConfig,
)


@pytest.mark.unit
class TestPidFileManagement:
    """Unit tests for PID file operations."""

    @pytest.fixture
    def temp_dir(self) -> Generator[Path, None, None]:
        """Create temporary directory for PID files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def manager(self, temp_dir: Path) -> ServerManager:
        """Create ServerManager with temporary directories."""
        config = DeploymentConfig(
            nginx=NginxConfig(port=18000, worker_processes=1, worker_connections=1024),
            servers={
                "broker": ServerConfig(
                    port=18001, instances=1, modules=["broker"], reload=True
                ),
            },
            websocket=WebSocketConfig(routing_strategy="path", query_param_name="type"),
            websocket_routes={"broker": "broker"},
        )

        manager = ServerManager(config)

        # Override directories to use temp_dir for isolated testing
        manager.pid_dir = temp_dir / ".pids"
        manager.log_dir = temp_dir / ".logs"
        manager.nginx_config_path = temp_dir / "nginx.conf"
        manager.nginx_pid_file = temp_dir / "nginx.pid"
        manager.pid_dir.mkdir(parents=True, exist_ok=True)
        manager.log_dir.mkdir(parents=True, exist_ok=True)

        return manager

    def test_write_pid_file(self, manager: ServerManager) -> None:
        """Test writing PID to file."""
        instance_name = "broker-0"
        pid = 12345

        manager._write_pid_file(instance_name, pid)

        pid_file = manager.pid_dir / f"{instance_name}.pid"
        assert pid_file.exists()
        assert pid_file.read_text().strip() == str(pid)

    def test_read_pid_file(self, manager: ServerManager) -> None:
        """Test reading PID from file."""
        instance_name = "broker-0"
        expected_pid = 12345

        manager._write_pid_file(instance_name, expected_pid)
        actual_pid = manager._read_pid_file(instance_name)

        assert actual_pid == expected_pid

    def test_read_nonexistent_pid_file(self, manager: ServerManager) -> None:
        """Test reading PID from non-existent file returns None."""
        pid = manager._read_pid_file("nonexistent-0")
        assert pid is None

    def test_read_invalid_pid_file(
        self, manager: ServerManager, temp_dir: Path
    ) -> None:
        """Test reading invalid PID file returns None."""
        instance_name = "invalid-0"
        pid_file = manager.pid_dir / f"{instance_name}.pid"

        # Write invalid content
        pid_file.write_text("not-a-number")

        pid = manager._read_pid_file(instance_name)
        assert pid is None

    def test_is_process_running_with_current_process(
        self, manager: ServerManager
    ) -> None:
        """Test checking if current process is running."""
        current_pid = os.getpid()
        assert manager._is_process_running(current_pid)

    def test_is_process_running_with_invalid_pid(self, manager: ServerManager) -> None:
        """Test checking invalid PID returns False."""
        # PID 999999 is unlikely to exist
        assert not manager._is_process_running(999999)
