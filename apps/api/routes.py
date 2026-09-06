from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.schemas import (
    AssetOut,
    DetectionOut,
    EventOut,
    IncidentDetailOut,
    IncidentOut,
    MetricsSummaryOut,
)
from domain.db import get_session
from domain.models.orm import (
    Detection,
    DetectionEventLink,
    Incident,
    IncidentDetectionLink,
    IncidentEventLink,
    NormalizedEventRecord,
    SentinelAsset,
)

router = APIRouter(prefix="/api/v1")
MISSIONNET_BASE_URL = "http://127.0.0.1:8090"


@router.get("/assets", response_model=list[AssetOut])
async def list_assets(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(SentinelAsset).order_by(SentinelAsset.id))
    return result.scalars().all()


@router.get("/assets/{asset_id}", response_model=AssetOut)
async def get_asset(asset_id: str, session: AsyncSession = Depends(get_session)):
    asset = await session.get(SentinelAsset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="asset not found")
    return asset


@router.get("/events", response_model=list[EventOut])
async def list_events(
    severity: str | None = Query(default=None),
    source: str | None = Query(default=None),
    asset_id: str | None = Query(default=None),
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(NormalizedEventRecord)
    if severity:
        stmt = stmt.where(NormalizedEventRecord.severity == severity)
    if source:
        stmt = stmt.where(NormalizedEventRecord.source == source)
    if asset_id:
        stmt = stmt.where(NormalizedEventRecord.asset_id == asset_id)
    if since:
        stmt = stmt.where(NormalizedEventRecord.timestamp >= since)
    if until:
        stmt = stmt.where(NormalizedEventRecord.timestamp <= until)
    stmt = stmt.order_by(NormalizedEventRecord.timestamp.desc()).limit(limit)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.get("/events/{event_id}", response_model=EventOut)
async def get_event(event_id: str, session: AsyncSession = Depends(get_session)):
    event = await session.get(NormalizedEventRecord, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="event not found")
    return event


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
        update={"detection_ids": detection_ids, "event_ids": event_ids, "detections": detections}
    )


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
        Incident.status != "closed"
    )
    open_incidents = (await session.execute(open_incidents_stmt)).scalar_one()

    severity_rows = await session.execute(
        select(Incident.severity, func.count(Incident.incident_id))
        .where(Incident.status != "closed")
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
        severity_distribution=severity_distribution,
        missionnet_reachable=missionnet_reachable,
        last_ingestion_at=last_ingestion_at,
    )
