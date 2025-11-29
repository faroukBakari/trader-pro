"""Pluggable modules for the trading API.

Contains all feature modules (datafeed, broker) that can be loaded
independently via the application factory.
"""

from .auth import AuthModule
from .broker import BrokerModule
from .datafeed import DatafeedModule

# Registry of available module classes for explicit registration
AVAILABLE_MODULES = [
    AuthModule,
    BrokerModule,
    DatafeedModule,
]

__all__ = ["AVAILABLE_MODULES", "AuthModule", "BrokerModule", "DatafeedModule"]
# backend/src/trading_api/providers/__init__.py
