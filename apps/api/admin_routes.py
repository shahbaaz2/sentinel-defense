"""Internal operational endpoints - not SOC-analyst-facing.

These exist so the Demo Control Plane (Phase 3) can drive Sentinel's real pipeline over HTTP
without importing Sentinel's internals or a subprocess/CLI call. Both simply call the exact same
functions `make ingest-once` / `make sentinel-reset` already use - no new logic, no shortcut that
bypasses the adapter/normalizer/detection/incident engine, and no function that creates an
event/detection/incident directly.
"""

from fastapi import APIRouter

from services.event_ingestor.pipeline import run_ingestion_cycle
from services.event_ingestor.reset import reset as reset_sentinel_state

router = APIRouter(prefix="/api/v1", tags=["admin"])


@router.post("/ingest/run")
async def trigger_ingestion_cycle():
    result = await run_ingestion_cycle()
    return result.as_dict()


@router.post("/admin/reset")
async def reset_sentinel():
    await reset_sentinel_state()
    return {"status": "reset"}
