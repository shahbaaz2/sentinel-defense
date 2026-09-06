"""The one full Sentinel ingestion cycle: sync assets -> ingest audit+telemetry -> deterministic
detection -> deterministic correlation. Every caller (the CLI, `make ingest-watch`, and Phase 3's
Demo Control Plane triggering it over HTTP) goes through this exact same function, so there is
never a second, divergent code path that skips the adapter/normalizer/detection/incident engine.
"""

import logging
import os
from dataclasses import asdict, dataclass

from domain.db import Base, SessionLocal, engine
from domain.models import orm  # noqa: F401 - registers tables on Base.metadata
from integrations.missionnet.adapter import missionnet_audit_adapter, missionnet_telemetry_adapter
from services.detection_engine.engine import run_detection_engine
from services.event_ingestor.service import ingest_all, sync_missionnet_assets
from services.incident_engine.engine import run_incident_correlation

logger = logging.getLogger("sentinel.ingest_pipeline")

MISSIONNET_BASE_URL = os.environ.get("MISSIONNET_BASE_URL", "http://127.0.0.1:8090")


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


async def run_ingestion_cycle(base_url: str = MISSIONNET_BASE_URL) -> PipelineResult:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as session:
        asset_count = await sync_missionnet_assets(session, base_url)

    async with SessionLocal() as session:
        adapters = {
            "audit": missionnet_audit_adapter(base_url),
            "telemetry": missionnet_telemetry_adapter(base_url),
        }
        ingestion_results = await ingest_all(session, adapters)

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
