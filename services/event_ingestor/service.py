"""Pulls from an `EventSourceAdapter`, normalizes, and persists - idempotently, with per-stream
cursor tracking so a restart resumes rather than reprocessing (blueprint §8.2, Phase 2 requirement).
"""

import hashlib
import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from domain.audit import write_audit
from domain.models.orm import IngestionCursor, NormalizedEventRecord, RawEvent, SentinelAsset
from integrations.missionnet.mapper import UnmappedEventTypeError, normalize_missionnet_event
from services.event_ingestor.ports import EventSourceAdapter, RawSourceEvent

logger = logging.getLogger("sentinel.event_ingestor")

_MAPPERS = {
    "missionnet": normalize_missionnet_event,
}


@dataclass
class IngestionResult:
    source: str
    stream: str
    fetched: int
    ingested: int
    skipped_duplicate: int
    skipped_unmapped: int


async def _get_cursor(session: AsyncSession, source: str, stream: str) -> datetime | None:
    cursor = await session.get(IngestionCursor, {"source": source, "stream": stream})
    return cursor.last_timestamp if cursor else None


async def _advance_cursor(
    session: AsyncSession, source: str, stream: str, new_cursor: datetime
) -> None:
    stmt = pg_insert(IngestionCursor).values(
        source=source, stream=stream, last_timestamp=new_cursor
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["source", "stream"], set_={"last_timestamp": new_cursor}
    )
    await session.execute(stmt)


def _raw_event_sha256(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def ingest_stream(
    session: AsyncSession,
    adapter: EventSourceAdapter,
    *,
    source: str,
    stream: str,
) -> IngestionResult:
    mapper = _MAPPERS.get(source)
    if mapper is None:
        raise UnmappedEventTypeError(f"no mapper registered for source {source!r}")

    since = await _get_cursor(session, source, stream)
    batch = await adapter.fetch_events(since=since)

    # Two explicit passes rather than one add-both-then-flush loop: RawEvent and
    # NormalizedEventRecord have a plain FK column but no declared ORM relationship() between
    # them, so SQLAlchemy's unit-of-work has no dependency edge to order their inserts by - it can
    # (and did, empirically) flush normalized_events before raw_events in the same flush,
    # violating the FK. Flushing every needed RawEvent first guarantees the target rows exist
    # before any NormalizedEventRecord referencing them is even added.
    to_insert: list[tuple[RawSourceEvent, dict, str]] = []
    skipped_duplicate = 0
    with session.no_autoflush:
        for raw in batch.events:
            normalized = mapper(raw)
            existing = await session.get(NormalizedEventRecord, normalized["event_id"])
            if existing is not None:
                skipped_duplicate += 1
                continue
            raw_event_id = f"{source}-{raw.stream}-{raw.source_event_id}"
            to_insert.append((raw, normalized, raw_event_id))

        for raw, _normalized, raw_event_id in to_insert:
            if await session.get(RawEvent, raw_event_id) is None:
                session.add(
                    RawEvent(
                        raw_event_id=raw_event_id,
                        source=source,
                        payload=raw.payload,
                        sha256=_raw_event_sha256(raw.payload),
                    )
                )
    await session.flush()

    for _raw, normalized, raw_event_id in to_insert:
        session.add(NormalizedEventRecord(raw_event_ref=raw_event_id, **normalized))

    if batch.next_cursor is not None:
        await _advance_cursor(session, source, stream, batch.next_cursor)

    if to_insert:
        await write_audit(
            session,
            entity_type="ingestion",
            entity_id=f"{source}:{stream}",
            action="ingestion.cycle_completed",
            detail={"fetched": len(batch.events), "ingested": len(to_insert)},
        )

    await session.commit()

    return IngestionResult(
        source=source,
        stream=stream,
        fetched=len(batch.events),
        ingested=len(to_insert),
        skipped_duplicate=skipped_duplicate,
        skipped_unmapped=0,
    )


async def sync_missionnet_assets(session: AsyncSession, base_url: str) -> int:
    """Upserts Sentinel's own `assets` table from MissionNet's `/assets` - the source of truth for
    criticality (used by DET-002) and for Sentinel's own `/api/v1/assets` endpoint. Not part of the
    event stream: assets don't have a stable "event" identity, just current state."""
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        resp = await client.get("/assets")
        resp.raise_for_status()
        assets: list[dict] = resp.json()

    now = datetime.now(UTC)
    for asset in assets:
        sentinel_id = f"missionnet:{asset['asset_id']}"
        stmt = pg_insert(SentinelAsset).values(
            id=sentinel_id,
            external_asset_id=asset["asset_id"],
            source="missionnet",
            name=asset["name"],
            asset_type=asset["asset_type"],
            environment="lab",
            criticality=asset["criticality"],
            status=asset["status"],
            first_seen_at=now,
            last_seen_at=now,
            extra={"mission_role": asset["mission_role"], "network_state": asset["network_state"]},
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "name": asset["name"],
                "asset_type": asset["asset_type"],
                "criticality": asset["criticality"],
                "status": asset["status"],
                "last_seen_at": now,
                "extra": {
                    "mission_role": asset["mission_role"],
                    "network_state": asset["network_state"],
                },
            },
        )
        await session.execute(stmt)

    await session.commit()
    return len(assets)


async def ingest_all(
    session: AsyncSession, adapters: Mapping[str, EventSourceAdapter]
) -> list[IngestionResult]:
    """`adapters` keys are `stream` names; all assumed to be the same `source` for now
    (MissionNet). Extending to multiple sources means calling this once per source with its own
    adapter map."""
    results = []
    for stream, adapter in adapters.items():
        results.append(await ingest_stream(session, adapter, source="missionnet", stream=stream))
    return results
