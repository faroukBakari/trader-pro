"""Core API utilities and configurations.

DEPRECATION NOTICE:
- DatafeedService has moved to trading_api.modules.datafeed.service
- BrokerService has moved to trading_api.modules.broker.service

The re-exports below are for backward compatibility and will be removed in a future version.
Please update imports to use:
    from trading_api.modules.datafeed import DatafeedService
    from trading_api.modules.broker import BrokerService
"""

from ..modules.broker.service import BrokerService

# Backward compatibility re-exports (DEPRECATED)
from ..modules.datafeed.service import DatafeedService

__all__ = [
    "BrokerService",
    "DatafeedService",
]
