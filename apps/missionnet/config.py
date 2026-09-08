from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from domain.db_url import normalize_async_postgres_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MISSIONNET_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://missionnet:missionnet@127.0.0.1:5432/missionnet"
    api_host: str = "127.0.0.1"
    api_port: int = 8090
    lab_secret: str = "dev-only-lab-secret-change-me"

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        return normalize_async_postgres_url(value)


settings = Settings()
