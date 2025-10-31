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
import logging
import subprocess
import sys
from pathlib import Path
from typing import TextIO

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from trading_api.shared.deployment import (  # noqa: E402
    DeploymentConfig,
    load_config,
)

# Import ServerManager from scripts (same directory)
from server_manager import ServerManager, check_all_ports, is_port_in_use  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


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
