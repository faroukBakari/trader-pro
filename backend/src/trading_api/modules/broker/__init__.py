"""Broker module - Trading operations.

Provides REST API and WebSocket streaming for orders, positions,
executions, and account information.
"""

from pathlib import Path

from trading_api.shared import Module


class BrokerModule(Module):
    """Broker module implementation.

    Implements the Module Protocol for pluggable broker functionality.
    Provides eager service instantiation and router registration.

    Attributes:
        _service: BrokerService instance
        _api_routers: List of FastAPI routers
        _ws_routers: List of WebSocket routers
    """

    @property
    def module_dir(self) -> Path:
        """Return the directory path for this module.

        Returns:
            Path: Module directory path
        """
        return Path(__file__).parent

    @property
    def tags(self) -> list[dict[str, str]]:
        """Get OpenAPI tags for broker module.

        Returns:
            list[dict[str, str]]: OpenAPI tags describing broker operations
        """
        return [
            {
                "name": "broker",
                "description": "Broker operations (orders, positions, executions)",
            }
        ]


__all__ = ["BrokerModule"]
