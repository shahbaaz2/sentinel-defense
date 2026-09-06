"""Phase 5: the structured-output schema is the first defense against malformed AI output
(blueprint AI Analyst §8) - confidence must be bounded, and no undeclared field may sneak
through."""

import pytest
from pydantic import ValidationError

from ai.schemas import AIIncidentAssessment


def _base(**overrides):
    payload = {
        "classification": "credential-stuffing",
        "confidence": 0.8,
        "summary": "Repeated auth failures against one identity.",
        "affected_assets": ["asset-1"],
        "evidence_refs": [{"event_id": "EVT-1", "relevance": "shows the failed logins"}],
        "detection_refs": [{"detection_id": "DET-001-abc", "relevance": "fired on the pattern"}],
        "hypotheses": ["Automated credential stuffing"],
        "recommended_investigation_steps": ["Check source IP reputation"],
        "attack_techniques": ["T1110"],
        "recommended_playbook_id": None,
        "limitations": ["No network telemetry available"],
    }
    payload.update(overrides)
    return payload


def test_valid_assessment_parses():
    assessment = AIIncidentAssessment.model_validate(_base())
    assert assessment.confidence == 0.8
    assert assessment.recommended_playbook_id is None


@pytest.mark.parametrize("confidence", [-0.01, 1.01, 5.0, -3.0])
def test_confidence_out_of_bounds_rejected(confidence):
    with pytest.raises(ValidationError):
        AIIncidentAssessment.model_validate(_base(confidence=confidence))


def test_confidence_boundaries_accepted():
    AIIncidentAssessment.model_validate(_base(confidence=0.0))
    AIIncidentAssessment.model_validate(_base(confidence=1.0))


def test_unknown_field_rejected():
    payload = _base()
    payload["close_incident_now"] = True
    with pytest.raises(ValidationError):
        AIIncidentAssessment.model_validate(payload)


def test_missing_required_field_rejected():
    payload = _base()
    del payload["classification"]
    with pytest.raises(ValidationError):
        AIIncidentAssessment.model_validate(payload)


def test_defaults_allow_empty_lists():
    payload = _base()
    for key in (
        "affected_assets",
        "evidence_refs",
        "detection_refs",
        "hypotheses",
        "recommended_investigation_steps",
        "attack_techniques",
        "limitations",
    ):
        del payload[key]
    assessment = AIIncidentAssessment.model_validate(payload)
    assert assessment.evidence_refs == []
    assert assessment.limitations == []
