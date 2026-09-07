"""Pulls from an `EventSourceAdapter`, normalizes, and persists - idempotently, with per-stream
cursor tracking so a restart resumes rather than reprocessing (blueprint §8.2, Phase 2 requirement).
"""

import hashlib
import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from domain.audit import write_audit
from domain.models.orm import (
    IngestionAdapterStatus,
    IngestionCursor,
    NormalizedEventRecord,
    RawEvent,
    SentinelAsset,
)
from integrations.falco.mapper import normalize_falco_event
from integrations.missionnet.mapper import UnmappedEventTypeError, normalize_missionnet_event
from integrations.suricata.mapper import normalize_suricata_event
from integrations.wazuh.mapper import normalize_wazuh_event
from integrations.zeek.mapper import normalize_zeek_event
from services.event_ingestor.ports import EventSourceAdapter, RawSourceEvent
from services.event_ingestor.registry import AdapterDescriptor

logger = logging.getLogger("sentinel.event_ingestor")

# One mapper per source with a fixed `(raw) -> dict` signature. Splunk is the sole exception - its
# normalizer needs a per-deployment field-mapping profile, so a SplunkAdapter instance carries its
# own bound `.mapper` attribute instead of registering here (see integrations/splunk/adapter.py and
# `_resolve_mapper` below).
_MAPPERS = {
    "missionnet": normalize_missionnet_event,
    "suricata": normalize_suricata_event,
    "zeek": normalize_zeek_event,
    "wazuh": normalize_wazuh_event,
    "falco": normalize_falco_event,
}


def _resolve_mapper(source: str, adapter: EventSourceAdapter):
    per_instance_mapper = getattr(adapter, "mapper", None)
    if per_instance_mapper is not None:
        return per_instance_mapper
    return _MAPPERS.get(source)


@dataclass
class IngestionResult:
    source: str
    stream: str
    fetched: int
    ingested: int
    skipped_duplicate: int
    skipped_unmapped: int
    error: str | None = None
    """Phase 8: set when this one adapter/stream failed - the ingestion cycle still runs every
    other adapter (see `ingest_all`'s per-adapter error isolation)."""


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


async def _record_ingestion_success(session: AsyncSession, source: str, stream: str) -> None:
    now = datetime.now(UTC)
    stmt = pg_insert(IngestionAdapterStatus).values(
        source=source, stream=stream, last_attempt_at=now, last_success_at=now, last_error=None
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["source", "stream"],
        set_={"last_attempt_at": now, "last_success_at": now, "last_error": None},
    )
    await session.execute(stmt)
    await session.commit()


async def _record_ingestion_failure(
    session: AsyncSession, source: str, stream: str, error: str
) -> None:
    now = datetime.now(UTC)
    stmt = pg_insert(IngestionAdapterStatus).values(
        source=source, stream=stream, last_attempt_at=now, last_success_at=None, last_error=error
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["source", "stream"], set_={"last_attempt_at": now, "last_error": error}
    )
    await session.execute(stmt)
    await session.commit()


async def ingest_stream(
    session: AsyncSession,
    adapter: EventSourceAdapter,
    *,
    source: str,
    stream: str,
) -> IngestionResult:
    mapper = _resolve_mapper(source, adapter)
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
    await _record_ingestion_success(session, source, stream)

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
    session: AsyncSession, descriptors: Iterable[AdapterDescriptor]
) -> list[IngestionResult]:
    """Runs every enabled adapter's every stream. Phase 8 requirement: one failing adapter/stream
    must never stop the others - each stream's `ingest_stream` call is individually wrapped, and a
    failure is reported as an `IngestionResult` with `error` set (fetched/ingested left at 0)
    rather than propagating and aborting the whole cycle."""
    results: list[IngestionResult] = []
    for descriptor in descriptors:
        if not descriptor.enabled:
            continue
        for stream, adapter in descriptor.streams.items():
            try:
                results.append(
                    await ingest_stream(
                        session, adapter, source=descriptor.adapter_id, stream=stream
                    )
                )
            except Exception as exc:  # noqa: BLE001 - isolate one adapter's failure from the rest
                logger.exception(
                    "ingestion failed for source=%s stream=%s", descriptor.adapter_id, stream
                )
                await session.rollback()
                error_message = str(exc) or f"{type(exc).__name__} (no message)"
                await _record_ingestion_failure(
                    session, descriptor.adapter_id, stream, error_message
                )
                results.append(
                    IngestionResult(
                        source=descriptor.adapter_id,
                        stream=stream,
                        fetched=0,
                        ingested=0,
                        skipped_duplicate=0,
                        skipped_unmapped=0,
                        error=error_message,
                    )
                )
    return results
