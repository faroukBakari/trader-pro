"""Pluggable modules for the trading API.

Contains all feature modules (datafeed, broker) that can be loaded
independently via the application factory.
"""

from .broker import BrokerModule
from .datafeed import DatafeedModule

# Registry of available module classes for explicit registration
AVAILABLE_MODULES = [
    BrokerModule,
    DatafeedModule,
]

__all__ = ["AVAILABLE_MODULES", "BrokerModule", "DatafeedModule"]
