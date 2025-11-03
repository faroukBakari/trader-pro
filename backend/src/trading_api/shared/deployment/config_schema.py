"""Configuration schema for multi-process backend deployment."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


class NginxConfig(BaseModel):
    """Nginx gateway configuration."""

    port: int = Field(..., description="Public-facing nginx port")
    worker_processes: int | str = Field(
        default=1, description="Number of worker processes (or 'auto')"
    )
    worker_connections: int = Field(
        default=1024, description="Max connections per worker"
    )

    @field_validator("port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Validate port is in valid range."""
        if not (1024 <= v <= 65535):
            raise ValueError("Port must be between 1024 and 65535")
        return v

    @field_validator("worker_processes")
    @classmethod
    def validate_worker_processes(cls, v: int | str) -> int | str:
        """Validate worker_processes is 'auto' or positive integer."""
        if isinstance(v, str):
            if v != "auto":
                raise ValueError(
                    "worker_processes must be 'auto' or a positive integer"
                )
            return v
        if v < 1:
            raise ValueError("worker_processes must be at least 1")
        return v


class ServerConfig(BaseModel):
    """Individual server configuration."""

    port: int = Field(..., description="Base port for this server")
    instances: int = Field(default=1, description="Number of instances to spawn")
    modules: list[str] = Field(
        default_factory=list, description="Enabled modules for this server"
    )
    reload: bool = Field(default=True, description="Enable auto-reload")

    @field_validator("port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Validate port is in valid range."""
        if not (1024 <= v <= 65535):
            raise ValueError("Port must be between 1024 and 65535")
        return v

    @field_validator("instances")
    @classmethod
    def validate_instances(cls, v: int) -> int:
        """Validate instances is positive."""
        if v < 1:
            raise ValueError("instances must be at least 1")
        return v


class WebSocketConfig(BaseModel):
    """WebSocket routing configuration."""

    routing_strategy: str = Field(
        default="query_param",
        description="Routing strategy: 'query_param' or 'path'",
    )
    query_param_name: str = Field(
        default="type", description="Query parameter name for routing"
    )

    @field_validator("routing_strategy")
    @classmethod
    def validate_routing_strategy(cls, v: str) -> str:
        """Validate routing strategy is supported."""
        if v not in ("query_param", "path"):
            raise ValueError("routing_strategy must be 'query_param' or 'path'")
        return v


class DeploymentConfig(BaseModel):
    """Complete deployment configuration."""

    api_base_url: str = Field(
        default="/api/v1",
        description="API base URL prefix for all modules",
    )
    nginx: NginxConfig = Field(..., description="Nginx gateway configuration")
    servers: dict[str, ServerConfig] = Field(
        ..., description="Server configurations by name"
    )
    websocket: WebSocketConfig = Field(
        default_factory=WebSocketConfig, description="WebSocket routing configuration"
    )
    websocket_routes: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of WebSocket routes to server names",
    )

    @model_validator(mode="after")
    def validate_no_port_conflicts(self) -> "DeploymentConfig":
        """Validate no port conflicts between nginx and servers."""
        all_ports: dict[int, str] = {}

        # Check nginx port
        nginx_port = self.nginx.port
        all_ports[nginx_port] = "nginx"

        # Check all server ports (including instance ports)
        for server_name, server_config in self.servers.items():
            for instance_idx in range(server_config.instances):
                port = server_config.port + instance_idx
                if port in all_ports:
                    existing = all_ports[port]
                    raise ValueError(
                        f"Port conflict: {port} used by both "
                        f"'{existing}' and '{server_name}-{instance_idx}'"
                    )
                all_ports[port] = f"{server_name}-{instance_idx}"

        return self

    @model_validator(mode="after")
    def validate_core_server_has_no_modules(self) -> "DeploymentConfig":
        """Validate core server has empty modules list."""
        if "core" in self.servers:
            core_modules = self.servers["core"].modules
            if core_modules:
                raise ValueError(
                    f"Core server must have no modules, found: {core_modules}"
                )

        return self

    @model_validator(mode="after")
    def validate_websocket_routes(self) -> "DeploymentConfig":
        """Validate all websocket routes reference existing servers."""
        for route, server_name in self.websocket_routes.items():
            if server_name not in self.servers:
                raise ValueError(
                    f"WebSocket route '{route}' references unknown server '{server_name}'"
                )

        return self

    def get_all_ports(self) -> list[tuple[str, int]]:
        """Get all ports that will be used.

        Returns:
            List of (name, port) tuples
        """
        ports: list[tuple[str, int]] = [("nginx", self.nginx.port)]

        for server_name, server_config in self.servers.items():
            for instance_idx in range(server_config.instances):
                port = server_config.port + instance_idx
                name = f"{server_name}-{instance_idx}"
                ports.append((name, port))

        return ports


def load_config(config_path: str | Path) -> DeploymentConfig:
    """Load deployment configuration from YAML file.

    Args:
        config_path: Path to YAML configuration file

    Returns:
        Validated deployment configuration

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If configuration is invalid
    """
    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r") as f:
        data: dict[str, Any] = yaml.safe_load(f)

    return DeploymentConfig(**data)
