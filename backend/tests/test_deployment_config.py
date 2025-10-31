"""Tests for deployment configuration schema."""

import tempfile
from pathlib import Path

import pytest
import yaml

from trading_api.shared.deployment import (
    DeploymentConfig,
    NginxConfig,
    ServerConfig,
    WebSocketConfig,
    load_config,
)


class TestNginxConfig:
    """Tests for NginxConfig model."""

    def test_valid_config(self) -> None:
        """Test valid nginx configuration."""
        config = NginxConfig(port=8000, worker_processes=1, worker_connections=1024)

        assert config.port == 8000
        assert config.worker_processes == 1
        assert config.worker_connections == 1024

    def test_auto_worker_processes(self) -> None:
        """Test 'auto' worker_processes value."""
        config = NginxConfig(
            port=8000, worker_processes="auto", worker_connections=1024
        )

        assert config.worker_processes == "auto"

    def test_invalid_port_too_low(self) -> None:
        """Test port validation (too low)."""
        with pytest.raises(ValueError, match="Port must be between 1024 and 65535"):
            NginxConfig(port=1023, worker_processes=1)

    def test_invalid_port_too_high(self) -> None:
        """Test port validation (too high)."""
        with pytest.raises(ValueError, match="Port must be between 1024 and 65535"):
            NginxConfig(port=65536, worker_processes=1)

    def test_invalid_worker_processes(self) -> None:
        """Test worker_processes validation."""
        with pytest.raises(
            ValueError, match="worker_processes must be 'auto' or a positive integer"
        ):
            NginxConfig(port=8000, worker_processes="invalid")

    def test_negative_worker_processes(self) -> None:
        """Test negative worker_processes."""
        with pytest.raises(ValueError, match="worker_processes must be at least 1"):
            NginxConfig(port=8000, worker_processes=0)


class TestServerConfig:
    """Tests for ServerConfig model."""

    def test_valid_config(self) -> None:
        """Test valid server configuration."""
        config = ServerConfig(port=8001, instances=2, modules=["broker"], reload=True)

        assert config.port == 8001
        assert config.instances == 2
        assert config.modules == ["broker"]
        assert config.reload is True

    def test_default_values(self) -> None:
        """Test default values."""
        config = ServerConfig(port=8001)

        assert config.instances == 1
        assert config.modules == []
        assert config.reload is True

    def test_invalid_port(self) -> None:
        """Test port validation."""
        with pytest.raises(ValueError, match="Port must be between 1024 and 65535"):
            ServerConfig(port=500)

    def test_invalid_instances(self) -> None:
        """Test instances validation."""
        with pytest.raises(ValueError, match="instances must be at least 1"):
            ServerConfig(port=8001, instances=0)


class TestWebSocketConfig:
    """Tests for WebSocketConfig model."""

    def test_valid_config_query_param(self) -> None:
        """Test valid query param configuration."""
        config = WebSocketConfig(
            routing_strategy="query_param", query_param_name="type"
        )

        assert config.routing_strategy == "query_param"
        assert config.query_param_name == "type"

    def test_valid_config_path(self) -> None:
        """Test valid path-based configuration."""
        config = WebSocketConfig(routing_strategy="path")

        assert config.routing_strategy == "path"

    def test_default_values(self) -> None:
        """Test default values."""
        config = WebSocketConfig()

        assert config.routing_strategy == "query_param"
        assert config.query_param_name == "type"

    def test_invalid_routing_strategy(self) -> None:
        """Test routing strategy validation."""
        with pytest.raises(
            ValueError, match="routing_strategy must be 'query_param' or 'path'"
        ):
            WebSocketConfig(routing_strategy="invalid")


class TestDeploymentConfig:
    """Tests for DeploymentConfig model."""

    def test_valid_config(self) -> None:
        """Test valid deployment configuration."""
        config = DeploymentConfig(
            nginx=NginxConfig(port=8000),
            servers={
                "core": ServerConfig(port=8003, modules=[]),
                "broker": ServerConfig(port=8001, modules=["broker"]),
                "datafeed": ServerConfig(port=8002, modules=["datafeed"]),
            },
            websocket=WebSocketConfig(),
            websocket_routes={
                "orders": "broker",
                "positions": "broker",
                "bars": "datafeed",
            },
        )

        assert config.nginx.port == 8000
        assert len(config.servers) == 3
        assert "core" in config.servers
        assert "broker" in config.servers
        assert "datafeed" in config.servers
        assert config.websocket_routes["orders"] == "broker"
        assert config.websocket_routes["bars"] == "datafeed"

    def test_port_conflict_nginx_server(self) -> None:
        """Test port conflict between nginx and server."""
        with pytest.raises(ValueError, match="Port conflict.*8000.*nginx.*broker"):
            DeploymentConfig(
                nginx=NginxConfig(port=8000),
                servers={
                    "broker": ServerConfig(port=8000, modules=["broker"]),
                },
            )

    def test_port_conflict_between_servers(self) -> None:
        """Test port conflict between two servers."""
        with pytest.raises(ValueError, match="Port conflict.*8001"):
            DeploymentConfig(
                nginx=NginxConfig(port=8000),
                servers={
                    "broker": ServerConfig(port=8001, modules=["broker"]),
                    "datafeed": ServerConfig(port=8001, modules=["datafeed"]),
                },
            )

    def test_port_conflict_with_instance_ports(self) -> None:
        """Test port conflict with multi-instance server."""
        with pytest.raises(ValueError, match="Port conflict.*8002"):
            DeploymentConfig(
                nginx=NginxConfig(port=8000),
                servers={
                    "broker": ServerConfig(
                        port=8001, instances=2, modules=["broker"]
                    ),  # Uses 8001, 8002
                    "datafeed": ServerConfig(
                        port=8002, modules=["datafeed"]
                    ),  # Conflicts with broker-1
                },
            )

    def test_core_server_must_have_no_modules(self) -> None:
        """Test core server validation (must have empty modules)."""
        with pytest.raises(
            ValueError, match="Core server must have no modules, found: \\['broker'\\]"
        ):
            DeploymentConfig(
                nginx=NginxConfig(port=8000),
                servers={
                    "core": ServerConfig(port=8003, modules=["broker"]),
                },
            )

    def test_websocket_route_unknown_server(self) -> None:
        """Test WebSocket route validation (unknown server)."""
        with pytest.raises(
            ValueError,
            match="WebSocket route 'orders' references unknown server 'unknown'",
        ):
            DeploymentConfig(
                nginx=NginxConfig(port=8000),
                servers={
                    "broker": ServerConfig(port=8001, modules=["broker"]),
                },
                websocket_routes={
                    "orders": "unknown",
                },
            )

    def test_get_all_ports(self) -> None:
        """Test get_all_ports method."""
        config = DeploymentConfig(
            nginx=NginxConfig(port=8000),
            servers={
                "core": ServerConfig(port=8003, modules=[]),
                "broker": ServerConfig(port=8001, instances=2, modules=["broker"]),
            },
        )

        ports = config.get_all_ports()

        assert ("nginx", 8000) in ports
        assert ("core-0", 8003) in ports
        assert ("broker-0", 8001) in ports
        assert ("broker-1", 8002) in ports
        assert len(ports) == 4


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_valid_config(self) -> None:
        """Test loading valid configuration from YAML."""
        config_data = {
            "nginx": {"port": 8000, "worker_processes": 1},
            "servers": {
                "core": {"port": 8003, "modules": []},
                "broker": {"port": 8001, "modules": ["broker"]},
            },
            "websocket": {"routing_strategy": "query_param"},
            "websocket_routes": {"orders": "broker"},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            config_path = Path(f.name)

        try:
            config = load_config(config_path)

            assert config.nginx.port == 8000
            assert "core" in config.servers
            assert "broker" in config.servers
            assert config.websocket_routes["orders"] == "broker"
        finally:
            config_path.unlink()

    def test_load_config_file_not_found(self) -> None:
        """Test loading from non-existent file."""
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            load_config("/nonexistent/path/config.yaml")

    def test_load_invalid_config(self) -> None:
        """Test loading invalid configuration."""
        config_data = {
            "nginx": {"port": 8000},
            "servers": {
                "broker": {"port": 8000},  # Port conflict with nginx
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            config_path = Path(f.name)

        try:
            with pytest.raises(ValueError, match="Port conflict"):
                load_config(config_path)
        finally:
            config_path.unlink()

    def test_load_real_dev_config(self) -> None:
        """Test loading the actual dev-config.yaml file."""
        # This test assumes dev-config.yaml exists in backend/
        dev_config_path = Path(__file__).parent.parent / "dev-config.yaml"

        if not dev_config_path.exists():
            pytest.skip("dev-config.yaml not found")

        config = load_config(dev_config_path)

        # Validate structure matches expectations
        assert config.nginx.port == 8000
        assert "core" in config.servers
        assert "broker" in config.servers
        assert "datafeed" in config.servers

        # Validate no port conflicts
        ports = config.get_all_ports()
        port_numbers = [p[1] for p in ports]
        assert len(port_numbers) == len(set(port_numbers))  # No duplicates

        # Validate core server has no modules
        assert config.servers["core"].modules == []
