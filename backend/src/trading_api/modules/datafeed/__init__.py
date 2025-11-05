"""Datafeed module - Market data and symbol information.

Provides REST API and WebSocket streaming for market data.
"""

from pathlib import Path

from trading_api.shared import Module


class DatafeedModule(Module):
    """Datafeed module implementation.

    Implements the Module Protocol for pluggable datafeed functionality.
    Provides lazy-loaded service instantiation and router registration.

    Attributes:
        _service: Lazy-loaded DatafeedService instance
        _enabled: Whether this module is enabled for loading
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
        """Get OpenAPI tags for datafeed module.

        Returns:
            list[dict[str, str]]: OpenAPI tags describing datafeed operations
        """
        return [
            {
                "name": "datafeed",
                "description": "Market data and symbols operations",
            }
        ]


__all__ = ["DatafeedModule"]
