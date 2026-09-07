"""Declarative playbook schema + strict loader (blueprint Phase 6 §3, §6). Mirrors
`apps/demo_control/scenarios.py`'s pattern: this module only parses and validates the YAML shape -
`engine.py` is the only thing that decides whether a loaded, valid playbook is *eligible* for a
given incident, and no execution ever happens in Phase 6.

YAML playbooks reference `action_id`s only - never shell commands, SQL, or any executable payload.
An invalid playbook (unknown action ID, missing rollback for a reversible playbook, etc.) raises at
load time rather than being silently skipped, so a catalog error is caught immediately rather than
surfacing later as a confusing "no eligible playbooks" result.
"""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator

from services.policy_engine.actions import ACTION_REGISTRY

PLAYBOOKS_DIR = Path(__file__).resolve().parents[2] / "playbooks"

Severity = Literal["info", "low", "medium", "high", "critical"]
SEVERITY_ORDER: dict[str, int] = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}


class PlaybookAction(BaseModel):
    action_id: str
    target_source: Literal["incident", "incident_asset", "incident_identity"]
    """Where a future executor would resolve this action's target from - Phase 6 never resolves or
    uses this beyond display; it exists so the catalog is execution-ready for a later phase."""


class PlaybookRisk(BaseModel):
    mission_impact: Literal["low", "medium", "high", "critical"]
    reversibility: Literal["low", "medium", "high"]


class PlaybookDefinition(BaseModel):
    id: str
    version: str = "1.0"
    name: str
    description: str
    enabled: bool = True
    allowed_asset_types: list[str] = Field(default_factory=list)
    """Matched against the affected asset's MissionNet `mission_role` (edge/gateway/data/identity),
    not Sentinel's `asset_type` column - every MissionNet asset has `asset_type == "service"`, so
    that column can never discriminate between playbooks in this deployment. Empty list means
    asset-agnostic (no asset requirement at all - e.g. identity-focused playbooks)."""
    allowed_incident_categories: list[str] = Field(min_length=1)
    minimum_incident_severity: list[Severity] = Field(min_length=1)
    """Interpreted as a floor, not a strict set: the *lowest*-ranked entry is the minimum severity
    an incident must have (by SEVERITY_ORDER) to qualify - so `[high]` means "high or critical"."""
    minimum_detection_count: int = Field(default=1, ge=1)
    requires_human_approval: bool = True
    reversible: bool
    actions: list[PlaybookAction] = Field(min_length=1)
    verification: list[str] = Field(min_length=1)
    rollback: list[str] = Field(default_factory=list)
    risk: PlaybookRisk

    @model_validator(mode="after")
    def _validate_actions_known(self) -> "PlaybookDefinition":
        for action in self.actions:
            if action.action_id not in ACTION_REGISTRY:
                raise ValueError(
                    f"playbook {self.id!r} references unknown action_id {action.action_id!r}"
                )
        return self

    @model_validator(mode="after")
    def _validate_rollback_consistency(self) -> "PlaybookDefinition":
        if self.reversible and not self.rollback:
            raise ValueError(
                f"playbook {self.id!r} is marked reversible but declares no rollback steps"
            )
        if not self.reversible and self.rollback:
            raise ValueError(
                f"playbook {self.id!r} is marked non-reversible but declares rollback steps"
            )
        return self

    def severity_floor(self) -> int:
        return min(SEVERITY_ORDER[s] for s in self.minimum_incident_severity)


def _load_file(path: Path) -> PlaybookDefinition:
    with open(path) as f:
        raw = yaml.safe_load(f)
    playbook = PlaybookDefinition.model_validate(raw)
    if playbook.id != path.stem:
        raise ValueError(f"playbook file {path.name} declares id {playbook.id!r} - must match")
    return playbook


def list_playbooks() -> list[PlaybookDefinition]:
    """Uniqueness (blueprint §6) is guaranteed structurally, not by a separate duplicate check: a
    filesystem cannot hold two files with the same name, and `_load_file` requires each file's
    declared `id` to equal its own filename - so two files can never legally declare the same id."""
    if not PLAYBOOKS_DIR.exists():
        return []
    playbooks: list[PlaybookDefinition] = []
    for path in sorted(PLAYBOOKS_DIR.glob("RP-*.yaml")):
        playbooks.append(_load_file(path))
    return playbooks


def get_playbook(playbook_id: str) -> PlaybookDefinition | None:
    path = PLAYBOOKS_DIR / f"{playbook_id}.yaml"
    if not path.exists():
        return None
    return _load_file(path)
