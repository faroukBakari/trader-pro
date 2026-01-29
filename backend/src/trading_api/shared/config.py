from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    JWT_ALGORITHM: str = "RS256"
    JWT_PRIVATE_KEY_PATH: Path = Path(".local/secrets/jwt_private.pem")
    JWT_PUBLIC_KEY_PATH: Path = Path(".local/secrets/jwt_public.pem")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    GOOGLE_CLIENT_ID: str = ""

    # CORS Configuration
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:8000"]
    CORS_ALLOW_CREDENTIALS: bool = True

    # Cookie Configuration
    COOKIE_SECURE: bool = False  # Set to True in production (HTTPS only)

    # API Configuration (used by app_factory and client generation)
    API_PREFIX: str = "/api"
    API_PORT: int = 8000
    DEFAULT_TIMEOUT: float = 30.0

    # Inter-module HMAC authentication
    INTERNAL_HMAC_KEY_PATH: Path = Path(".local/secrets/hmac_internal.key")
    INTERNAL_SIGNATURE_TTL_SECONDS: int = 30  # Replay protection window

    # PostgreSQL Datastore Configuration
    DATASTORE_POSTGRES_DSN: str | None = None
    DATASTORE_POSTGRES_USER: str = "trader"
    DATASTORE_POSTGRES_PASSWORD: str = "trader_dev"
    DATASTORE_POSTGRES_HOST: str = "localhost"
    DATASTORE_POSTGRES_PORT: int = 5433
    DATASTORE_POSTGRES_DB: str = "trader_bars"
    DATASTORE_POSTGRES_POOL_MAX_SIZE: int = 10
    DATASTORE_POSTGRES_POOL_RECONNECT_TIMEOUT: float = 5.0

    model_config = SettingsConfigDict(env_file=".env.local", env_file_encoding="utf-8")

    @model_validator(mode="after")
    def resolve_paths(self) -> "Settings":
        """Resolve relative paths to absolute from project root"""
        if not self.JWT_PRIVATE_KEY_PATH.is_absolute():
            project_root = Path(__file__).resolve().parent.parent.parent.parent
            self.JWT_PRIVATE_KEY_PATH = project_root / self.JWT_PRIVATE_KEY_PATH
            self.JWT_PUBLIC_KEY_PATH = project_root / self.JWT_PUBLIC_KEY_PATH
            self.INTERNAL_HMAC_KEY_PATH = project_root / self.INTERNAL_HMAC_KEY_PATH
        return self

    @property
    def jwt_private_key(self) -> str:
        return self.JWT_PRIVATE_KEY_PATH.read_text()

    @property
    def jwt_public_key(self) -> str:
        return self.JWT_PUBLIC_KEY_PATH.read_text()

    @property
    def internal_hmac_key(self) -> bytes:
        """Load HMAC key for inter-module auth. Empty bytes if file missing."""
        if self.INTERNAL_HMAC_KEY_PATH.exists():
            return self.INTERNAL_HMAC_KEY_PATH.read_bytes()
        return b""  # Empty = feature disabled

    @property
    def postgres_dsn(self) -> str:
        """Build PostgreSQL DSN from config or individual components."""
        if self.DATASTORE_POSTGRES_DSN:
            return self.DATASTORE_POSTGRES_DSN
        return (
            f"postgresql://{self.DATASTORE_POSTGRES_USER}:"
            f"{self.DATASTORE_POSTGRES_PASSWORD}@"
            f"{self.DATASTORE_POSTGRES_HOST}:{self.DATASTORE_POSTGRES_PORT}/"
            f"{self.DATASTORE_POSTGRES_DB}"
        )


settings = Settings()
