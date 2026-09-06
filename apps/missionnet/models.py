"""MissionNet ORM models (blueprint §7, §7.3, §7.6, §10).

Every row is fictional/synthetic by construction; classification defaults to "SYNTHETIC"
everywhere it is displayed. This is the system Sentinel protects, not Sentinel's own data model.
"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.missionnet.db import Base


class Asset(Base):
    __tablename__ = "assets"

    asset_id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    asset_type: Mapped[str]
    mission_role: Mapped[str]
    """One of: identity, gateway, data, comms, operator-console, edge (blueprint §7.3)."""
    criticality: Mapped[int] = mapped_column(default=3)
    dependencies: Mapped[list[str]] = mapped_column(JSON, default=list)
    max_allowed_outage_seconds: Mapped[int] = mapped_column(default=300)
    containment_cost: Mapped[str] = mapped_column(default="medium")
    rollback_supported: Mapped[bool] = mapped_column(default=True)

    status: Mapped[str] = mapped_column(default="nominal")
    """One of: nominal, degraded, quarantined, contained, recovering."""
    network_state: Mapped[str] = mapped_column(default="normal")
    """One of: normal, quarantined, unexpected_destination (scenario-injected)."""
    classification: Mapped[str] = mapped_column(default="SYNTHETIC")


class IdentityUser(Base):
    __tablename__ = "identity_users"

    user_id: Mapped[str] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(unique=True)
    display_name: Mapped[str]
    role: Mapped[str]
    """One of: operator, analyst, administrator, service_account."""
    user_type: Mapped[str] = mapped_column(default="human")
    """One of: human, service_account."""
    status: Mapped[str] = mapped_column(default="active")
    """One of: active, suspended."""
    synthetic_password: Mapped[str] = mapped_column(default="SynthLab#2026")
    """Plaintext by design: this is a fictional identity in a synthetic lab, not a real
    credential. Exists so MissionNet can produce genuine auth.success/auth.failure events for
    Sentinel to detect - never treat as a real secret or apply real password-handling practices."""
    classification: Mapped[str] = mapped_column(default="SYNTHETIC")

    tokens: Mapped[list["ServiceToken"]] = relationship(back_populates="owner")


class ServiceToken(Base):
    __tablename__ = "service_tokens"

    token_id: Mapped[str] = mapped_column(primary_key=True)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("identity_users.user_id"))
    token_type: Mapped[str] = mapped_column(default="service")
    valid: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    classification: Mapped[str] = mapped_column(default="SYNTHETIC")

    owner: Mapped[IdentityUser] = relationship(back_populates="tokens")


class MissionRecord(Base):
    __tablename__ = "mission_records"

    record_id: Mapped[str] = mapped_column(primary_key=True)
    title: Mapped[str]
    body: Mapped[str]
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("identity_users.user_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    classification: Mapped[str] = mapped_column(default="SYNTHETIC")


class TelemetrySample(Base):
    __tablename__ = "telemetry_samples"

    sample_id: Mapped[str] = mapped_column(primary_key=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.asset_id"))
    battery: Mapped[int] = mapped_column(default=100)
    link_quality: Mapped[int] = mapped_column(default=100)
    latitude: Mapped[float | None] = mapped_column(default=None)
    longitude: Mapped[float | None] = mapped_column(default=None)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    classification: Mapped[str] = mapped_column(default="SYNTHETIC")


class AuditEvent(Base):
    """MissionNet's own application/audit stream - distinct from Sentinel's audit_log (§10).

    Sentinel's event ingestor reads these rows as a source of NormalizedEvents; they are never
    treated as instructions, only as evidence data.
    """

    __tablename__ = "audit_events"

    audit_id: Mapped[str] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actor_type: Mapped[str]
    """One of: human, service_account, lab_control, scenario_controller."""
    actor_id: Mapped[str]
    action: Mapped[str]
    object_type: Mapped[str]
    object_id: Mapped[str]
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    severity: Mapped[str] = mapped_column(default="info")
    scenario_id: Mapped[str | None] = mapped_column(default=None)
    classification: Mapped[str] = mapped_column(default="SYNTHETIC")
