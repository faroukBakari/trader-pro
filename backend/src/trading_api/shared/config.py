from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    JWT_ALGORITHM: str = "RS256"
    JWT_PRIVATE_KEY_PATH: Path = Path(".local/secrets/jwt_private.pem")
    JWT_PUBLIC_KEY_PATH: Path = Path(".local/secrets/jwt_public.pem")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 5
    GOOGLE_CLIENT_ID: str = ""

    # CORS Configuration
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:8000"]
    CORS_ALLOW_CREDENTIALS: bool = True

    # Cookie Configuration
    COOKIE_SECURE: bool = False  # Set to True in production (HTTPS only)

    model_config = SettingsConfigDict(env_file=".env.local", env_file_encoding="utf-8")

    @model_validator(mode="after")
    def resolve_paths(self) -> "Settings":
        """Resolve relative paths to absolute from project root"""
        if not self.JWT_PRIVATE_KEY_PATH.is_absolute():
            project_root = Path(__file__).resolve().parent.parent.parent.parent
            self.JWT_PRIVATE_KEY_PATH = project_root / self.JWT_PRIVATE_KEY_PATH
            self.JWT_PUBLIC_KEY_PATH = project_root / self.JWT_PUBLIC_KEY_PATH
        return self

    @property
    def jwt_private_key(self) -> str:
        return self.JWT_PRIVATE_KEY_PATH.read_text()

    @property
    def jwt_public_key(self) -> str:
        return self.JWT_PUBLIC_KEY_PATH.read_text()


settings = Settings()
