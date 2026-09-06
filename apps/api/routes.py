import uuid
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.schemas import (
    AssetDetailOut,
    AssetOut,
    DetectionOut,
    EventDetailOut,
    EventOut,
    IncidentAssignmentUpdate,
    IncidentDetailOut,
    IncidentDispositionUpdate,
    IncidentNoteCreate,
    IncidentNoteOut,
    IncidentOut,
    IncidentStatusUpdate,
    MetricsSummaryOut,
)
from domain.audit import write_audit
from domain.db import get_session
from domain.incidents import TERMINAL_INCIDENT_STATUSES
from domain.models.orm import (
    Detection,
    DetectionEventLink,
    Incident,
    IncidentDetectionLink,
    IncidentEventLink,
    IncidentNote,
    NormalizedEventRecord,
    RawEvent,
    SentinelAsset,
)

router = APIRouter(prefix="/api/v1")
MISSIONNET_BASE_URL = "http://127.0.0.1:8090"


# --------------------------------------------------------------------------------------------
# Assets
# --------------------------------------------------------------------------------------------


@router.get("/assets", response_model=list[AssetOut])
async def list_assets(
    criticality: int | None = Query(default=None, ge=1, le=5),
    status: str | None = Query(default=None),
    asset_type: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(SentinelAsset)
    if criticality is not None:
        stmt = stmt.where(SentinelAsset.criticality == criticality)
    if status:
        stmt = stmt.where(SentinelAsset.status == status)
    if asset_type:
        stmt = stmt.where(SentinelAsset.asset_type == asset_type)
    stmt = stmt.order_by(SentinelAsset.id)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.get("/assets/{asset_id}", response_model=AssetDetailOut)
async def get_asset(asset_id: str, session: AsyncSession = Depends(get_session)):
    asset = await session.get(SentinelAsset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="asset not found")

    active_incidents_stmt = (
        select(Incident)
        .where(Incident.primary_asset_id == asset.external_asset_id)
        .where(Incident.status.not_in(TERMINAL_INCIDENT_STATUSES))
    )
    active_incidents = (await session.execute(active_incidents_stmt)).scalars().all()

    active_detections_stmt = select(Detection).where(
        Detection.asset_id == asset.external_asset_id, Detection.status == "open"
    )
    active_detections = (await session.execute(active_detections_stmt)).scalars().all()

    recent_events_stmt = (
        select(NormalizedEventRecord)
        .where(NormalizedEventRecord.asset_id == asset.external_asset_id)
        .order_by(NormalizedEventRecord.timestamp.desc())
        .limit(10)
    )
    recent_events = (await session.execute(recent_events_stmt)).scalars().all()

    recent_incidents_stmt = (
        select(Incident)
        .where(Incident.primary_asset_id == asset.external_asset_id)
        .order_by(Incident.last_seen.desc())
        .limit(10)
    )
    recent_incidents = (await session.execute(recent_incidents_stmt)).scalars().all()

    base = AssetOut.model_validate(asset, from_attributes=True)
    return AssetDetailOut.model_validate(
        {
            **base.model_dump(),
            "active_incident_count": len(active_incidents),
            "active_detection_count": len(active_detections),
            "recent_events": [
                EventOut.model_validate(e, from_attributes=True) for e in recent_events
            ],
            "recent_detections": [
                DetectionOut.model_validate(d, from_attributes=True) for d in active_detections[:10]
            ],
            "recent_incidents": [
                IncidentOut.model_validate(i, from_attributes=True) for i in recent_incidents
            ],
            "related_identity": asset.extra.get("mission_role") if asset.extra else None,
        }
    )


# --------------------------------------------------------------------------------------------
# Events
# --------------------------------------------------------------------------------------------


@router.get("/events", response_model=list[EventOut])
async def list_events(
    severity: str | None = Query(default=None),
    source: str | None = Query(default=None),
    asset_id: str | None = Query(default=None),
    event_category: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    scenario_id: str | None = Query(default=None),
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(NormalizedEventRecord)
    if severity:
        stmt = stmt.where(NormalizedEventRecord.severity == severity)
    if source:
        stmt = stmt.where(NormalizedEventRecord.source == source)
    if asset_id:
        stmt = stmt.where(NormalizedEventRecord.asset_id == asset_id)
    if event_category:
        stmt = stmt.where(NormalizedEventRecord.event_category == event_category)
    if event_type:
        stmt = stmt.where(NormalizedEventRecord.event_type == event_type)
    if user_id:
        stmt = stmt.where(NormalizedEventRecord.user_id == user_id)
    if scenario_id:
        stmt = stmt.where(NormalizedEventRecord.scenario_id == scenario_id)
    if since:
        stmt = stmt.where(NormalizedEventRecord.timestamp >= since)
    if until:
        stmt = stmt.where(NormalizedEventRecord.timestamp <= until)
    stmt = stmt.order_by(NormalizedEventRecord.timestamp.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.get("/events/{event_id}", response_model=EventDetailOut)
async def get_event(event_id: str, session: AsyncSession = Depends(get_session)):
    event = await session.get(NormalizedEventRecord, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="event not found")

    raw = await session.get(RawEvent, event.raw_event_ref)
    detection_ids_result = await session.execute(
        select(DetectionEventLink.detection_id).where(DetectionEventLink.event_id == event_id)
    )
    incident_ids_result = await session.execute(
        select(IncidentEventLink.incident_id).where(IncidentEventLink.event_id == event_id)
    )

    base = EventOut.model_validate(event, from_attributes=True)
    return EventDetailOut.model_validate(
        {
            **base.model_dump(),
            "raw_payload": raw.payload if raw else {},
            "raw_sha256": raw.sha256 if raw else None,
            "detection_ids": [row[0] for row in detection_ids_result.all()],
            "incident_ids": [row[0] for row in incident_ids_result.all()],
        }
    )


# --------------------------------------------------------------------------------------------
# Detections
# --------------------------------------------------------------------------------------------


async def _event_ids_for_detection(session: AsyncSession, detection_id: str) -> list[str]:
    result = await session.execute(
        select(DetectionEventLink.event_id).where(DetectionEventLink.detection_id == detection_id)
    )
    return [row[0] for row in result.all()]


@router.get("/detections", response_model=list[DetectionOut])
async def list_detections(
    severity: str | None = Query(default=None),
    status: str | None = Query(default=None),
    asset_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Detection)
    if severity:
        stmt = stmt.where(Detection.severity == severity)
    if status:
        stmt = stmt.where(Detection.status == status)
    if asset_id:
        stmt = stmt.where(Detection.asset_id == asset_id)
    stmt = stmt.order_by(Detection.timestamp.desc()).limit(limit)
    result = await session.execute(stmt)
    detections = result.scalars().all()

    out = []
    for d in detections:
        event_ids = await _event_ids_for_detection(session, d.detection_id)
        detection_out = DetectionOut.model_validate(d, from_attributes=True)
        out.append(detection_out.model_copy(update={"event_ids": event_ids}))
    return out


@router.get("/detections/{detection_id}", response_model=DetectionOut)
async def get_detection(detection_id: str, session: AsyncSession = Depends(get_session)):
    detection = await session.get(Detection, detection_id)
    if detection is None:
        raise HTTPException(status_code=404, detail="detection not found")
    event_ids = await _event_ids_for_detection(session, detection_id)
    return DetectionOut.model_validate(detection, from_attributes=True).model_copy(
        update={"event_ids": event_ids}
    )


# --------------------------------------------------------------------------------------------
# Incidents
# --------------------------------------------------------------------------------------------


async def _detection_ids_for_incident(session: AsyncSession, incident_id: str) -> list[str]:
    result = await session.execute(
        select(IncidentDetectionLink.detection_id).where(
            IncidentDetectionLink.incident_id == incident_id
        )
    )
    return [row[0] for row in result.all()]


async def _event_ids_for_incident(session: AsyncSession, incident_id: str) -> list[str]:
    result = await session.execute(
        select(IncidentEventLink.event_id).where(IncidentEventLink.incident_id == incident_id)
    )
    return [row[0] for row in result.all()]


async def _notes_for_incident(session: AsyncSession, incident_id: str) -> list[IncidentNoteOut]:
    result = await session.execute(
        select(IncidentNote)
        .where(IncidentNote.incident_id == incident_id)
        .order_by(IncidentNote.created_at)
    )
    return [IncidentNoteOut.model_validate(n, from_attributes=True) for n in result.scalars().all()]


@router.get("/incidents", response_model=list[IncidentOut])
async def list_incidents(
    severity: str | None = Query(default=None),
    status: str | None = Query(default=None),
    asset_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Incident)
    if severity:
        stmt = stmt.where(Incident.severity == severity)
    if status:
        stmt = stmt.where(Incident.status == status)
    if asset_id:
        stmt = stmt.where(Incident.primary_asset_id == asset_id)
    stmt = stmt.order_by(Incident.last_seen.desc()).limit(limit)
    result = await session.execute(stmt)
    incidents = result.scalars().all()

    out = []
    for i in incidents:
        detection_ids = await _detection_ids_for_incident(session, i.incident_id)
        out.append(
            IncidentOut.model_validate(i, from_attributes=True).model_copy(
                update={"detection_ids": detection_ids}
            )
        )
    return out


@router.get("/incidents/{incident_id}", response_model=IncidentDetailOut)
async def get_incident(incident_id: str, session: AsyncSession = Depends(get_session)):
    incident = await session.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")

    detection_ids = await _detection_ids_for_incident(session, incident_id)
    event_ids = await _event_ids_for_incident(session, incident_id)
    notes = await _notes_for_incident(session, incident_id)

    detections = []
    for detection_id in detection_ids:
        detection = await session.get(Detection, detection_id)
        if detection is not None:
            d_event_ids = await _event_ids_for_detection(session, detection_id)
            detections.append(
                DetectionOut.model_validate(detection, from_attributes=True).model_copy(
                    update={"event_ids": d_event_ids}
                )
            )

    return IncidentDetailOut.model_validate(incident, from_attributes=True).model_copy(
        update={
            "detection_ids": detection_ids,
            "event_ids": event_ids,
            "detections": detections,
            "notes": notes,
        }
    )


@router.patch("/incidents/{incident_id}/status", response_model=IncidentOut)
async def update_incident_status(
    incident_id: str, body: IncidentStatusUpdate, session: AsyncSession = Depends(get_session)
):
    incident = await session.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")

    old_status = incident.status
    incident.status = body.status
    if body.status == "RESOLVED" and old_status != "RESOLVED":
        incident.resolved_at = datetime.now(UTC)
    elif body.status != "RESOLVED":
        incident.resolved_at = None

    await write_audit(
        session,
        entity_type="incident",
        entity_id=incident_id,
        action="incident.status_changed",
        actor=body.actor,
        detail={"old_status": old_status, "new_status": body.status},
    )
    await session.commit()
    await session.refresh(incident)

    detection_ids = await _detection_ids_for_incident(session, incident_id)
    return IncidentOut.model_validate(incident, from_attributes=True).model_copy(
        update={"detection_ids": detection_ids}
    )


@router.patch("/incidents/{incident_id}/assignment", response_model=IncidentOut)
async def update_incident_assignment(
    incident_id: str, body: IncidentAssignmentUpdate, session: AsyncSession = Depends(get_session)
):
    incident = await session.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")

    old_assignee = incident.assigned_to
    incident.assigned_to = body.assigned_to

    await write_audit(
        session,
        entity_type="incident",
        entity_id=incident_id,
        action="incident.assigned",
        actor=body.actor,
        detail={"old_assignee": old_assignee, "new_assignee": body.assigned_to},
    )
    await session.commit()
    await session.refresh(incident)

    detection_ids = await _detection_ids_for_incident(session, incident_id)
    return IncidentOut.model_validate(incident, from_attributes=True).model_copy(
        update={"detection_ids": detection_ids}
    )


@router.post("/incidents/{incident_id}/notes", response_model=IncidentNoteOut)
async def add_incident_note(
    incident_id: str, body: IncidentNoteCreate, session: AsyncSession = Depends(get_session)
):
    incident = await session.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")

    note_id = f"NOTE-{uuid.uuid4()}"
    note = IncidentNote(
        note_id=note_id, incident_id=incident_id, author=body.author, body=body.body
    )
    session.add(note)

    await write_audit(
        session,
        entity_type="incident",
        entity_id=incident_id,
        action="incident.note_added",
        actor=body.author,
        detail={"note_id": note_id},
    )
    await session.commit()
    await session.refresh(note)
    return IncidentNoteOut.model_validate(note, from_attributes=True)


@router.get("/incidents/{incident_id}/notes", response_model=list[IncidentNoteOut])
async def list_incident_notes(incident_id: str, session: AsyncSession = Depends(get_session)):
    incident = await session.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")
    return await _notes_for_incident(session, incident_id)


@router.patch("/incidents/{incident_id}/disposition", response_model=IncidentOut)
async def update_incident_disposition(
    incident_id: str, body: IncidentDispositionUpdate, session: AsyncSession = Depends(get_session)
):
    incident = await session.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")

    old_disposition = incident.disposition
    incident.disposition = body.disposition

    await write_audit(
        session,
        entity_type="incident",
        entity_id=incident_id,
        action="incident.disposition_set",
        actor=body.actor,
        detail={"old_disposition": old_disposition, "new_disposition": body.disposition},
    )
    await session.commit()
    await session.refresh(incident)

    detection_ids = await _detection_ids_for_incident(session, incident_id)
    return IncidentOut.model_validate(incident, from_attributes=True).model_copy(
        update={"detection_ids": detection_ids}
    )


# --------------------------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------------------------


@router.get("/metrics/summary", response_model=MetricsSummaryOut)
async def metrics_summary(session: AsyncSession = Depends(get_session)):
    protected_assets = (await session.execute(select(func.count(SentinelAsset.id)))).scalar_one()
    normalized_events = (
        await session.execute(select(func.count(NormalizedEventRecord.event_id)))
    ).scalar_one()
    active_detections_stmt = select(func.count(Detection.detection_id)).where(
        Detection.status == "open"
    )
    active_detections = (await session.execute(active_detections_stmt)).scalar_one()
    open_incidents_stmt = select(func.count(Incident.incident_id)).where(
        Incident.status.not_in(TERMINAL_INCIDENT_STATUSES)
    )
    open_incidents = (await session.execute(open_incidents_stmt)).scalar_one()
    critical_high_stmt = (
        select(func.count(Incident.incident_id))
        .where(Incident.status.not_in(TERMINAL_INCIDENT_STATUSES))
        .where(Incident.severity.in_(("high", "critical")))
    )
    critical_high_incidents = (await session.execute(critical_high_stmt)).scalar_one()

    severity_rows = await session.execute(
        select(Incident.severity, func.count(Incident.incident_id))
        .where(Incident.status.not_in(TERMINAL_INCIDENT_STATUSES))
        .group_by(Incident.severity)
    )
    severity_distribution = {row[0]: row[1] for row in severity_rows.all()}

    last_event = await session.execute(
        select(func.max(NormalizedEventRecord.ingestion_timestamp))
    )
    last_ingestion_at = last_event.scalar_one()

    missionnet_reachable = False
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{MISSIONNET_BASE_URL}/health")
            missionnet_reachable = resp.status_code == 200
    except httpx.HTTPError:
        missionnet_reachable = False

    return MetricsSummaryOut(
        protected_assets=protected_assets,
        normalized_events=normalized_events,
        active_detections=active_detections,
        open_incidents=open_incidents,
        critical_high_incidents=critical_high_incidents,
        severity_distribution=severity_distribution,
        missionnet_reachable=missionnet_reachable,
        last_ingestion_at=last_ingestion_at,
    )
