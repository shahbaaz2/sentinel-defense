"""The structured output contract every AI assessment must satisfy (blueprint AI Analyst §8).
Pydantic validation is the first line of defense against malformed output; `services/ai_analyst/
validation.py` is the second, checking that every ID actually exists in the evidence pack that was
sent to the model.
"""

from pydantic import BaseModel, Field

OUTPUT_SCHEMA_VERSION = "ai_incident_assessment_v1"


class EvidenceReference(BaseModel):
    event_id: str
    relevance: str = Field(max_length=500)


class DetectionReference(BaseModel):
    detection_id: str
    relevance: str = Field(max_length=500)


class AIIncidentAssessment(BaseModel):
    classification: str = Field(max_length=200)
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str = Field(max_length=2000)
    affected_assets: list[str] = Field(default_factory=list)
    evidence_refs: list[EvidenceReference] = Field(default_factory=list)
    detection_refs: list[DetectionReference] = Field(default_factory=list)
    hypotheses: list[str] = Field(default_factory=list)
    recommended_investigation_steps: list[str] = Field(default_factory=list)
    attack_techniques: list[str] = Field(default_factory=list)
    recommended_playbook_id: str | None = None
    limitations: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}
