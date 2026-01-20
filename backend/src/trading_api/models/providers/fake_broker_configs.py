"""FakeBrokerProvider configuration."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class FakeBrokerProviderConfig(BaseSettings):
    """Configuration for FakeBrokerProvider (mock broker).

    [AUTO-LOAD]: Reads from environment variables with FAKE_BROKER_ prefix.
    [ENVIRONMENT]: Works with system env vars - .env.local file is optional.

    Environment variables (prefix: FAKE_BROKER_):
        FAKE_BROKER_ENABLED: Enable/disable provider (default: true)
        FAKE_BROKER_INITIAL_BALANCE: Starting account balance (default: 100000.0)
        FAKE_BROKER_EXECUTION_DELAY_MIN: Min delay between executions (default: 1.0)
        FAKE_BROKER_EXECUTION_DELAY_MAX: Max delay between executions (default: 2.0)
        FAKE_BROKER_ACCOUNT_ID: Demo account ID (default: DEMO-ACCOUNT)
        FAKE_BROKER_ACCOUNT_NAME: Demo account name (default: Demo Trading Account)

    Note: This uses BaseSettings instead of ProviderConfig to enable
    automatic environment variable loading and avoid import boundary violations.
    The 'enabled' field is included to maintain compatibility with ProviderConfig interface.
    """

    model_config = SettingsConfigDict(
        env_prefix="FAKE_BROKER_",
        env_file=".env.local",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    enabled: bool = Field(
        default=True,
        description="Enable fake broker provider (for development/testing)",
    )

    initial_balance: float = Field(
        default=100000.0,
        description="Initial account balance",
    )

    execution_delay_min: float = Field(
        default=1.0,
        description="Minimum delay between simulated executions (seconds)",
    )

    execution_delay_max: float = Field(
        default=2.0,
        description="Maximum delay between simulated executions (seconds)",
    )

    account_id: str = Field(
        default="DEMO-ACCOUNT",
        description="Demo account identifier",
    )

    account_name: str = Field(
        default="Demo Trading Account",
        description="Demo account display name",
    )


__all__ = ["FakeBrokerProviderConfig"]
