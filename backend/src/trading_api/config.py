from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    JWT_ALGORITHM: str = "RS256"
    JWT_PRIVATE_KEY_PATH: Path = Path("backend/.local/secrets/jwt_private.pem")
    JWT_PUBLIC_KEY_PATH: Path = Path("backend/.local/secrets/jwt_public.pem")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 5
    GOOGLE_CLIENT_ID: str = ""

    model_config = SettingsConfigDict(env_file=".env.local", env_file_encoding="utf-8")

    @property
    def jwt_private_key(self) -> str:
        return self.JWT_PRIVATE_KEY_PATH.read_text()

    @property
    def jwt_public_key(self) -> str:
        return self.JWT_PUBLIC_KEY_PATH.read_text()


settings = Settings()
