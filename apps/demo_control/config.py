from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from domain.db_url import normalize_async_postgres_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DEMOCONTROL_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://democontrol:democontrol@127.0.0.1:5432/democontrol"
    api_host: str = "127.0.0.1"
    api_port: int = 8100
    cors_allowed_origins: str = "http://127.0.0.1:3200,http://localhost:3200"
    """Comma-separated. A cloud deployment sets this to its real Vercel origin - see
    docs/deployment.md."""

    missionnet_base_url: str = "http://127.0.0.1:8090"
    sentinel_base_url: str = "http://127.0.0.1:8080"
    missionnet_lab_secret: str = "dev-only-lab-secret-change-me"

    poll_interval_seconds: float = 1.5
    poll_timeout_seconds: float = 30.0

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        return normalize_async_postgres_url(value)


settings = Settings()
