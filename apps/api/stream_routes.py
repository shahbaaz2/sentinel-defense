"""One shared Server-Sent-Events feed for the whole dashboard, instead of every page polling
independently (Phase 4 requirement - see DECISIONS.md for the SSE-vs-polling rationale). A single
browser tab opens one `EventSource`; every page that needs live data reads from the same stream via
a shared client-side provider (`apps/dashboard/app/LiveDataProvider.tsx`).

The server re-queries the database every `SNAPSHOT_INTERVAL_SECONDS` and pushes a fresh JSON
snapshot - simple, bounded, and easy to reason about at this data volume (blueprint §28.1: hundreds
to low thousands of events, not a high-throughput stream). `EventSource` reconnects automatically on
its own if a connection drops, which is what satisfies the "reconnect behavior" requirement without
any custom client-side retry logic.
"""

import asyncio
import json
import logging

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select

from domain.db import SessionLocal
from domain.incidents import TERMINAL_INCIDENT_STATUSES
from domain.models.orm import (
    Detection,
    Incident,
    IncidentDetectionLink,
    NormalizedEventRecord,
    SentinelAsset,
)

logger = logging.getLogger("sentinel.stream")
router = APIRouter(prefix="/api/v1")

SNAPSHOT_INTERVAL_SECONDS = 2.0
MISSIONNET_BASE_URL = "http://127.0.0.1:8090"


async def _build_snapshot() -> dict:
    async with SessionLocal() as session:
        protected_assets_stmt = select(func.count(SentinelAsset.id))
        protected_assets = (await session.execute(protected_assets_stmt)).scalar_one()
        normalized_events = (
            await session.execute(select(func.count(NormalizedEventRecord.event_id)))
        ).scalar_one()
        active_detections = (
            await session.execute(
                select(func.count(Detection.detection_id)).where(Detection.status == "open")
            )
        ).scalar_one()
        open_incidents = (
            await session.execute(
                select(func.count(Incident.incident_id)).where(
                    Incident.status.not_in(TERMINAL_INCIDENT_STATUSES)
                )
            )
        ).scalar_one()
        last_ingestion_at = (
            await session.execute(select(func.max(NormalizedEventRecord.ingestion_timestamp)))
        ).scalar_one()

        recent_incidents_result = await session.execute(
            select(Incident).order_by(Incident.last_seen.desc()).limit(20)
        )
        recent_incidents = []
        for incident in recent_incidents_result.scalars().all():
            count_result = await session.execute(
                select(func.count(IncidentDetectionLink.detection_id)).where(
                    IncidentDetectionLink.incident_id == incident.incident_id
                )
            )
            recent_incidents.append(
                {
                    "incident_id": incident.incident_id,
                    "title": incident.title,
                    "severity": incident.severity,
                    "status": incident.status,
                    "primary_asset_id": incident.primary_asset_id,
                    "first_seen": incident.first_seen.isoformat(),
                    "detection_count": count_result.scalar_one(),
                }
            )

    missionnet_reachable = False
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{MISSIONNET_BASE_URL}/health")
            missionnet_reachable = resp.status_code == 200
    except httpx.HTTPError:
        missionnet_reachable = False

    return {
        "metrics": {
            "protected_assets": protected_assets,
            "normalized_events": normalized_events,
            "active_detections": active_detections,
            "open_incidents": open_incidents,
            "last_ingestion_at": last_ingestion_at.isoformat() if last_ingestion_at else None,
        },
        "missionnet_reachable": missionnet_reachable,
        "recent_incidents": recent_incidents,
    }


@router.get("/stream")
async def stream(request: Request) -> StreamingResponse:
    async def event_generator():
        while True:
            if await request.is_disconnected():
                logger.debug("SSE client disconnected")
                break
            try:
                snapshot = await _build_snapshot()
                yield f"event: snapshot\ndata: {json.dumps(snapshot)}\n\n"
            except Exception:
                logger.exception("failed to build SSE snapshot")
            await asyncio.sleep(SNAPSHOT_INTERVAL_SECONDS)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
