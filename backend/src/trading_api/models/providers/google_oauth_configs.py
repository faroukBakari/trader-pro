"""Authentication provider configurations."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class GoogleProviderConfig(BaseSettings):
    """Google OAuth configuration.

    [AUTO-LOAD]: Reads from environment variables with GOOGLE_ prefix.
    [ENVIRONMENT]: Works with system env vars - .env.local file is optional.

    Note: This uses BaseSettings instead of ProviderConfig to enable
    automatic environment variable loading. The 'enabled' field is included
    to maintain compatibility with ProviderConfig interface.
    """

    enabled: bool = True
    client_id: str = ""  # Required at runtime, optional during code generation

    model_config = SettingsConfigDict(
        env_prefix="GOOGLE_",
        env_file=".env.local",
        env_file_encoding="utf-8",
        extra="ignore",
    )


__all__ = ["GoogleProviderConfig"]
