"""Unit tests for backend_manager.py configuration loading and validation.

These tests validate configuration loading from YAML files and
configuration helper methods. They don't start real processes.

Test Coverage:
- load_config() - Load deployment configuration from YAML
- DeploymentConfig.get_all_ports() - Extract all ports from config
"""

from pathlib import Path

import pytest

from trading_api.shared.deployment import (
    DeploymentConfig,
    NginxConfig,
    ServerConfig,
    WebSocketConfig,
    load_config,
)


@pytest.mark.unit
class TestConfigurationValidation:
    """Test configuration loading and validation."""

    def test_load_dev_config(self) -> None:
        """Test loading dev-config.yaml."""
        # Config is in backend directory
        config_path = Path(__file__).parent.parent.parent / "dev-config.yaml"
        config = load_config(str(config_path))

        assert config.nginx.port > 0
        assert len(config.servers) > 0
        assert config.websocket.routing_strategy in ["path", "query_param"]

    def test_config_get_all_ports(self) -> None:
        """Test getting all ports from configuration."""
        config = DeploymentConfig(
            nginx=NginxConfig(port=8000, worker_processes=1, worker_connections=1024),
            servers={
                "broker": ServerConfig(
                    port=8001, instances=2, modules=["broker"], reload=True
                ),
                "datafeed": ServerConfig(
                    port=8003, instances=1, modules=["datafeed"], reload=True
                ),
            },
            websocket=WebSocketConfig(routing_strategy="path", query_param_name="type"),
            websocket_routes={"broker": "broker", "datafeed": "datafeed"},
        )

        ports = config.get_all_ports()

        # Should have: nginx (8000), broker-0 (8001), broker-1 (8002), datafeed-0 (8003)
        assert ("nginx", 8000) in ports
        assert ("broker-0", 8001) in ports
        assert ("broker-1", 8002) in ports
        assert ("datafeed-0", 8003) in ports
        assert len(ports) == 4
