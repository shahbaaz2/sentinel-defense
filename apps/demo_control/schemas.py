from datetime import datetime

from pydantic import BaseModel


class ScenarioSummary(BaseModel):
    id: str
    version: str
    name: str
    description: str
    risk_level: str
    step_count: int


class ScenarioRunOut(BaseModel):
    run_id: str
    scenario_id: str
    scenario_version: str
    actor: str
    status: str
    current_step: str | None
    failure_reason: str | None
    started_at: datetime
    completed_at: datetime | None
    step_results: list
    timeline: list
    missionnet_event_ids: list[str]
    sentinel_event_ids: list[str]
    detection_ids: list[str]
    incident_ids: list[str]
    verification: dict
    reset_status: str | None

    model_config = {"from_attributes": True}


class RunScenarioRequest(BaseModel):
    actor: str = "demo-operator"


class SystemStatusOut(BaseModel):
    missionnet_status: str
    sentinel_status: str
    ai_analyst_status: str = "NOT_ENABLED"
