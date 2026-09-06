"""Demo Control's own persistence: one row per scenario run.

A single table with JSON columns for step results and observed-ID lists is a deliberate
simplification (see DECISIONS.md) - this is operational run metadata, not core security data, and
nothing here needs relational joins the way Sentinel's evidence links do. Every ID this table
records was independently observed by reading MissionNet's or Sentinel's own read APIs, never
written by the controller into either system.
"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from apps.demo_control.db import Base


class ScenarioRun(Base):
    __tablename__ = "scenario_runs"

    run_id: Mapped[str] = mapped_column(primary_key=True)
    scenario_id: Mapped[str]
    scenario_version: Mapped[str]
    actor: Mapped[str] = mapped_column(default="demo-operator")

    status: Mapped[str] = mapped_column(default="PENDING")
    """PENDING, PREPARING, RUNNING, WAITING_FOR_TELEMETRY, WAITING_FOR_SENTINEL, VERIFYING, PASSED,
    FAILED, CANCELLED, RESETTING, COMPLETE."""
    current_step: Mapped[str | None] = mapped_column(default=None)
    failure_reason: Mapped[str | None] = mapped_column(default=None)
    cancel_requested: Mapped[bool] = mapped_column(default=False)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    step_results: Mapped[list] = mapped_column(JSON, default=list)
    timeline: Mapped[list] = mapped_column(JSON, default=list)
    """Ordered list of {timestamp, message} - exactly what the UI's live timeline renders,
    generated only as real execution milestones happen, never animated after the fact."""

    missionnet_event_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    sentinel_event_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    detection_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    incident_ids: Mapped[list[str]] = mapped_column(JSON, default=list)

    verification: Mapped[dict] = mapped_column(JSON, default=dict)
    """check_name -> bool, derived from real observed IDs above - never hard-coded to True."""

    reset_status: Mapped[str | None] = mapped_column(default=None)
