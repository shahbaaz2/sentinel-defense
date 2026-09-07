"""Phase 6 blueprint §20: "The LLM can recommend. The LLM cannot approve, reject, change approval
status, execute, or claim action succeeded." Proven structurally, the same way Phase 5 proved the
AI Analyst has no write path to incident state (tests/adversarial/test_prompt_injection.py) - not
by trusting that the model won't try, but by there being no field, no code path, and no import that
could let it.
"""

import inspect

import pytest
from pydantic import ValidationError

from ai.schemas import AIIncidentAssessment
from apps.api.schemas import ResponsePlanApprove, ResponsePlanReject
from services.policy_engine import service as policy_service


def test_ai_assessment_schema_has_no_approval_related_field():
    field_names = set(AIIncidentAssessment.model_fields.keys())
    assert not any("approv" in name.lower() for name in field_names)
    assert not any("execut" in name.lower() for name in field_names)


def test_ai_assessment_schema_rejects_an_injected_approval_field():
    payload = dict(
        classification="benign",
        confidence=0.9,
        summary="s",
        affected_assets=[],
        evidence_refs=[],
        detection_refs=[],
        hypotheses=[],
        recommended_investigation_steps=[],
        attack_techniques=[],
        recommended_playbook_id=None,
        limitations=[],
        approval_status="APPROVED",  # not a real field - must be rejected outright
    )
    with pytest.raises(ValidationError):
        AIIncidentAssessment.model_validate(payload)


def test_response_plan_approval_requires_an_explicit_human_actor():
    with pytest.raises(ValidationError):
        ResponsePlanApprove.model_validate({"note": "looks fine"})
    with pytest.raises(ValidationError):
        ResponsePlanReject.model_validate({"reason": "no"})
    # both succeed once an actor is present
    ResponsePlanApprove.model_validate({"actor": "j.analyst"})
    ResponsePlanReject.model_validate({"actor": "j.analyst", "reason": "no"})


def test_policy_engine_service_never_imports_the_llm_provider():
    """The module that can move a response plan to APPROVED/REJECTED has zero import-time contact
    with anything that talks to a model - not "the AI didn't call it this time", but "there is no
    line of code by which it could"."""
    source = inspect.getsource(policy_service)
    assert "ai.providers" not in source
    assert "import mlx" not in source
    forbidden_calls = ("structured_completion", "get_provider(")
    for call in forbidden_calls:
        assert call not in source


def test_approve_and_reject_functions_take_no_ai_assessment_parameter():
    approve_params = set(inspect.signature(policy_service.approve_response_plan).parameters)
    reject_params = set(inspect.signature(policy_service.reject_response_plan).parameters)
    for params in (approve_params, reject_params):
        assert not any("assessment" in p or "ai" in p.lower() for p in params)
