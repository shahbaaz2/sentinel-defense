from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SENTINEL_", env_file=".env", extra="ignore")

    env: str = "development"
    profile: str = "lite"

    database_url: str = "postgresql+asyncpg://sentinel:sentinel@127.0.0.1:5432/sentinel"

    llm_provider: str = "mock"
    llm_base_url: str = "http://127.0.0.1:8000/v1"
    llm_model: str = "mlx-community/Qwen3-4B-Instruct-2507-4bit"
    llm_max_tokens: int = 1500
    llm_timeout_seconds: float = 90.0
    external_ai_enabled: bool = False
    ai_enabled: bool = False
    """Phase 5: master switch for the AI Analyst. False is the safe default for a fresh checkout
    that hasn't downloaded a local model yet - deterministic detection/correlation never depend on
    this. See DECISIONS.md."""

    response_mode: str = "assisted"
    knowledge_bundle: str = "KB-local-dev"
    """Phase 6: real policy versioning lives in code (`services/policy_engine/engine.py::
    POLICY_BUNDLE_VERSION`), not settings, since it describes which deterministic rules are loaded,
    not a deployment-time option - see DECISIONS.md. `knowledge_bundle` stays a placeholder string
    here since no real knowledge bundle exists yet (RAG remains NOT ENABLED, deferred beyond
    Phase 6 - see System Assurance)."""
    synthetic_only: bool = True

    api_host: str = "127.0.0.1"
    api_port: int = 8080


settings = Settings()
