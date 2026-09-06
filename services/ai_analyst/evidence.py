"""Builds the curated Evidence Pack the AI Analyst is allowed to see (blueprint AI Analyst §6).

The model never gets raw database access. It gets exactly: this incident's own fields, its exact
detections, its exact normalized events, the affected asset's context, and whatever ATT&CK
technique IDs deterministic code has already attached - nothing else, and no unbounded query.
"""

import hashlib
import json
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.models.orm import (
    Detection,
    DetectionEventLink,
    IncidentDetectionLink,
    IncidentEventLink,
    NormalizedEventRecord,
    SentinelAsset,
)
from domain.models.orm import Incident as IncidentRow


class EvidenceEvent(BaseModel):
    """Every field below may have been influenced by an attacker (blueprint AI Analyst §7) - the
    AI Analyst's system prompt is responsible for treating this as data, not instructions."""

    event_id: str
    timestamp: datetime
    source: str
    event_category: str
    event_type: str
    severity: str
    asset_id: str | None
    user_id: str | None
    summary: str
    src_ip: str | None = None
    dst_ip: str | None = None
    process_name: str | None = None
    technique_ids: list[str] = []


class EvidenceDetection(BaseModel):
    detection_id: str
    rule_id: str
    rule_name: str
    severity: str
    confidence: float
    evidence_summary: str
    mitre_techniques: list[str]
    event_ids: list[str]


class EvidenceAsset(BaseModel):
    asset_id: str
    name: str
    asset_type: str
    environment: str
    criticality: int
    status: str


class EvidencePack(BaseModel):
    incident_id: str
    incident_title: str
    incident_severity: str
    incident_status: str
    incident_category: str
    incident_summary: str
    primary_asset_id: str | None
    scenario_id: str | None
    first_seen: datetime
    last_seen: datetime
    asset_context: EvidenceAsset | None
    detections: list[EvidenceDetection]
    events: list[EvidenceEvent]
    known_attack_techniques: list[str]
    available_playbook_ids: list[str] = []
    """Phase 5: no playbooks are shipped yet, so this is always empty and the AI Analyst's system
    prompt requires recommended_playbook_id to be null whenever it is. Phase 6+ populates this
    from a real playbook catalog."""


def _pack_hash(pack: EvidencePack) -> str:
    canonical = pack.model_dump_json(exclude_none=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def build_evidence_pack(session: AsyncSession, incident_id: str) -> EvidencePack | None:
    incident = await session.get(IncidentRow, incident_id)
    if incident is None:
        return None

    detection_ids = [
        row[0]
        for row in (
            await session.execute(
                select(IncidentDetectionLink.detection_id).where(
                    IncidentDetectionLink.incident_id == incident_id
                )
            )
        ).all()
    ]
    event_ids = [
        row[0]
        for row in (
            await session.execute(
                select(IncidentEventLink.event_id).where(
                    IncidentEventLink.incident_id == incident_id
                )
            )
        ).all()
    ]

    detections: list[EvidenceDetection] = []
    known_techniques: set[str] = set(incident.mitre_techniques or [])
    for detection_id in detection_ids:
        d = await session.get(Detection, detection_id)
        if d is None:
            continue
        d_event_ids = [
            row[0]
            for row in (
                await session.execute(
                    select(DetectionEventLink.event_id).where(
                        DetectionEventLink.detection_id == detection_id
                    )
                )
            ).all()
        ]
        known_techniques.update(d.mitre_techniques or [])
        detections.append(
            EvidenceDetection(
                detection_id=d.detection_id,
                rule_id=d.rule_id,
                rule_name=d.rule_name,
                severity=d.severity,
                confidence=d.confidence,
                evidence_summary=d.evidence_summary,
                mitre_techniques=d.mitre_techniques or [],
                event_ids=d_event_ids,
            )
        )

    events: list[EvidenceEvent] = []
    for event_id in event_ids:
        e = await session.get(NormalizedEventRecord, event_id)
        if e is None:
            continue
        events.append(
            EvidenceEvent(
                event_id=e.event_id,
                timestamp=e.timestamp,
                source=e.source,
                event_category=e.event_category,
                event_type=e.event_type,
                severity=e.severity,
                asset_id=e.asset_id,
                user_id=e.user_id,
                summary=e.summary,
                src_ip=e.src_ip,
                dst_ip=e.dst_ip,
                process_name=e.process_name,
                technique_ids=e.technique_ids or [],
            )
        )
        known_techniques.update(e.technique_ids or [])
    events.sort(key=lambda e: e.timestamp)

    asset_context: EvidenceAsset | None = None
    if incident.primary_asset_id:
        asset_row = (
            await session.execute(
                select(SentinelAsset).where(
                    SentinelAsset.external_asset_id == incident.primary_asset_id
                )
            )
        ).scalars().first()
        if asset_row is not None:
            asset_context = EvidenceAsset(
                asset_id=asset_row.external_asset_id,
                name=asset_row.name,
                asset_type=asset_row.asset_type,
                environment=asset_row.environment,
                criticality=asset_row.criticality,
                status=asset_row.status,
            )

    pack = EvidencePack(
        incident_id=incident.incident_id,
        incident_title=incident.title,
        incident_severity=incident.severity,
        incident_status=incident.status,
        incident_category=incident.category,
        incident_summary=incident.summary,
        primary_asset_id=incident.primary_asset_id,
        scenario_id=incident.scenario_id,
        first_seen=incident.first_seen,
        last_seen=incident.last_seen,
        asset_context=asset_context,
        detections=detections,
        events=events,
        known_attack_techniques=sorted(known_techniques),
        available_playbook_ids=[],
    )
    return pack


def evidence_pack_hash(pack: EvidencePack) -> str:
    return _pack_hash(pack)


def evidence_pack_to_model_input(pack: EvidencePack) -> dict:
    """The exact dict handed to the LLM provider - JSON round-tripped so datetimes serialize the
    same way every time (used both for the prompt and for hashing consistency checks in tests)."""
    return json.loads(pack.model_dump_json())
