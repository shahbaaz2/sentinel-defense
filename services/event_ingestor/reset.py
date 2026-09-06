"""`make sentinel-reset`: clears Sentinel's own ingested/derived state (events, detections,
incidents, cursors, synced assets) without touching MissionNet. Pair with `make reset-lab` to get
back to a fully pristine two-system baseline for a repeatable demo.
"""

import asyncio

from sqlalchemy import delete

from domain.db import SessionLocal
from domain.models.orm import (
    Detection,
    DetectionEventLink,
    Incident,
    IncidentDetectionLink,
    IncidentEventLink,
    IngestionCursor,
    NormalizedEventRecord,
    RawEvent,
    SentinelAsset,
)

_DELETE_ORDER = (
    IncidentEventLink,
    IncidentDetectionLink,
    DetectionEventLink,
    Incident,
    Detection,
    NormalizedEventRecord,
    RawEvent,
    IngestionCursor,
    SentinelAsset,
)


async def reset() -> None:
    async with SessionLocal() as session:
        for model in _DELETE_ORDER:
            await session.execute(delete(model))
        await session.commit()
    print("Sentinel ingestion/detection/incident state cleared.")


if __name__ == "__main__":
    asyncio.run(reset())
