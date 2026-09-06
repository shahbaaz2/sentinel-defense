"""CLI entrypoints backing `make ingest-once` / `make ingest-watch`. See pipeline.py for the actual
ingestion cycle - this module is just process/argument plumbing around it.
"""

import argparse
import asyncio
import logging

from services.event_ingestor.pipeline import run_ingestion_cycle

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("sentinel.ingest_cli")


async def run_watch(interval_seconds: float) -> None:
    logger.info("starting ingestion watch loop, interval=%ss", interval_seconds)
    while True:
        try:
            await run_ingestion_cycle()
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
        asyncio.run(run_ingestion_cycle())
    elif args.command == "run-watch":
        asyncio.run(run_watch(args.interval))


if __name__ == "__main__":
    main()
