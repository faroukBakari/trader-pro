"""DEPRECATED: Re-export from shared.plugins for backward compatibility.

This module is deprecated. Use 'from trading_api.shared.plugins import FastWSAdapter' instead.
Will be removed after full migration to modular architecture.
"""

from trading_api.shared.plugins import FastWSAdapter

__all__ = ["FastWSAdapter"]
