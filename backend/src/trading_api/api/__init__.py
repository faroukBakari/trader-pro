"""API routers.

DEPRECATION NOTICE: HealthApi and VersionApi have moved to trading_api.shared.api
The re-exports below are for backward compatibility and will be removed in a future version.
Please update imports to use:
    from trading_api.shared.api import HealthApi, VersionApi
"""

# Backward compatibility re-exports (DEPRECATED - use trading_api.shared.api instead)
from ..shared.api import HealthApi, VersionApi
from .broker import BrokerApi
from .datafeed import DatafeedApi

__all__ = ["BrokerApi", "DatafeedApi", "VersionApi", "HealthApi"]
