"""Runs every enabled `Rule` against a recent window of normalized events and persists any new
matches as `Detection` rows. Idempotent: re-running against unchanged data creates nothing new,
because each candidate's dedupe_key (rule_id + exact evidence event IDs) is stable.
"""

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.models.orm import Detection, DetectionEventLink, NormalizedEventRecord, SentinelAsset
from services.detection_engine.rules import RULES, EventView, RuleCandidate

DEFAULT_LOOKBACK = timedelta(hours=24)


@dataclass
class DetectionRunResult:
    events_considered: int
    detections_created: int
    detections_skipped_duplicate: int


def _dedupe_key(rule_id: str, event_ids: list[str]) -> str:
    canonical = rule_id + "|" + ",".join(sorted(event_ids))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def _load_recent_events(session: AsyncSession, lookback: timedelta) -> list[EventView]:
    since = datetime.now(UTC) - lookback
    stmt = select(NormalizedEventRecord).where(NormalizedEventRecord.timestamp >= since)
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [
        EventView(
            event_id=r.event_id,
            timestamp=r.timestamp,
            event_type=r.event_type,
            event_category=r.event_category,
            severity=r.severity,
            asset_id=r.asset_id,
            user_id=r.user_id,
            scenario_id=r.scenario_id,
        )
        for r in rows
    ]


async def _load_asset_criticality(session: AsyncSession) -> dict[str, int]:
    result = await session.execute(select(SentinelAsset))
    return {a.external_asset_id: a.criticality for a in result.scalars().all()}


async def _persist_candidate(
    session: AsyncSession, rule, candidate: RuleCandidate
) -> bool:
    dedupe_key = _dedupe_key(rule.rule_id, candidate.event_ids)
    existing = await session.execute(select(Detection).where(Detection.dedupe_key == dedupe_key))
    if existing.scalar_one_or_none() is not None:
        return False

    detection_id = f"DET-{uuid.uuid4()}"
    session.add(
        Detection(
            detection_id=detection_id,
            rule_id=rule.rule_id,
            rule_version=rule.version,
            rule_name=rule.name,
            severity=candidate.severity,
            asset_id=candidate.asset_id,
            correlation_key=candidate.asset_id or candidate.user_id,
            mitre_techniques=rule.mitre_techniques,
            evidence_summary=candidate.evidence_summary,
            dedupe_key=dedupe_key,
        )
    )
    for event_id in candidate.event_ids:
        session.add(DetectionEventLink(detection_id=detection_id, event_id=event_id))
    return True


async def run_detection_engine(
    session: AsyncSession, lookback: timedelta = DEFAULT_LOOKBACK
) -> DetectionRunResult:
    events = await _load_recent_events(session, lookback)
    criticality = await _load_asset_criticality(session)

    created = skipped = 0
    for rule in RULES:
        candidates = rule.evaluate(events, criticality)
        for candidate in candidates:
            if await _persist_candidate(session, rule, candidate):
                created += 1
            else:
                skipped += 1

    await session.commit()
    return DetectionRunResult(
        events_considered=len(events),
        detections_created=created,
        detections_skipped_duplicate=skipped,
    )
