"""TWS provider configurations."""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class TWSProviderConfig(BaseSettings):
    """TWS provider configuration.

    [AUTO-LOAD]: Reads from environment variables with TWS_ prefix.
    [ENVIRONMENT]: Works with system env vars - .env.local file is optional.

    Environment variables:
        TWS_ENABLED: bool = True
        TWS_HOST: str = "127.0.0.1"
        TWS_PORT: int = 7497 (paper trading) or 7496 (live trading)
        TWS_CLIENT_ID: int = 1 (1-32)
        TWS_CONNECTION_TIMEOUT: float = 10.0
        TWS_REALTIME_BAR_SIZE: int = 5 (5 or 10 seconds only)
        TWS_MARKET_DATA_TYPE: int = 1 (1=real-time, 2=frozen, 3=delayed, 4=delayed-frozen)
        TWS_MAX_CONCURRENT_RT_SUBSCRIPTIONS: int = 100
    """

    enabled: bool = True
    host: str = Field(
        default="127.0.0.1",
        description="TWS/IB Gateway hostname or IP address",
    )
    port: int = Field(
        default=7497,
        description="TWS/IB Gateway port (7497=paper TWS, 7496=live TWS, 4002=paper Gateway, 4001=live Gateway)",
    )
    client_id: int = Field(
        default=1,
        ge=1,
        le=32,
        description="Client ID (1-32) - must be unique per connection",
    )
    connection_timeout: float = Field(
        default=10.0,
        ge=5.0,
        description="Connection timeout in seconds",
    )
    realtime_bar_size: int = Field(
        default=5,
        description="Real-time bar size in seconds (5 or 10 only)",
    )
    market_data_type: int = Field(
        default=1,
        ge=1,
        le=4,
        description="Market data type (1=real-time, 2=frozen, 3=delayed, 4=delayed-frozen)",
    )
    max_concurrent_rt_subscriptions: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Maximum concurrent real-time subscriptions (TWS limit varies by account)",
    )

    model_config = SettingsConfigDict(
        env_prefix="TWS_",
        env_file=".env.local",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Validate TWS/Gateway port is one of the standard ports."""
        valid_ports = {7497, 7496, 4002, 4001}  # Paper/Live TWS/Gateway
        if v not in valid_ports:
            raise ValueError(
                f"Port must be one of {valid_ports} "
                f"(7497=paper TWS, 7496=live TWS, 4002=paper Gateway, 4001=live Gateway)"
            )
        return v

    @field_validator("realtime_bar_size")
    @classmethod
    def validate_bar_size(cls, v: int) -> int:
        """Validate real-time bar size is 5 or 10 seconds."""
        if v not in {5, 10}:
            raise ValueError("Real-time bar size must be 5 or 10 seconds")
        return v


__all__ = ["TWSProviderConfig"]
