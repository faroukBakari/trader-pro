#!/usr/bin/env python3
"""Generate nginx configuration for multi-process backend deployment.

This script generates an nginx configuration file that routes requests
to different backend servers based on the deployment configuration.

Usage:
    python scripts/gen_nginx_conf.py dev-config.yaml -o nginx-dev.conf
    nginx -t -c $(pwd)/nginx-dev.conf
"""

import argparse
import sys
from pathlib import Path
from typing import TextIO

# Add src to path to import trading_api modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from trading_api.shared.deployment import DeploymentConfig, load_config


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
    if "core" in config.servers:
        core_location = """        # Core endpoints (health, versions, docs)
        location ~ ^/api/v1/(health|version|versions|docs|redoc|openapi.json)$ {
            proxy_pass http://core_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }"""
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
    log_dir = Path(__file__).parent.parent / ".local" / "logs"
    access_log = log_dir / "nginx-access.log"
    error_log = log_dir / "nginx-error.log"

    # Generate complete configuration
    nginx_config = f"""# Auto-generated nginx configuration for multi-process backend
# Generated from deployment configuration
# DO NOT EDIT MANUALLY - regenerate using scripts/gen_nginx_conf.py

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
    """Validate generated nginx configuration.

    Tries to use local nginx binary first, falls back to system nginx.

    Args:
        config_path: Path to nginx configuration file

    Returns:
        True if validation succeeds, False otherwise
    """
    import subprocess

    # Ensure log directory exists
    log_dir = Path(__file__).parent.parent / ".local" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    # Check for local nginx binary first
    local_nginx = Path(__file__).parent.parent / ".local" / "bin" / "nginx"
    nginx_cmd = str(local_nginx) if local_nginx.exists() else "nginx"

    try:
        # Use absolute path for nginx -t
        abs_config_path = config_path.resolve()
        result = subprocess.run(
            [nginx_cmd, "-t", "-c", str(abs_config_path)],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            print(f"✅ Nginx configuration is valid: {abs_config_path}")
            print(result.stderr)
            return True
        else:
            print(f"❌ Nginx configuration validation failed: {abs_config_path}")
            print(result.stderr)
            return False

    except FileNotFoundError:
        print("❌ nginx command not found!")
        print("Install options:")
        print("  1. Standalone (no sudo): make install-nginx")
        print("  2. System package: sudo apt install nginx")
        return False


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate nginx configuration for multi-process backend"
    )
    parser.add_argument(
        "config", type=Path, help="Path to deployment configuration YAML file"
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("nginx-generated.conf"),
        help="Output nginx configuration file (default: nginx-generated.conf)",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate generated configuration with nginx -t",
    )

    args = parser.parse_args()

    # Load deployment configuration
    try:
        config = load_config(args.config)
    except Exception as e:
        print(f"❌ Failed to load configuration: {e}")
        return 1

    # Generate nginx configuration
    try:
        with open(args.output, "w") as f:
            generate_nginx_config(config, f)

        print(f"✅ Generated nginx configuration: {args.output}")
    except Exception as e:
        print(f"❌ Failed to generate nginx configuration: {e}")
        return 1

    # Validate if requested
    if args.validate:
        if not validate_nginx_config(args.output):
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
