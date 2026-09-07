"""Phase 6: the playbook catalog is declarative and validated strictly at load time (blueprint §6)
- an invalid playbook must never silently load, and a playbook may only reference action IDs that
actually exist in the registry.
"""

import pytest
import yaml
from pydantic import ValidationError

from services.policy_engine.actions import ACTION_REGISTRY
from services.policy_engine.playbooks import PlaybookDefinition, get_playbook, list_playbooks

VALID_PLAYBOOK: dict = {
    "id": "RP-TEST",
    "version": "1.0",
    "name": "Test Playbook",
    "description": "A playbook used only by tests.",
    "enabled": True,
    "allowed_asset_types": [],
    "allowed_incident_categories": ["credential-abuse"],
    "minimum_incident_severity": ["medium"],
    "requires_human_approval": True,
    "reversible": True,
    "actions": [{"action_id": "preserve_evidence", "target_source": "incident"}],
    "verification": ["evidence_snapshot_created"],
    "rollback": ["undo_something"],
    "risk": {"mission_impact": "low", "reversibility": "high"},
}


def test_real_catalog_loads_without_error():
    playbooks = list_playbooks()
    assert {p.id for p in playbooks} == {"RP-001", "RP-002", "RP-003", "RP-004", "RP-005"}


def test_real_catalog_actions_are_all_registered():
    for playbook in list_playbooks():
        for action in playbook.actions:
            assert action.action_id in ACTION_REGISTRY


def test_get_playbook_returns_none_for_unknown_id():
    assert get_playbook("RP-999") is None


def test_get_playbook_returns_real_definition():
    playbook = get_playbook("RP-001")
    assert playbook is not None
    assert playbook.name == "Authentication Abuse Investigation / Credential Protection"


def test_valid_playbook_parses():
    PlaybookDefinition.model_validate(VALID_PLAYBOOK)


def test_unknown_action_id_rejected():
    bad = {
        **VALID_PLAYBOOK,
        "actions": [{"action_id": "launch_nukes", "target_source": "incident"}],
    }
    with pytest.raises(ValidationError, match="unknown action_id"):
        PlaybookDefinition.model_validate(bad)


def test_reversible_without_rollback_rejected():
    bad = {**VALID_PLAYBOOK, "reversible": True, "rollback": []}
    with pytest.raises(ValidationError, match="declares no rollback"):
        PlaybookDefinition.model_validate(bad)


def test_irreversible_with_rollback_rejected():
    bad = {**VALID_PLAYBOOK, "reversible": False, "rollback": ["something"]}
    with pytest.raises(ValidationError, match="declares rollback steps"):
        PlaybookDefinition.model_validate(bad)


def test_empty_incident_categories_rejected():
    bad = {**VALID_PLAYBOOK, "allowed_incident_categories": []}
    with pytest.raises(ValidationError):
        PlaybookDefinition.model_validate(bad)


def test_empty_severity_list_rejected():
    bad = {**VALID_PLAYBOOK, "minimum_incident_severity": []}
    with pytest.raises(ValidationError):
        PlaybookDefinition.model_validate(bad)


def test_no_actions_rejected():
    bad = {**VALID_PLAYBOOK, "actions": []}
    with pytest.raises(ValidationError):
        PlaybookDefinition.model_validate(bad)


def test_no_verification_rejected():
    bad = {**VALID_PLAYBOOK, "verification": []}
    with pytest.raises(ValidationError):
        PlaybookDefinition.model_validate(bad)


def test_invalid_severity_value_rejected():
    bad = {**VALID_PLAYBOOK, "minimum_incident_severity": ["catastrophic"]}
    with pytest.raises(ValidationError):
        PlaybookDefinition.model_validate(bad)


def test_severity_floor_uses_lowest_ranked_entry():
    playbook = PlaybookDefinition.model_validate(
        {**VALID_PLAYBOOK, "minimum_incident_severity": ["high", "medium"]}
    )
    from services.policy_engine.playbooks import SEVERITY_ORDER

    assert playbook.severity_floor() == SEVERITY_ORDER["medium"]


def test_filename_must_match_declared_id(tmp_path, monkeypatch):
    """Also proves uniqueness structurally: two files can never legally declare the same id, since
    each file's id must equal its own (necessarily unique) filename."""
    (tmp_path / "RP-001.yaml").write_text(yaml.safe_dump({**VALID_PLAYBOOK, "id": "RP-WRONG"}))
    monkeypatch.setattr("services.policy_engine.playbooks.PLAYBOOKS_DIR", tmp_path)
    with pytest.raises(ValueError, match="must match"):
        list_playbooks()


def test_missing_playbooks_dir_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr("services.policy_engine.playbooks.PLAYBOOKS_DIR", tmp_path / "nope")
    assert list_playbooks() == []
