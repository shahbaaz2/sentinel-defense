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
    ResponsePlan,
    SentinelAsset,
)

_DELETE_ORDER = (
    # ResponsePlan FKs into both AIAssessment and Incident - must precede them both. Whenever a
    # new table gets a foreign key into incidents/detections/normalized_events/ai_assessments,
    # add it here BEFORE its target - this has been a real, recurring bug (see DECISIONS.md).
    ResponsePlan,
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
