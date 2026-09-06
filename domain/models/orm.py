"""Sentinel's own persistence schema (blueprint §10), Phase 2.

Distinct from `domain/models/events.NormalizedEvent` (the canonical Pydantic *contract* every
adapter maps into) and from `apps/missionnet/models.py` (the system Sentinel protects). This is
Sentinel's system of record: what it ingested, what deterministic rules fired, and how those were
correlated into incidents. No AI involvement anywhere in this file - everything here is written by
deterministic code paths only.
"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from domain.db import Base


class RawEvent(Base):
    """Original, unmodified source payload (blueprint §8.2). Never discarded, never truncated."""

    __tablename__ = "raw_events"

    raw_event_id: Mapped[str] = mapped_column(primary_key=True)
    source: Mapped[str]
    payload: Mapped[dict] = mapped_column(JSON)
    sha256: Mapped[str]
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SentinelAsset(Base):
    """Sentinel's own view of a protected asset - may later aggregate multiple source systems
    behind one `id`, which is why `external_asset_id` + `source` are tracked separately."""

    __tablename__ = "assets"
    __table_args__ = (UniqueConstraint("source", "external_asset_id"),)

    id: Mapped[str] = mapped_column(primary_key=True)
    external_asset_id: Mapped[str]
    source: Mapped[str] = mapped_column(default="missionnet")
    name: Mapped[str]
    asset_type: Mapped[str] = mapped_column(default="unknown")
    environment: Mapped[str] = mapped_column(default="lab")
    criticality: Mapped[int] = mapped_column(default=3)
    status: Mapped[str] = mapped_column(default="unknown")
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    extra: Mapped[dict] = mapped_column(JSON, default=dict)


class NormalizedEventRecord(Base):
    """Persisted form of `domain.models.events.NormalizedEvent`, plus a few ingestion-only fields
    (event_type, correlation_key) that the canonical Pydantic contract deliberately keeps out of the
    wire schema but that make DB-side rule evaluation and correlation efficient."""

    __tablename__ = "normalized_events"
    __table_args__ = (UniqueConstraint("source", "source_event_id"),)

    event_id: Mapped[str] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ingestion_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    source: Mapped[str]
    source_event_id: Mapped[str]
    """The source system's own ID for this event (e.g. MissionNet's audit_id) - idempotency key."""

    asset_id: Mapped[str | None] = mapped_column(default=None)
    user_id: Mapped[str | None] = mapped_column(default=None)

    event_category: Mapped[str]
    event_type: Mapped[str]
    """More specific than event_category - the source action, e.g. 'auth.failure'."""
    severity: Mapped[str]

    src_ip: Mapped[str | None] = mapped_column(default=None)
    dst_ip: Mapped[str | None] = mapped_column(default=None)
    process_name: Mapped[str | None] = mapped_column(default=None)
    rule_id: Mapped[str | None] = mapped_column(default=None)
    """Rule/technique ID the SOURCE already attached, if any - not a Sentinel conclusion."""

    technique_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    summary: Mapped[str]
    raw_event_ref: Mapped[str] = mapped_column(ForeignKey("raw_events.raw_event_id"))
    scenario_id: Mapped[str | None] = mapped_column(default=None)
    correlation_key: Mapped[str | None] = mapped_column(default=None)
    """Convenience grouping key for the incident engine - asset_id if present, else user_id."""


class Detection(Base):
    """One deterministic rule firing against one or more normalized events. Evidence links live in
    `DetectionEventLink`, not as an opaque JSON blob, so the API can join back to real evidence."""

    __tablename__ = "detections"

    detection_id: Mapped[str] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    rule_id: Mapped[str]
    rule_version: Mapped[str]
    rule_name: Mapped[str]
    severity: Mapped[str]
    confidence: Mapped[float] = mapped_column(default=1.0)
    asset_id: Mapped[str | None] = mapped_column(default=None)
    correlation_key: Mapped[str | None] = mapped_column(default=None)
    """asset_id when present, else the identity (user_id) the detection is about - lets the
    incident engine group identity-centric detections (e.g. DET-001, DET-006) the same way it
    groups asset-centric ones, without conflating the two into one column's semantics."""
    mitre_techniques: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(default="open")
    evidence_summary: Mapped[str]
    dedupe_key: Mapped[str] = mapped_column(unique=True)
    """hash(rule_id, sorted(event_ids)) - lets the engine re-run every cycle without duplicating a
    detection for a pattern that hasn't changed."""
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DetectionEventLink(Base):
    __tablename__ = "detection_event_links"

    detection_id: Mapped[str] = mapped_column(
        ForeignKey("detections.detection_id"), primary_key=True
    )
    event_id: Mapped[str] = mapped_column(
        ForeignKey("normalized_events.event_id"), primary_key=True
    )


class Incident(Base):
    __tablename__ = "incidents"

    incident_id: Mapped[str] = mapped_column(primary_key=True)
    title: Mapped[str]
    severity: Mapped[str]
    status: Mapped[str] = mapped_column(default="OPEN")
    """Phase 4 analyst-workflow vocabulary: OPEN, INVESTIGATING, MONITORING, RESOLVED, DISMISSED.
    This is deliberately a *different, earlier* state machine than blueprint §9.4's full
    new/triage/.../awaiting_approval/responding/contained/closed - that one describes the response
    lifecycle (Phase 6/7, once playbooks and containment exist). This one describes analyst triage,
    which is all that exists so far. Phase 6 can extend this vocabulary rather than replace it."""
    confidence: Mapped[float] = mapped_column(default=1.0)
    primary_asset_id: Mapped[str | None] = mapped_column(default=None)
    correlation_key: Mapped[str | None] = mapped_column(default=None)
    """Mirrors Detection.correlation_key - what new detections are matched against to decide
    whether they extend this incident or start a new one."""
    category: Mapped[str]
    summary: Mapped[str]
    mitre_techniques: Mapped[list[str]] = mapped_column(JSON, default=list)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    scenario_id: Mapped[str | None] = mapped_column(default=None)
    """Set once at creation from the triggering detection's evidence provenance, never overwritten
    by a later merge - an incident that started from a real scenario stays attributed to it."""
    assigned_to: Mapped[str | None] = mapped_column(default=None)
    disposition: Mapped[str | None] = mapped_column(default=None)
    """Analyst-set only, never auto-assigned - see DECISIONS.md. One of TRUE_POSITIVE,
    BENIGN_TRUE_POSITIVE, FALSE_POSITIVE, TEST_SCENARIO, UNDETERMINED."""
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class IncidentNote(Base):
    """Free-text analyst notes - additive, never edited/deleted, so the note history itself is
    part of the incident's provenance trail."""

    __tablename__ = "incident_notes"

    note_id: Mapped[str] = mapped_column(primary_key=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.incident_id"))
    author: Mapped[str]
    body: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLogEntry(Base):
    """Sentinel's own audit/provenance trail (blueprint §10 `audit_log`) - append-only by
    convention (no code path updates or deletes a row). Every ingestion cycle, detection, incident,
    and analyst workflow change writes exactly one row here."""

    __tablename__ = "audit_log"

    audit_id: Mapped[str] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    entity_type: Mapped[str]
    """One of: ingestion, event, detection, incident."""
    entity_id: Mapped[str]
    action: Mapped[str]
    actor: Mapped[str] = mapped_column(default="system")
    """'system' for automated pipeline actions; an analyst identifier for workflow changes."""
    source: Mapped[str] = mapped_column(default="sentinel")
    scenario_id: Mapped[str | None] = mapped_column(default=None)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    """Structured metadata only - counts, IDs, old/new values. Never raw payloads or secrets."""


class IncidentDetectionLink(Base):
    __tablename__ = "incident_detection_links"

    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.incident_id"), primary_key=True)
    detection_id: Mapped[str] = mapped_column(
        ForeignKey("detections.detection_id"), primary_key=True
    )


class IncidentEventLink(Base):
    """Direct incident -> event evidence links, so the API/UI can show exact source evidence
    without a two-hop join through detections."""

    __tablename__ = "incident_event_links"

    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.incident_id"), primary_key=True)
    event_id: Mapped[str] = mapped_column(
        ForeignKey("normalized_events.event_id"), primary_key=True
    )


class IngestionCursor(Base):
    """One row per (source, stream) - e.g. ('missionnet', 'audit') - tracking the polling
    watermark so ingestion is resumable and never reprocesses the same window from scratch."""

    __tablename__ = "ingestion_cursors"

    source: Mapped[str] = mapped_column(primary_key=True)
    stream: Mapped[str] = mapped_column(primary_key=True)
    last_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
