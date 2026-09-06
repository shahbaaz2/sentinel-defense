"""CLI entrypoints backing `make ingest-once` / `make ingest-watch` / `make sentinel-reset`.

One full cycle is: sync assets -> ingest audit+telemetry streams -> run detection engine -> run
incident correlation. Each step is independently idempotent, so re-running (or watch-mode's
repeated polling) never duplicates data.
"""

import argparse
import asyncio
import logging
import os

from domain.db import Base, SessionLocal, engine
from domain.models import orm  # noqa: F401 - registers tables on Base.metadata
from integrations.missionnet.adapter import missionnet_audit_adapter, missionnet_telemetry_adapter
from services.detection_engine.engine import run_detection_engine
from services.event_ingestor.service import ingest_all, sync_missionnet_assets
from services.incident_engine.engine import run_incident_correlation

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("sentinel.ingest_cli")

MISSIONNET_BASE_URL = os.environ.get("MISSIONNET_BASE_URL", "http://127.0.0.1:8090")


async def run_once() -> dict:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as session:
        asset_count = await sync_missionnet_assets(session, MISSIONNET_BASE_URL)

    async with SessionLocal() as session:
        adapters = {
            "audit": missionnet_audit_adapter(MISSIONNET_BASE_URL),
            "telemetry": missionnet_telemetry_adapter(MISSIONNET_BASE_URL),
        }
        ingestion_results = await ingest_all(session, adapters)

    async with SessionLocal() as session:
        detection_result = await run_detection_engine(session)

    async with SessionLocal() as session:
        incident_result = await run_incident_correlation(session)

    summary = {
        "assets_synced": asset_count,
        "ingestion": [r.__dict__ for r in ingestion_results],
        "detections_created": detection_result.detections_created,
        "incidents_created": incident_result.incidents_created,
        "incidents_updated": incident_result.incidents_updated,
    }
    logger.info("ingestion cycle complete: %s", summary)
    return summary


async def run_watch(interval_seconds: float) -> None:
    logger.info("starting ingestion watch loop, interval=%ss", interval_seconds)
    while True:
        try:
            await run_once()
        except Exception:
            logger.exception("ingestion cycle failed - will retry next interval")
        await asyncio.sleep(interval_seconds)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run-once")
    watch_parser = sub.add_parser("run-watch")
    watch_parser.add_argument("--interval", type=float, default=5.0)
    args = parser.parse_args()

    if args.command == "run-once":
        asyncio.run(run_once())
    elif args.command == "run-watch":
        asyncio.run(run_watch(args.interval))


if __name__ == "__main__":
    main()
