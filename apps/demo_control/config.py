from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DEMOCONTROL_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://democontrol:democontrol@127.0.0.1:5432/democontrol"
    api_host: str = "127.0.0.1"
    api_port: int = 8100

    missionnet_base_url: str = "http://127.0.0.1:8090"
    sentinel_base_url: str = "http://127.0.0.1:8080"
    missionnet_lab_secret: str = "dev-only-lab-secret-change-me"

    poll_interval_seconds: float = 1.5
    poll_timeout_seconds: float = 30.0


settings = Settings()
