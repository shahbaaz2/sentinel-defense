"""`make sentinel-reset`: clears Sentinel's own ingested/derived state (events, detections,
incidents, cursors, synced assets) without touching MissionNet. Pair with `make reset-lab` to get
back to a fully pristine two-system baseline for a repeatable demo.

This is the one reset path every caller goes through - the bash script, `make sentinel-reset`, and
`POST /api/v1/admin/reset` (which every Demo Control scenario's own automatic `lab_reset` calls
before it runs, not just the top-level scripts). That is why the Phase 8 sensor-lab file cleanup
below lives here rather than only in scripts/reset-lab.sh: a DB-only reset would leave a stale
eve.json/Zeek log on disk that the next unrelated scenario's ingestion cycle re-ingests (with a
freshly-cleared cursor), fabricating a spurious network-intrusion incident interleaved with that
scenario's own real one - a real bug this phase found and fixed (see DECISIONS.md).
"""

import asyncio
import os
import shutil
from pathlib import Path

from sqlalchemy import delete

from domain.db import SessionLocal
from domain.models.orm import (
    ActionResult,
    AIAssessment,
    AuditLogEntry,
    Detection,
    DetectionEventLink,
    Incident,
    IncidentDetectionLink,
    IncidentEventLink,
    IncidentNote,
    IngestionAdapterStatus,
    IngestionCursor,
    NormalizedEventRecord,
    RawEvent,
    ResponsePlan,
    SentinelAsset,
)

_DELETE_ORDER = (
    # ActionResult FKs into ResponsePlan, which FKs into both AIAssessment and Incident - each
    # must precede what it points to. Whenever a new table gets a foreign key into
    # incidents/detections/normalized_events/ai_assessments/response_plans, add it here BEFORE
    # its target - this has been a real, recurring bug (see DECISIONS.md).
    ActionResult,
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
    IngestionAdapterStatus,
    SentinelAsset,
    AuditLogEntry,
)


def _clear_sensor_lab_output() -> None:
    """Removes generated Suricata eve.json / Zeek log output (not the rules/www fixtures, which
    services/sensor_lab/pipeline.py regenerates fresh on every run anyway). Uses the same env
    vars apps.api.config.Settings reads, directly - services/ never imports apps/."""
    eve_path = Path(
        os.environ.get("SENTINEL_SURICATA_EVE_PATH", "var/sensor-lab/suricata-out/eve.json")
    )
    zeek_log_dir = Path(os.environ.get("SENTINEL_ZEEK_LOG_DIR", "var/sensor-lab/zeek-out"))
    shutil.rmtree(eve_path.parent, ignore_errors=True)
    shutil.rmtree(zeek_log_dir, ignore_errors=True)


async def reset() -> None:
    async with SessionLocal() as session:
        for model in _DELETE_ORDER:
            await session.execute(delete(model))
        await session.commit()
    _clear_sensor_lab_output()
    print("Sentinel ingestion/detection/incident state cleared.")


if __name__ == "__main__":
    asyncio.run(reset())
