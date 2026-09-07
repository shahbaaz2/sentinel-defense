"""Phase 6: the deterministic policy engine (blueprint §7-8, §23). Every negative case here is a
pure function test against a manually built EvidencePack - no DB, no AI, no live services. Each
proves the policy engine blocks a specific ineligible combination with a real `blocking_reasons`
entry, never a silent allow.
"""

from datetime import UTC, datetime

from services.ai_analyst.evidence import (
    EvidenceAsset,
    EvidenceDetection,
    EvidenceEvent,
    EvidencePack,
)
from services.policy_engine.engine import evaluate_policy
from services.policy_engine.playbooks import PlaybookAction, get_playbook

T0 = datetime(2026, 9, 6, 12, 0, 0, tzinfo=UTC)


def _detection(**overrides) -> EvidenceDetection:
    defaults: dict = dict(
        detection_id="D1",
        rule_id="DET-002",
        rule_name="Mission-Critical Asset Degraded Unexpectedly",
        severity="high",
        confidence=1.0,
        evidence_summary="e",
        mitre_techniques=[],
        event_ids=["E1"],
    )
    defaults.update(overrides)
    return EvidenceDetection(**defaults)


def _pack(**overrides) -> EvidencePack:
    defaults: dict = dict(
        incident_id="INC-1",
        incident_title="t",
        incident_severity="high",
        incident_status="OPEN",
        incident_category="asset-degradation",
        incident_summary="s",
        primary_asset_id="mission-data-api-01",
        scenario_id="SCN-010",
        first_seen=T0,
        last_seen=T0,
        asset_context=EvidenceAsset(
            asset_id="mission-data-api-01",
            name="Mission Data API",
            asset_type="service",
            environment="lab",
            criticality=5,
            status="degraded",
            mission_role="data",
        ),
        detections=[_detection()],
        events=[
            EvidenceEvent(
                event_id="E1",
                timestamp=T0,
                source="missionnet",
                event_category="application",
                event_type="asset.degrade",
                severity="high",
                asset_id="mission-data-api-01",
                user_id=None,
                summary="s",
            )
        ],
        known_attack_techniques=[],
    )
    defaults.update(overrides)
    return EvidencePack(**defaults)


def test_rp003_allowed_for_a_matching_asset_degradation_incident():
    decision = evaluate_policy(get_playbook("RP-003"), _pack())
    assert decision.allowed
    assert decision.decision == "ALLOW"
    assert decision.blocking_reasons == []
    assert decision.requires_human_approval is True


def test_rp005_requires_two_detections():
    decision = evaluate_policy(get_playbook("RP-005"), _pack())  # only 1 detection
    assert not decision.allowed
    assert any("linked detection" in r for r in decision.blocking_reasons)


def test_rp005_allowed_with_two_detections():
    pack = _pack(detections=[_detection(detection_id="D1"), _detection(detection_id="D2")])
    decision = evaluate_policy(get_playbook("RP-005"), pack)
    assert decision.allowed


# --- negative tests (blueprint §23) ---------------------------------------------------------


def test_nonexistent_playbook_denied():
    decision = evaluate_policy(None, _pack())
    assert not decision.allowed
    assert decision.decision == "DENY"
    assert "playbook does not exist" in decision.blocking_reasons


def test_disabled_playbook_denied():
    playbook = get_playbook("RP-003")
    assert playbook is not None
    disabled = playbook.model_copy(update={"enabled": False})
    decision = evaluate_policy(disabled, _pack())
    assert not decision.allowed
    assert any("disabled" in r for r in decision.blocking_reasons)


def test_wrong_asset_type_denied():
    pack = _pack(
        asset_context=EvidenceAsset(
            asset_id="uav-07",
            name="UAV 07",
            asset_type="service",
            environment="lab",
            criticality=3,
            status="nominal",
            mission_role="edge",  # RP-003 only allows data/gateway/identity
        )
    )
    decision = evaluate_policy(get_playbook("RP-003"), pack)
    assert not decision.allowed
    assert any("mission_role" in r for r in decision.blocking_reasons)


def test_missing_asset_context_denied_when_playbook_requires_one():
    pack = _pack(primary_asset_id=None, asset_context=None)
    decision = evaluate_policy(get_playbook("RP-003"), pack)
    assert not decision.allowed
    assert any("no asset context" in r for r in decision.blocking_reasons)


def test_severity_below_threshold_denied():
    pack = _pack(incident_severity="low")
    decision = evaluate_policy(get_playbook("RP-003"), pack)
    assert not decision.allowed
    assert any("below the playbook's minimum" in r for r in decision.blocking_reasons)


def test_resolved_incident_denied():
    pack = _pack(incident_status="RESOLVED")
    decision = evaluate_policy(get_playbook("RP-003"), pack)
    assert not decision.allowed
    assert any("terminal" in r for r in decision.blocking_reasons)


def test_dismissed_incident_denied():
    pack = _pack(incident_status="DISMISSED")
    decision = evaluate_policy(get_playbook("RP-003"), pack)
    assert not decision.allowed
    assert any("terminal" in r for r in decision.blocking_reasons)


def test_invalid_category_denied():
    pack = _pack(incident_category="data-access-anomaly")  # RP-003 wants asset-degradation
    decision = evaluate_policy(get_playbook("RP-003"), pack)
    assert not decision.allowed
    assert any("allowed categories" in r for r in decision.blocking_reasons)


def test_unknown_action_id_denied_defense_in_depth():
    """PlaybookDefinition's own validator already rejects unknown action IDs at construction time
    (tests/unit/test_playbook_schema.py) - this proves the policy engine has its own independent
    check too, in case a playbook object is ever constructed by some other path that skips
    validation (e.g. `model_construct`)."""
    playbook = get_playbook("RP-003")
    assert playbook is not None
    tampered = playbook.model_construct(
        **{
            **dict(playbook),
            "actions": [PlaybookAction(action_id="launch_nukes", target_source="incident")],
        }
    )
    decision = evaluate_policy(tampered, _pack())
    assert not decision.allowed
    assert any("unknown action_id" in r for r in decision.blocking_reasons)


def test_out_of_scope_target_denied():
    """An incident whose asset exists but plays no role the playbook cares about at all."""
    pack = _pack(
        asset_context=EvidenceAsset(
            asset_id="identity-service-01",
            name="Identity Service",
            asset_type="service",
            environment="lab",
            criticality=5,
            status="nominal",
            mission_role="identity",
        )
    )
    decision = evaluate_policy(get_playbook("RP-003"), pack)  # allows data/gateway/identity
    assert decision.allowed  # identity IS in scope for RP-003 - sanity check for the next assert
    pack_out_of_scope = pack.model_copy(
        update={
            "asset_context": EvidenceAsset(
                asset_id="telemetry-gateway-01",
                name="Telemetry Gateway Alpha",
                asset_type="service",
                environment="lab",
                criticality=4,
                status="nominal",
                mission_role="edge",
            )
        }
    )
    decision2 = evaluate_policy(get_playbook("RP-003"), pack_out_of_scope)
    assert not decision2.allowed


def test_asset_agnostic_playbook_allows_missing_asset_context():
    pack = _pack(
        incident_category="credential-abuse",
        primary_asset_id=None,
        asset_context=None,
        detections=[_detection(rule_id="DET-001", detection_id="D1")],
        incident_severity="medium",
    )
    decision = evaluate_policy(get_playbook("RP-001"), pack)
    assert decision.allowed


def test_reasons_and_blocking_reasons_are_mutually_exclusive_outcome():
    decision = evaluate_policy(get_playbook("RP-003"), _pack())
    assert decision.allowed
    assert decision.blocking_reasons == []
    assert len(decision.reasons) > 0
