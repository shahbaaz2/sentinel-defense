"""Phase 5: hallucinated-reference rejection (blueprint AI Analyst §9). These tests build an
EvidencePack directly in memory (no DB needed) and prove that every ID category the model can cite
- event, detection, asset, playbook - is checked against exactly what was in the pack, with a 0%
acceptance rate for invented IDs."""

from datetime import UTC, datetime

import pytest

from ai.schemas import AIIncidentAssessment, DetectionReference, EvidenceReference
from services.ai_analyst.evidence import EvidenceDetection, EvidenceEvent, EvidencePack
from services.ai_analyst.validation import ReferenceValidationError, validate_assessment

T0 = datetime(2026, 9, 6, 12, 0, 0, tzinfo=UTC)


def _pack(**overrides) -> EvidencePack:
    defaults = dict(
        incident_id="INC-1",
        incident_title="Repeated auth failures",
        incident_severity="medium",
        incident_status="OPEN",
        incident_category="auth-abuse",
        incident_summary="3 failed logins",
        primary_asset_id="asset-1",
        scenario_id="SCN-001",
        first_seen=T0,
        last_seen=T0,
        asset_context=None,
        detections=[
            EvidenceDetection(
                detection_id="DET-001-real",
                rule_id="DET-001",
                rule_name="Repeated auth failure",
                severity="medium",
                confidence=1.0,
                evidence_summary="3 failures in 60s",
                mitre_techniques=["T1110"],
                event_ids=["EVT-real-1", "EVT-real-2"],
            )
        ],
        events=[
            EvidenceEvent(
                event_id="EVT-real-1",
                timestamp=T0,
                source="missionnet",
                event_category="identity",
                event_type="auth.failure",
                severity="info",
                asset_id=None,
                user_id="u1",
                summary="failed login",
            ),
            EvidenceEvent(
                event_id="EVT-real-2",
                timestamp=T0,
                source="missionnet",
                event_category="identity",
                event_type="auth.failure",
                severity="info",
                asset_id=None,
                user_id="u1",
                summary="failed login",
            ),
        ],
        known_attack_techniques=["T1110"],
        available_playbook_ids=[],
    )
    defaults.update(overrides)
    return EvidencePack(**defaults)


def _assessment(**overrides) -> AIIncidentAssessment:
    defaults = dict(
        classification="credential-stuffing",
        confidence=0.7,
        summary="Looks like automated credential stuffing.",
        affected_assets=["asset-1"],
        evidence_refs=[EvidenceReference(event_id="EVT-real-1", relevance="shows the pattern")],
        detection_refs=[
            DetectionReference(detection_id="DET-001-real", relevance="fired on the pattern")
        ],
        hypotheses=[],
        recommended_investigation_steps=[],
        attack_techniques=["T1110"],
        recommended_playbook_id=None,
        limitations=[],
    )
    defaults.update(overrides)
    return AIIncidentAssessment(**defaults)


def test_valid_assessment_passes():
    validate_assessment(_assessment(), _pack())  # must not raise


def test_hallucinated_event_id_rejected():
    bad = _assessment(
        evidence_refs=[EvidenceReference(event_id="EVT-does-not-exist", relevance="fabricated")]
    )
    with pytest.raises(ReferenceValidationError, match="EVT-does-not-exist"):
        validate_assessment(bad, _pack())


def test_hallucinated_detection_id_rejected():
    bad = _assessment(
        detection_refs=[
            DetectionReference(detection_id="DET-999-fake", relevance="fabricated")
        ]
    )
    with pytest.raises(ReferenceValidationError, match="DET-999-fake"):
        validate_assessment(bad, _pack())


def test_hallucinated_affected_asset_rejected():
    bad = _assessment(affected_assets=["asset-1", "asset-that-does-not-exist"])
    with pytest.raises(ReferenceValidationError, match="asset-that-does-not-exist"):
        validate_assessment(bad, _pack())


def test_playbook_id_outside_allowlist_rejected():
    bad = _assessment(recommended_playbook_id="PB-999")
    with pytest.raises(ReferenceValidationError, match="PB-999"):
        validate_assessment(bad, _pack())


def test_playbook_id_within_allowlist_accepted():
    pack = _pack(available_playbook_ids=["PB-001"])
    ok = _assessment(recommended_playbook_id="PB-001")
    validate_assessment(ok, pack)  # must not raise


def test_null_playbook_id_always_accepted_with_empty_allowlist():
    validate_assessment(_assessment(recommended_playbook_id=None), _pack())  # must not raise


def test_empty_refs_never_hallucinate():
    minimal = _assessment(
        affected_assets=[], evidence_refs=[], detection_refs=[], attack_techniques=[]
    )
    validate_assessment(minimal, _pack())  # must not raise
