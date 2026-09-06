"""`make sentinel-reset`: clears Sentinel's own ingested/derived state (events, detections,
incidents, cursors, synced assets) without touching MissionNet. Pair with `make reset-lab` to get
back to a fully pristine two-system baseline for a repeatable demo.
"""

import asyncio

from sqlalchemy import delete

from domain.db import SessionLocal
from domain.models.orm import (
    AIAssessment,
    AuditLogEntry,
    Detection,
    DetectionEventLink,
    Incident,
    IncidentDetectionLink,
    IncidentEventLink,
    IncidentNote,
    IngestionCursor,
    NormalizedEventRecord,
    RawEvent,
    SentinelAsset,
)

_DELETE_ORDER = (
    AIAssessment,
    IncidentNote,
    IncidentEventLink,
    IncidentDetectionLink,
    DetectionEventLink,
    Incident,
    Detection,
    NormalizedEventRecord,
    RawEvent,
    IngestionCursor,
    SentinelAsset,
    AuditLogEntry,
)


async def reset() -> None:
    async with SessionLocal() as session:
        for model in _DELETE_ORDER:
            await session.execute(delete(model))
        await session.commit()
    print("Sentinel ingestion/detection/incident state cleared.")


if __name__ == "__main__":
    asyncio.run(reset())
