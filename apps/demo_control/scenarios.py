"""Declarative scenario schema + loader. A scenario file describes *what MissionNet actions to
take* and *what should be observed as a result* - the runner (runner.py) is the only thing that
actually executes it, and the verifier (verification.py) is the only thing that decides pass/fail.
Nothing here contains success logic; this module only parses and validates the YAML shape.
"""

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

SCENARIOS_DIR = Path(__file__).resolve().parents[2] / "cyber-range" / "scenarios"


class ScenarioStep(BaseModel):
    id: str
    action: str
    target: str | None = None
    targets: list[str] | None = None
    repeat: int = Field(default=1, ge=1, le=20)
    parameters: dict = Field(default_factory=dict)


class MissionNetExpectation(BaseModel):
    event_type: str
    asset_id: str | None = None
    count: int = 1


class SentinelDetectionExpectation(BaseModel):
    rule_id: str


class SentinelIncidentExpectation(BaseModel):
    min_count: int = 1
    primary_asset_id: str | None = None


class SentinelExpectation(BaseModel):
    detections: list[SentinelDetectionExpectation] = Field(default_factory=list)
    incidents: SentinelIncidentExpectation = Field(default_factory=SentinelIncidentExpectation)


class ExpectedObservations(BaseModel):
    missionnet: list[MissionNetExpectation] = Field(default_factory=list)
    sentinel: SentinelExpectation = Field(default_factory=SentinelExpectation)


class ResetSpec(BaseModel):
    strategy: str = "lab_reset"


class Preconditions(BaseModel):
    missionnet_status: str = "nominal"


class ScenarioDefinition(BaseModel):
    id: str
    version: str = "1.0.0"
    name: str
    description: str
    risk_level: str
    preconditions: Preconditions = Field(default_factory=Preconditions)
    steps: list[ScenarioStep]
    expected_observations: ExpectedObservations
    success_conditions: list[str]
    reset: ResetSpec = Field(default_factory=ResetSpec)


def load_scenario(scenario_id: str) -> ScenarioDefinition:
    path = SCENARIOS_DIR / f"{scenario_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"no scenario definition at {path}")
    with open(path) as f:
        raw = yaml.safe_load(f)
    return ScenarioDefinition.model_validate(raw)


def list_scenarios() -> list[ScenarioDefinition]:
    if not SCENARIOS_DIR.exists():
        return []
    scenarios = []
    for path in sorted(SCENARIOS_DIR.glob("SCN-*.yaml")):
        with open(path) as f:
            raw = yaml.safe_load(f)
        scenarios.append(ScenarioDefinition.model_validate(raw))
    return scenarios
