"""Configuration module for the Trading API."""

import os
from typing import List


class BroadcasterConfig:
    """Configuration for bar broadcaster."""

    @staticmethod
    def get_enabled() -> bool:
        """Check if broadcaster is enabled."""
        return os.getenv("BAR_BROADCASTER_ENABLED", "true").lower() in (
            "true",
            "1",
            "yes",
        )

    @staticmethod
    def get_interval() -> float:
        """Get broadcast interval in seconds."""
        try:
            return float(os.getenv("BAR_BROADCASTER_INTERVAL", "2.0"))
        except ValueError:
            return 2.0

    @staticmethod
    def get_symbols() -> List[str]:
        """Get list of symbols to broadcast."""
        symbols_env = os.getenv("BAR_BROADCASTER_SYMBOLS", "AAPL,GOOGL,MSFT")
        return [s.strip() for s in symbols_env.split(",") if s.strip()]

    @staticmethod
    def get_resolutions() -> List[str]:
        """Get list of resolutions to broadcast."""
        resolutions_env = os.getenv("BAR_BROADCASTER_RESOLUTIONS", "1")
        return [r.strip() for r in resolutions_env.split(",") if r.strip()]


__all__ = ["BroadcasterConfig"]
