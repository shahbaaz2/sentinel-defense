from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

IncidentStatus = Literal["OPEN", "INVESTIGATING", "MONITORING", "RESOLVED", "DISMISSED"]
IncidentDisposition = Literal[
    "TRUE_POSITIVE", "BENIGN_TRUE_POSITIVE", "FALSE_POSITIVE", "TEST_SCENARIO", "UNDETERMINED"
]


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


class EventDetailOut(EventOut):
    raw_payload: dict = {}
    raw_sha256: str | None = None
    detection_ids: list[str] = []
    incident_ids: list[str] = []


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


class IncidentNoteOut(BaseModel):
    note_id: str
    incident_id: str
    author: str
    body: str
    created_at: datetime

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
    scenario_id: str | None
    assigned_to: str | None
    disposition: str | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime
    detection_ids: list[str] = []

    model_config = {"from_attributes": True}


class AssetDetailOut(AssetOut):
    active_incident_count: int = 0
    active_detection_count: int = 0
    recent_events: list[EventOut] = []
    recent_detections: list[DetectionOut] = []
    recent_incidents: list[IncidentOut] = []
    related_identity: str | None = None
    vulnerability_posture: str = "NOT YET INTEGRATED"


class IncidentDetailOut(IncidentOut):
    """Adds the evidence Sentinel's future AI analyst (Phase 5) will be required to cite - exact
    detections and exact source events, not opaque reasoning."""

    detections: list[DetectionOut] = []
    event_ids: list[str] = []
    notes: list[IncidentNoteOut] = []


class IncidentStatusUpdate(BaseModel):
    status: IncidentStatus
    actor: str = Field(default="analyst", max_length=128)


class IncidentAssignmentUpdate(BaseModel):
    assigned_to: str | None = Field(default=None, max_length=128)
    actor: str = Field(default="analyst", max_length=128)


class IncidentNoteCreate(BaseModel):
    author: str = Field(max_length=128)
    body: str = Field(min_length=1, max_length=4000)


class IncidentDispositionUpdate(BaseModel):
    disposition: IncidentDisposition
    actor: str = Field(default="analyst", max_length=128)


class AIEvidenceReferenceOut(BaseModel):
    event_id: str
    relevance: str


class AIDetectionReferenceOut(BaseModel):
    detection_id: str
    relevance: str


class AIAssessmentContentOut(BaseModel):
    classification: str
    confidence: float
    summary: str
    affected_assets: list[str]
    evidence_refs: list[AIEvidenceReferenceOut]
    detection_refs: list[AIDetectionReferenceOut]
    hypotheses: list[str]
    recommended_investigation_steps: list[str]
    attack_techniques: list[str]
    recommended_playbook_id: str | None
    limitations: list[str]


class AIAssessmentOut(BaseModel):
    assessment_id: str
    incident_id: str
    created_at: datetime
    model_name: str
    model_provider: str
    model_revision: str | None
    model_quantization: str | None
    prompt_version: str
    evidence_pack_hash: str
    output_schema_version: str
    assessment: AIAssessmentContentOut | None
    validation_status: Literal[
        "VALID", "REJECTED_SCHEMA", "REJECTED_HALLUCINATION", "TIMEOUT", "PROVIDER_ERROR"
    ]
    latency_ms: int | None
    error: str | None
    scenario_id: str | None

    model_config = {"from_attributes": True}


class AIStatusOut(BaseModel):
    ai_enabled: bool
    runtime: str
    provider: str
    model: str
    status: Literal["READY", "LOADING", "DEGRADED", "DISABLED"]
    external_ai_api: str = "DISABLED"
    last_latency_ms: int | None = None


class MetricsSummaryOut(BaseModel):
    protected_assets: int
    normalized_events: int
    active_detections: int
    open_incidents: int
    critical_high_incidents: int
    severity_distribution: dict[str, int]
    missionnet_reachable: bool
    last_ingestion_at: datetime | None
    ai_analyst_status: str = "NOT_ENABLED"


class RuleCoverageOut(BaseModel):
    rule_id: str
    name: str
    version: str
    enabled: bool
    severity: str
    category: str
    description: str
    event_categories: list[str]
    mitre_techniques: list[str]
    validating_scenarios: list[str]
    validation_status: Literal["VALIDATED", "FAILED", "NOT_TESTED"]
    last_triggered: datetime | None
    total_detections: int


class AuditLogEntryOut(BaseModel):
    audit_id: str
    timestamp: datetime
    entity_type: str
    entity_id: str
    action: str
    actor: str
    source: str
    scenario_id: str | None
    detail: dict

    model_config = {"from_attributes": True}


class IntegrationStatusOut(BaseModel):
    missionnet: str = "ACTIVE"
    wazuh: str = "NOT_CONFIGURED"
    splunk: str = "NOT_CONFIGURED"
    suricata: str = "NOT_CONFIGURED"
    zeek: str = "NOT_CONFIGURED"
    falco: str = "NOT_CONFIGURED"


class SystemAssuranceOut(BaseModel):
    deployment_profile: str
    platform: str
    inference_location: str
    external_ai_api: str
    ai_analyst_status: str
    internet_required_for_core_demo: str
    model: str
    model_provider: str
    knowledge_bundle: str
    policy_bundle: str
    synthetic_only: bool
    missionnet_adapter: str
    sentinel_api: str
    postgresql: str
    demo_control: str
    local_llm_runtime: str
    rag_status: str = "NOT ENABLED"
    response_authority: str = "BOUNDED - HUMAN-APPROVED ONLY, NO AUTONOMY"
    response_planning: str = "ENABLED"
    policy_engine: str = "OPERATIONAL"
    human_approval: str = "ENABLED"
    response_execution: str = "ENABLED - BOUNDED"
    verification: str = "ENABLED"
    rollback: str = "ENABLED FOR SUPPORTED ACTIONS"
    autonomous_response: str = "DISABLED"
    integrations: IntegrationStatusOut


# --------------------------------------------------------------------------------------------
# Phase 6: playbooks, policy engine, response plans
# --------------------------------------------------------------------------------------------

ResponsePlanStatus = Literal[
    "DRAFT", "AWAITING_APPROVAL", "APPROVED", "REJECTED", "CANCELLED", "EXPIRED"
]


class PlaybookActionOut(BaseModel):
    action_id: str
    target_source: str
    description: str
    risk_level: str
    reversible: bool
    requires_approval: bool
    expected_verification: str


class PlaybookRiskOut(BaseModel):
    mission_impact: str
    reversibility: str


class PlaybookOut(BaseModel):
    id: str
    version: str
    name: str
    description: str
    enabled: bool
    allowed_asset_types: list[str]
    allowed_incident_categories: list[str]
    minimum_incident_severity: list[str]
    minimum_detection_count: int
    requires_human_approval: bool
    reversible: bool
    actions: list[PlaybookActionOut]
    verification: list[str]
    rollback: list[str]
    risk: PlaybookRiskOut


class PolicyDecisionOut(BaseModel):
    decision: Literal["ALLOW", "DENY"]
    playbook_id: str
    allowed: bool
    reasons: list[str]
    blocking_reasons: list[str]
    requires_human_approval: bool


class ResponsePlanCreate(BaseModel):
    playbook_id: str = Field(max_length=64)
    actor: str = Field(default="analyst", max_length=128)
    recommendation_source: Literal["ai", "analyst"] = "analyst"
    ai_assessment_id: str | None = Field(default=None, max_length=128)
    note: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _ai_source_requires_assessment_id(self) -> "ResponsePlanCreate":
        if self.recommendation_source == "ai" and not self.ai_assessment_id:
            raise ValueError("recommendation_source 'ai' requires ai_assessment_id")
        return self


class ResponsePlanOut(BaseModel):
    response_plan_id: str
    incident_id: str
    playbook_id: str
    playbook_version: str
    created_at: datetime
    created_by: str
    recommendation_source: Literal["ai", "analyst"]
    ai_assessment_id: str | None
    policy_bundle_version: str
    policy_decision: str
    policy_reasons: list[str]
    risk_level: str
    reversible: bool
    status: ResponsePlanStatus
    approved_by: str | None
    approved_at: datetime | None
    rejected_by: str | None
    rejected_at: datetime | None
    rejection_reason: str | None
    cancelled_by: str | None
    cancelled_at: datetime | None
    scenario_id: str | None
    execution_status: str
    executed_by: str | None = None
    execution_started_at: datetime | None = None
    execution_completed_at: datetime | None = None
    executor_version: str | None = None
    execution_block_reason: str | None = None

    model_config = {"from_attributes": True}


class ResponsePlanApprove(BaseModel):
    actor: str = Field(max_length=128)
    note: str | None = Field(default=None, max_length=2000)


class ResponsePlanReject(BaseModel):
    actor: str = Field(max_length=128)
    reason: str = Field(min_length=1, max_length=2000)


class ResponsePlanCancel(BaseModel):
    actor: str = Field(max_length=128)
    note: str | None = Field(default=None, max_length=2000)


# --------------------------------------------------------------------------------------------
# Phase 7: response execution, verification, rollback
# --------------------------------------------------------------------------------------------


class ResponsePlanExecute(BaseModel):
    actor: str = Field(max_length=128)


class ResponsePlanRollback(BaseModel):
    actor: str = Field(max_length=128)


class ActionResultOut(BaseModel):
    action_result_id: str
    response_plan_id: str
    action_index: int
    action_id: str
    required: bool
    target_type: str | None
    target_id: str | None
    started_at: datetime | None
    completed_at: datetime | None
    status: Literal["PENDING", "SKIPPED", "RUNNING", "SUCCEEDED", "FAILED"]
    result_metadata: dict
    verification_status: Literal["NOT_CHECKED", "NOT_APPLICABLE", "VERIFIED", "FAILED"]
    verification_detail: dict
    rollback_status: Literal["NOT_APPLICABLE", "PENDING", "ROLLED_BACK", "FAILED"]
    rolled_back_at: datetime | None
    error_code: str | None
    error_message: str | None

    model_config = {"from_attributes": True}


class ExecutionOut(BaseModel):
    response_plan_id: str
    execution_status: str
    executed_by: str | None
    execution_started_at: datetime | None
    execution_completed_at: datetime | None
    executor_version: str | None
    execution_block_reason: str | None
    actions: list[ActionResultOut]
