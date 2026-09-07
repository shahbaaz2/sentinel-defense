"""The one full Sentinel ingestion cycle: sync assets -> ingest audit+telemetry -> deterministic
detection -> deterministic correlation. Every caller (the CLI, `make ingest-watch`, and Phase 3's
Demo Control Plane triggering it over HTTP) goes through this exact same function, so there is
never a second, divergent code path that skips the adapter/normalizer/detection/incident engine.
"""

import dataclasses
import logging
import os
from dataclasses import asdict, dataclass

from domain.db import Base, SessionLocal, engine
from domain.models import orm  # noqa: F401 - registers tables on Base.metadata
from services.detection_engine.engine import run_detection_engine
from services.event_ingestor.registry import AdapterDescriptor, build_adapter_registry
from services.event_ingestor.service import ingest_all, sync_missionnet_assets
from services.incident_engine.engine import run_incident_correlation

logger = logging.getLogger("sentinel.ingest_pipeline")

MISSIONNET_BASE_URL = os.environ.get("MISSIONNET_BASE_URL", "http://127.0.0.1:8090")


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    return default if raw is None else raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class _EnvAdapterSettings:
    """Reads the same `SENTINEL_*` env vars `apps.api.config.Settings` reads, directly - `services/`
    never imports `apps/` (see services/event_ingestor/registry.py's `AdapterSettings` Protocol),
    exactly like this module already reads `MISSIONNET_BASE_URL` above rather than importing
    the apps-layer Settings object."""

    missionnet_base_url: str = MISSIONNET_BASE_URL
    suricata_enabled: bool = _env_bool("SENTINEL_SURICATA_ENABLED", False)
    suricata_eve_path: str = os.environ.get(
        "SENTINEL_SURICATA_EVE_PATH", "var/sensor-lab/suricata-out/eve.json"
    )
    zeek_enabled: bool = _env_bool("SENTINEL_ZEEK_ENABLED", False)
    zeek_log_dir: str = os.environ.get("SENTINEL_ZEEK_LOG_DIR", "var/sensor-lab/zeek-out")
    wazuh_enabled: bool = _env_bool("SENTINEL_WAZUH_ENABLED", False)
    wazuh_base_url: str = os.environ.get("SENTINEL_WAZUH_BASE_URL", "")
    wazuh_api_token: str = os.environ.get("SENTINEL_WAZUH_API_TOKEN", "")
    wazuh_verify_tls: bool = _env_bool("SENTINEL_WAZUH_VERIFY_TLS", True)
    splunk_enabled: bool = _env_bool("SENTINEL_SPLUNK_ENABLED", False)
    splunk_base_url: str = os.environ.get("SENTINEL_SPLUNK_BASE_URL", "")
    splunk_token: str = os.environ.get("SENTINEL_SPLUNK_TOKEN", "")
    splunk_verify_tls: bool = _env_bool("SENTINEL_SPLUNK_VERIFY_TLS", True)
    splunk_index: str = os.environ.get("SENTINEL_SPLUNK_INDEX", "")
    splunk_query: str = os.environ.get("SENTINEL_SPLUNK_QUERY", "")
    falco_enabled: bool = _env_bool("SENTINEL_FALCO_ENABLED", False)


@dataclass
class PipelineResult:
    assets_synced: int
    ingestion: list[dict]
    detections_created: int
    detections_skipped_duplicate: int
    incidents_created: int
    incidents_updated: int

    def as_dict(self) -> dict:
        return asdict(self)


async def run_ingestion_cycle(
    base_url: str = MISSIONNET_BASE_URL,
    scenario_id: str | None = None,
    adapter_registry: list[AdapterDescriptor] | None = None,
) -> PipelineResult:
    """`adapter_registry`, when given, overrides the default env-var-derived sensor registry - the
    apps-layer caller (`apps/api/admin_routes.py`) builds this from `apps.api.config.settings`
    (which parses `.env` via pydantic-settings) and passes it in, since `services/` must never
    import `apps/` (see services/event_ingestor/registry.py). The CLI path (`make ingest-once`,
    no explicit registry) falls back to reading real process env vars directly, which works for a
    shell that actually exports `SENTINEL_SURICATA_ENABLED=true` etc. before running it."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # MissionNet asset sync is its own network call, outside the multi-adapter loop below - a
    # MissionNet outage must not prevent Suricata/Zeek/Wazuh/Splunk from still being ingested, so
    # it gets the exact same isolation `ingest_all` gives every adapter (Phase 8 §9/§18).
    asset_count = 0
    try:
        async with SessionLocal() as session:
            asset_count = await sync_missionnet_assets(session, base_url)
    except Exception:  # noqa: BLE001 - see comment above; never abort the whole cycle for this
        logger.exception("MissionNet asset sync failed - continuing with other adapters")

    if adapter_registry is None:
        adapter_settings = dataclasses.replace(_EnvAdapterSettings(), missionnet_base_url=base_url)
        adapter_registry = build_adapter_registry(adapter_settings, scenario_id=scenario_id)

    async with SessionLocal() as session:
        ingestion_results = await ingest_all(session, adapter_registry)

    async with SessionLocal() as session:
        detection_result = await run_detection_engine(session)

    async with SessionLocal() as session:
        incident_result = await run_incident_correlation(session)

    result = PipelineResult(
        assets_synced=asset_count,
        ingestion=[r.__dict__ for r in ingestion_results],
        detections_created=detection_result.detections_created,
        detections_skipped_duplicate=detection_result.detections_skipped_duplicate,
        incidents_created=incident_result.incidents_created,
        incidents_updated=incident_result.incidents_updated,
    )
    logger.info("ingestion cycle complete: %s", result.as_dict())
    return result
