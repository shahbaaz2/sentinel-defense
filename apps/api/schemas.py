from datetime import datetime

from pydantic import BaseModel


class AssetOut(BaseModel):
    id: str
    external_asset_id: str
    source: str
    name: str
    asset_type: str
    environment: str
    criticality: int
    status: str
    first_seen_at: datetime
    last_seen_at: datetime

    model_config = {"from_attributes": True}


class EventOut(BaseModel):
    event_id: str
    timestamp: datetime
    ingestion_timestamp: datetime
    source: str
    source_event_id: str
    asset_id: str | None
    user_id: str | None
    event_category: str
    event_type: str
    severity: str
    summary: str
    raw_event_ref: str
    scenario_id: str | None

    model_config = {"from_attributes": True}


class DetectionOut(BaseModel):
    detection_id: str
    timestamp: datetime
    rule_id: str
    rule_version: str
    rule_name: str
    severity: str
    confidence: float
    asset_id: str | None
    mitre_techniques: list[str]
    status: str
    evidence_summary: str
    event_ids: list[str] = []

    model_config = {"from_attributes": True}


class IncidentOut(BaseModel):
    incident_id: str
    title: str
    severity: str
    status: str
    confidence: float
    primary_asset_id: str | None
    category: str
    summary: str
    mitre_techniques: list[str]
    first_seen: datetime
    last_seen: datetime
    created_at: datetime
    updated_at: datetime
    detection_ids: list[str] = []

    model_config = {"from_attributes": True}


class IncidentDetailOut(IncidentOut):
    """Adds the evidence Sentinel's future AI analyst (Phase 5) will be required to cite - exact
    detections and exact source events, not opaque reasoning."""

    detections: list[DetectionOut] = []
    event_ids: list[str] = []


class MetricsSummaryOut(BaseModel):
    protected_assets: int
    normalized_events: int
    active_detections: int
    open_incidents: int
    severity_distribution: dict[str, int]
    missionnet_reachable: bool
    last_ingestion_at: datetime | None
    ai_analyst_status: str = "NOT_ENABLED"
