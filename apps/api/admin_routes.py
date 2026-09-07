"""Internal operational endpoints - not SOC-analyst-facing.

These exist so the Demo Control Plane (Phase 3) can drive Sentinel's real pipeline over HTTP
without importing Sentinel's internals or a subprocess/CLI call. Both simply call the exact same
functions `make ingest-once` / `make sentinel-reset` already use - no new logic, no shortcut that
bypasses the adapter/normalizer/detection/incident engine, and no function that creates an
event/detection/incident directly.
"""

from fastapi import APIRouter, Query

from apps.api.config import settings
from services.event_ingestor.pipeline import run_ingestion_cycle
from services.event_ingestor.registry import build_adapter_registry
from services.event_ingestor.reset import reset as reset_sentinel_state

router = APIRouter(prefix="/api/v1", tags=["admin"])


@router.post("/ingest/run")
async def trigger_ingestion_cycle(scenario_id: str | None = Query(default=None)):
    """`scenario_id` is only needed for a scenario with no MissionNet step of its own to carry
    provenance (e.g. SCN-NET-001) - a MissionNet-driven scenario's events already carry their
    scenario_id from MissionNet's own audit trail without this parameter (see
    integrations/missionnet/mapper.py). The sensor-adapter registry is built here, from the real
    `apps.api.config.settings` (parsed from `.env`), and passed down explicitly - `services/`
    itself never reads `apps.api.config` (see services/event_ingestor/registry.py)."""
    registry = build_adapter_registry(settings, scenario_id=scenario_id)
    result = await run_ingestion_cycle(
        base_url=settings.missionnet_base_url, scenario_id=scenario_id, adapter_registry=registry
    )
    return result.as_dict()


@router.post("/admin/reset")
async def reset_sentinel():
    await reset_sentinel_state()
    return {"status": "reset"}
