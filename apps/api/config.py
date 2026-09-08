from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SENTINEL_", env_file=".env", extra="ignore")

    env: str = "development"
    profile: str = "lite"
    platform_label: str = "Apple Silicon (arm64)"
    """Purely descriptive, shown verbatim on System Assurance - override to the real host when
    deploying somewhere other than this Mac (e.g. "Linux x86_64 (Render)")."""

    database_url: str = "postgresql+asyncpg://sentinel:sentinel@127.0.0.1:5432/sentinel"

    llm_provider: str = "mock"
    llm_base_url: str = "http://127.0.0.1:8000/v1"
    llm_model: str = "mlx-community/Qwen3-4B-Instruct-2507-4bit"
    llm_max_tokens: int = 1500
    llm_timeout_seconds: float = 90.0
    external_ai_enabled: bool = False
    deepseek_api_key: str = ""
    deepseek_base_url: str = ""
    """Both only read when llm_provider == "deepseek" (a cloud deployment with no Apple-Silicon
    host to run MLXProvider - see ai/providers/deepseek_provider.py). Deliberately separate from
    `llm_base_url` (a vestigial Phase 5 placeholder no provider actually reads) rather than reusing
    it, so an empty `deepseek_base_url` cleanly falls back to DeepSeek's real default endpoint
    instead of an unrelated local-mlx-server URL. The API key is never logged, never sent to
    frontend JavaScript. Setting SENTINEL_LLM_PROVIDER=deepseek without also setting
    external_ai_enabled=true is a config error the operator should notice honestly reflected in
    System Assurance, not silently corrected - see docs/deployment.md."""
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
    cors_allowed_origins: str = "http://127.0.0.1:3000,http://localhost:3000"
    """Comma-separated. Defaults to the local dashboard only - a cloud deployment sets this to its
    real Vercel origin(s) (see docs/deployment.md). Never `*` - the dashboard sends no credentials
    cross-origin today, but an explicit origin list is the correct default regardless."""

    missionnet_base_url: str = "http://127.0.0.1:8090"
    missionnet_lab_secret: str = "dev-only-lab-secret-change-me"
    """Phase 7: the only two pieces of config the response executor needs to reach MissionNet's
    lab-control API - mirrors apps/demo_control/config.py's identical fields, since Demo Control
    and the executor are the only two callers of /lab/* (see apps/missionnet/lab.py's docstring)."""
    demo_control_base_url: str = "http://127.0.0.1:8100"
    """Used only by System Assurance's own reachability check - a cloud deployment sets this to
    Demo Control's real Render URL so the check reflects reality instead of an unreachable
    localhost address. See docs/deployment.md."""
    response_execution_enabled: bool = True
    """Master switch for Phase 7 execution, independent of response *planning* (Phase 6) which
    always stays on. False makes every execute/rollback request return 503 without touching
    MissionNet - an emergency kill switch, analogous to `ai_enabled` for the AI Analyst."""

    # -----------------------------------------------------------------------------------------
    # Phase 8: real sensor adapters. Every one of these defaults to disabled/absent so a fresh
    # checkout with no sensors configured behaves exactly like Phase 0-7 - see docs/integrations.md.
    # -----------------------------------------------------------------------------------------
    suricata_enabled: bool = False
    suricata_eve_path: str = "var/sensor-lab/suricata-out/eve.json"

    zeek_enabled: bool = False
    zeek_log_dir: str = "var/sensor-lab/zeek-out"

    wazuh_enabled: bool = False
    wazuh_base_url: str = ""
    wazuh_api_token: str = ""
    wazuh_verify_tls: bool = True

    splunk_enabled: bool = False
    splunk_base_url: str = ""
    splunk_token: str = ""
    splunk_verify_tls: bool = True
    splunk_index: str = ""
    splunk_query: str = ""
    """A bounded SPL search, e.g. `search index=security sourcetype=suricata`. Sentinel appends its
    own time-window/result-limit constraints - see docs/splunk-integration.md. Never logged."""

    falco_enabled: bool = False


settings = Settings()
