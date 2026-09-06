"""Detections are not incidents. This module correlates open, unlinked detections into incidents
using only deterministic attributes (same asset or same identity, within a bounded time window) -
never an LLM judgment call (blueprint §9, Phase 2 requirement).
"""

from dataclasses import dataclass
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.audit import write_audit
from domain.incidents import TERMINAL_INCIDENT_STATUSES
from domain.models.orm import (
    Detection,
    DetectionEventLink,
    Incident,
    IncidentDetectionLink,
    IncidentEventLink,
    NormalizedEventRecord,
)
from services.detection_engine.rules import RULES

CORRELATION_WINDOW = timedelta(minutes=10)
_SEVERITY_RANK = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
_RULE_BY_ID = {r.rule_id: r for r in RULES}


@dataclass
class IncidentRunResult:
    detections_considered: int
    incidents_created: int
    incidents_updated: int


def _max_severity(a: str, b: str) -> str:
    return a if _SEVERITY_RANK.get(a, 0) >= _SEVERITY_RANK.get(b, 0) else b


async def _unlinked_open_detections(session: AsyncSession) -> list[Detection]:
    linked_ids_result = await session.execute(select(IncidentDetectionLink.detection_id))
    linked_ids = {row[0] for row in linked_ids_result.all()}

    result = await session.execute(select(Detection).where(Detection.status == "open"))
    return [d for d in result.scalars().all() if d.detection_id not in linked_ids]


async def _find_mergeable_incident(
    session: AsyncSession, correlation_key: str, detection: Detection
) -> Incident | None:
    result = await session.execute(
        select(Incident)
        .where(Incident.correlation_key == correlation_key)
        .where(Incident.status.not_in(TERMINAL_INCIDENT_STATUSES))
        .order_by(Incident.last_seen.desc())
    )
    for incident in result.scalars().all():
        if abs((detection.timestamp - incident.last_seen).total_seconds()) <= (
            CORRELATION_WINDOW.total_seconds()
        ):
            return incident
    return None


async def _link_detection_evidence(
    session: AsyncSession, incident_id: str, detection_id: str
) -> None:
    session.add(IncidentDetectionLink(incident_id=incident_id, detection_id=detection_id))
    event_links = await session.execute(
        select(DetectionEventLink.event_id).where(DetectionEventLink.detection_id == detection_id)
    )
    for (event_id,) in event_links.all():
        link_key = {"incident_id": incident_id, "event_id": event_id}
        existing = await session.get(IncidentEventLink, link_key)
        if existing is None:
            session.add(IncidentEventLink(incident_id=incident_id, event_id=event_id))


async def _detection_scenario_id(session: AsyncSession, detection_id: str) -> str | None:
    result = await session.execute(
        select(NormalizedEventRecord.scenario_id)
        .join(DetectionEventLink, DetectionEventLink.event_id == NormalizedEventRecord.event_id)
        .where(DetectionEventLink.detection_id == detection_id)
        .where(NormalizedEventRecord.scenario_id.is_not(None))
        .limit(1)
    )
    row = result.first()
    return row[0] if row else None


async def run_incident_correlation(session: AsyncSession) -> IncidentRunResult:
    detections = await _unlinked_open_detections(session)
    created = updated = 0

    # Oldest first so incidents accumulate in the order signals actually happened.
    for detection in sorted(detections, key=lambda d: d.timestamp):
        correlation_key = detection.correlation_key or detection.detection_id
        rule = _RULE_BY_ID.get(detection.rule_id)
        category = rule.category if rule else "uncategorized"

        incident = await _find_mergeable_incident(session, correlation_key, detection)
        scenario_id = await _detection_scenario_id(session, detection.detection_id)

        if incident is not None:
            incident.severity = _max_severity(incident.severity, detection.severity)
            incident.last_seen = max(incident.last_seen, detection.timestamp)
            incident.mitre_techniques = sorted(
                set(incident.mitre_techniques) | set(detection.mitre_techniques)
            )
            await _link_detection_evidence(session, incident.incident_id, detection.detection_id)
            await write_audit(
                session,
                entity_type="incident",
                entity_id=incident.incident_id,
                action="incident.detection_merged",
                scenario_id=scenario_id,
                detail={"detection_id": detection.detection_id, "rule_id": detection.rule_id},
            )
            updated += 1
        else:
            incident_id = f"INC-{uuid4()}"
            session.add(
                Incident(
                    incident_id=incident_id,
                    title=f"{detection.rule_name} ({correlation_key})",
                    severity=detection.severity,
                    primary_asset_id=detection.asset_id,
                    correlation_key=correlation_key,
                    category=category,
                    summary=detection.evidence_summary,
                    mitre_techniques=list(detection.mitre_techniques),
                    first_seen=detection.timestamp,
                    last_seen=detection.timestamp,
                    scenario_id=scenario_id,
                )
            )
            await _link_detection_evidence(session, incident_id, detection.detection_id)
            await write_audit(
                session,
                entity_type="incident",
                entity_id=incident_id,
                action="incident.created",
                scenario_id=scenario_id,
                detail={
                    "detection_id": detection.detection_id,
                    "rule_id": detection.rule_id,
                    "severity": detection.severity,
                },
            )
            created += 1

    await session.commit()
    return IncidentRunResult(
        detections_considered=len(detections), incidents_created=created, incidents_updated=updated
    )
