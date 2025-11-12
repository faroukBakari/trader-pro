"""Unit tests for backend_manager.py nginx configuration generation.

These tests validate nginx configuration generation functions including
upstream blocks, location blocks, and WebSocket routing. They don't start
real processes and are suitable for frequent execution.

Test Coverage:
- generate_upstream_blocks() - Create nginx upstream server blocks
- generate_rest_location_blocks() - Create REST API routing
- generate_websocket_location_block() - Create WebSocket routing
- generate_nginx_config() - Generate complete nginx configuration
"""

import os
import tempfile
from pathlib import Path
from typing import TextIO, cast

import pytest

from scripts.backend_manager import (
    generate_nginx_config,
    generate_rest_location_blocks,
    generate_upstream_blocks,
    generate_websocket_location_block,
)
from trading_api.shared.deployment import (
    DeploymentConfig,
    NginxConfig,
    ServerConfig,
    WebSocketConfig,
)


@pytest.mark.unit
class TestNginxConfigGeneration:
    """Unit tests for nginx configuration generation."""

    def test_generate_upstream_blocks_single_server(self) -> None:
        """Test upstream block generation with single server instance."""
        config = DeploymentConfig(
            nginx=NginxConfig(port=8000, worker_processes=1, worker_connections=1024),
            servers={
                "broker": ServerConfig(
                    port=8001, instances=1, modules=["broker"], reload=True
                ),
            },
            websocket=WebSocketConfig(routing_strategy="path", query_param_name="type"),
            websocket_routes={"broker": "broker"},
        )

        upstream = generate_upstream_blocks(config)

        assert "upstream broker_backend" in upstream
        assert "server 127.0.0.1:8001;" in upstream

    def test_generate_upstream_blocks_multiple_instances(self) -> None:
        """Test upstream block generation with multiple instances."""
        config = DeploymentConfig(
            nginx=NginxConfig(port=8000, worker_processes=1, worker_connections=1024),
            servers={
                "broker": ServerConfig(
                    port=8001, instances=3, modules=["broker"], reload=True
                ),
            },
            websocket=WebSocketConfig(routing_strategy="path", query_param_name="type"),
            websocket_routes={"broker": "broker"},
        )

        upstream = generate_upstream_blocks(config)

        assert "upstream broker_backend" in upstream
        assert "server 127.0.0.1:8001;" in upstream
        assert "server 127.0.0.1:8002;" in upstream
        assert "server 127.0.0.1:8003;" in upstream

    def test_generate_upstream_blocks_multiple_servers(self) -> None:
        """Test upstream blocks for multiple different servers."""
        config = DeploymentConfig(
            nginx=NginxConfig(port=8000, worker_processes=1, worker_connections=1024),
            servers={
                "broker": ServerConfig(
                    port=8001, instances=2, modules=["broker"], reload=True
                ),
                "datafeed": ServerConfig(
                    port=8003, instances=2, modules=["datafeed"], reload=True
                ),
            },
            websocket=WebSocketConfig(routing_strategy="path", query_param_name="type"),
            websocket_routes={"broker": "broker", "datafeed": "datafeed"},
        )

        upstream = generate_upstream_blocks(config)

        # Broker upstream
        assert "upstream broker_backend" in upstream
        assert "server 127.0.0.1:8001;" in upstream
        assert "server 127.0.0.1:8002;" in upstream

        # Datafeed upstream
        assert "upstream datafeed_backend" in upstream
        assert "server 127.0.0.1:8003;" in upstream
        assert "server 127.0.0.1:8004;" in upstream

    def test_generate_rest_location_blocks(self) -> None:
        """Test REST API location block generation."""
        config = DeploymentConfig(
            nginx=NginxConfig(port=8000, worker_processes=1, worker_connections=1024),
            servers={
                "broker": ServerConfig(
                    port=8001, instances=1, modules=["broker"], reload=True
                ),
                "datafeed": ServerConfig(
                    port=8002, instances=1, modules=["datafeed"], reload=True
                ),
            },
            websocket=WebSocketConfig(routing_strategy="path", query_param_name="type"),
            websocket_routes={"broker": "broker", "datafeed": "datafeed"},
        )

        locations = generate_rest_location_blocks(config)

        # Broker module location
        assert "location /api/v1/broker/" in locations
        assert "proxy_pass http://broker_backend;" in locations

        # Datafeed module location
        assert "location /api/v1/datafeed/" in locations
        assert "proxy_pass http://datafeed_backend;" in locations

        # Verify proper proxy headers are set
        assert "proxy_set_header Host $host;" in locations
        assert "proxy_set_header X-Real-IP $remote_addr;" in locations

    def test_generate_websocket_path_based_routing(self) -> None:
        """Test WebSocket location block with path-based routing."""
        config = DeploymentConfig(
            nginx=NginxConfig(port=8000, worker_processes=1, worker_connections=1024),
            servers={
                "broker": ServerConfig(
                    port=8001, instances=1, modules=["broker"], reload=True
                ),
                "datafeed": ServerConfig(
                    port=8002, instances=1, modules=["datafeed"], reload=True
                ),
            },
            websocket=WebSocketConfig(routing_strategy="path", query_param_name="type"),
            websocket_routes={"broker": "broker", "datafeed": "datafeed"},
        )

        ws_location = generate_websocket_location_block(config)

        # Should have path-based routes
        assert "location /api/v1/broker/ws" in ws_location
        assert "location /api/v1/datafeed/ws" in ws_location
        assert "proxy_pass http://broker_backend;" in ws_location
        assert "proxy_pass http://datafeed_backend;" in ws_location

        # Should NOT have map directive
        assert "map $arg_" not in ws_location

    def test_generate_websocket_query_param_routing(self) -> None:
        """Test WebSocket location block with query parameter routing."""
        config = DeploymentConfig(
            nginx=NginxConfig(port=8000, worker_processes=1, worker_connections=1024),
            servers={
                "broker": ServerConfig(
                    port=8001, instances=1, modules=["broker"], reload=True
                ),
                "datafeed": ServerConfig(
                    port=8002, instances=1, modules=["datafeed"], reload=True
                ),
            },
            websocket=WebSocketConfig(
                routing_strategy="query_param", query_param_name="type"
            ),
            websocket_routes={"broker": "broker", "datafeed": "datafeed"},
        )

        ws_config = generate_websocket_location_block(config)

        # Should have map directive for query param routing
        assert "map $arg_type $ws_backend" in ws_config
        assert "broker_backend" in ws_config
        assert "datafeed_backend" in ws_config

        # Should have single WebSocket location
        assert "location /api/v1/ws" in ws_config
        assert "proxy_pass http://$ws_backend;" in ws_config

    def test_generate_full_nginx_config(self) -> None:
        """Test full nginx configuration generation."""
        config = DeploymentConfig(
            nginx=NginxConfig(
                port=8000, worker_processes="auto", worker_connections=2048
            ),
            servers={
                "broker": ServerConfig(
                    port=8001, instances=2, modules=["broker"], reload=True
                ),
            },
            websocket=WebSocketConfig(routing_strategy="path", query_param_name="type"),
            websocket_routes={"broker": "broker"},
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
            try:
                generate_nginx_config(config, cast(TextIO, f))
                f.flush()

                # Read generated config
                nginx_conf = Path(f.name).read_text()

                # Verify key sections
                assert "worker_processes auto;" in nginx_conf
                assert "worker_connections 2048;" in nginx_conf
                assert "listen 8000;" in nginx_conf
                assert "upstream broker_backend" in nginx_conf
                assert "server 127.0.0.1:8001;" in nginx_conf
                assert "server 127.0.0.1:8002;" in nginx_conf
                assert "location /api/v1/broker/" in nginx_conf

            finally:
                # Cleanup
                os.unlink(f.name)

    def test_generate_nginx_config_worker_processes_numeric(self) -> None:
        """Test nginx config generation with numeric worker_processes."""
        config = DeploymentConfig(
            nginx=NginxConfig(port=8000, worker_processes=4, worker_connections=1024),
            servers={
                "broker": ServerConfig(
                    port=8001, instances=1, modules=["broker"], reload=True
                ),
            },
            websocket=WebSocketConfig(routing_strategy="path", query_param_name="type"),
            websocket_routes={"broker": "broker"},
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
            try:
                generate_nginx_config(config, cast(TextIO, f))
                f.flush()

                nginx_conf = Path(f.name).read_text()
                assert "worker_processes 4;" in nginx_conf

            finally:
                os.unlink(f.name)
