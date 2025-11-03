"""Backend management and development scripts.

This package contains executable CLI tools that can also be imported
as modules for testing and integration purposes.

All scripts remain executable via:
    poetry run python scripts/backend_manager.py <args>

And can now be cleanly imported for testing:
    from scripts.backend_manager import ServerManager
"""

from scripts.backend_manager import (
    ServerManager,
    check_all_ports,
    generate_nginx_config,
    generate_rest_location_blocks,
    generate_upstream_blocks,
    generate_websocket_location_block,
    is_port_in_use,
)

__all__ = [
    "ServerManager",
    "check_all_ports",
    "generate_nginx_config",
    "generate_rest_location_blocks",
    "generate_upstream_blocks",
    "generate_websocket_location_block",
    "is_port_in_use",
]
