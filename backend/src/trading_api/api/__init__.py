"""API routers.

DEPRECATION NOTICE:
- HealthApi and VersionApi have moved to trading_api.shared.api
- DatafeedApi has moved to trading_api.modules.datafeed.api
- BrokerApi has moved to trading_api.modules.broker.api

The re-exports below are for backward compatibility and will be removed in a future version.
Please update imports to use:
    from trading_api.shared.api import HealthApi, VersionApi
    from trading_api.modules.datafeed import DatafeedApi
    from trading_api.modules.broker import BrokerApi
"""

from ..modules.broker.api import BrokerApi
from ..modules.datafeed.api import DatafeedApi

# Backward compatibility re-exports (DEPRECATED)
from ..shared.api import HealthApi, VersionApi

__all__ = ["BrokerApi", "DatafeedApi", "VersionApi", "HealthApi"]
