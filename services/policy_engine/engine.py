"""The deterministic policy engine (blueprint Phase 6 §7-8) - completely separate from the AI. Its
only input is a `services.ai_analyst.evidence.EvidencePack` (the same curated, real-data pack the
AI Analyst reads) plus a candidate `PlaybookDefinition`; its output is always the same for the same
input, and it never calls the model, a provider, or anything network-facing. This is what "AI only
sees eligible playbooks" and "hallucinated playbook IDs are rejected" both build on.
"""

from dataclasses import dataclass, field
from typing import Literal

from domain.incidents import TERMINAL_INCIDENT_STATUSES
from services.ai_analyst.evidence import EvidencePack
from services.policy_engine.actions import ACTION_REGISTRY
from services.policy_engine.playbooks import SEVERITY_ORDER, PlaybookDefinition, list_playbooks

POLICY_BUNDLE_VERSION = "PB-001"
"""Bump this whenever a rule in `evaluate_policy` changes meaning - every ResponsePlan row records
whichever version was in effect when it was created, so old plans keep an honest record of the
rules that actually applied to them even if this constant later moves to PB-002."""


@dataclass(frozen=True)
class PolicyDecision:
    decision: Literal["ALLOW", "DENY"]
    playbook_id: str
    allowed: bool
    reasons: list[str] = field(default_factory=list)
    blocking_reasons: list[str] = field(default_factory=list)
    requires_human_approval: bool = True


def evaluate_policy(playbook: PlaybookDefinition | None, pack: EvidencePack) -> PolicyDecision:
    """Deterministic - the same (playbook, pack) always produces the same decision. Every rule
    below appends either a `reasons` entry (why it passed) or a `blocking_reasons` entry (why it
    failed); `allowed` is true only if `blocking_reasons` ends up empty."""
    if playbook is None:
        return PolicyDecision(
            decision="DENY",
            playbook_id="",
            allowed=False,
            blocking_reasons=["playbook does not exist"],
        )

    reasons: list[str] = []
    blocking: list[str] = []

    if not playbook.enabled:
        blocking.append(f"playbook {playbook.id} is disabled")
    else:
        reasons.append(f"playbook {playbook.id} is enabled")

    if pack.incident_status in TERMINAL_INCIDENT_STATUSES:
        blocking.append(f"incident is already {pack.incident_status} (terminal)")
    else:
        reasons.append(f"incident status {pack.incident_status} is not terminal")

    if pack.incident_category not in playbook.allowed_incident_categories:
        blocking.append(
            f"incident category {pack.incident_category!r} not in playbook's allowed categories "
            f"{playbook.allowed_incident_categories}"
        )
    else:
        reasons.append(f"incident category {pack.incident_category!r} is allowed")

    incident_severity_rank = SEVERITY_ORDER.get(pack.incident_severity, -1)
    if incident_severity_rank < playbook.severity_floor():
        blocking.append(
            f"incident severity {pack.incident_severity!r} is below the playbook's minimum "
            f"{playbook.minimum_incident_severity}"
        )
    else:
        reasons.append(f"incident severity {pack.incident_severity!r} meets the minimum")

    if len(pack.detections) < playbook.minimum_detection_count:
        blocking.append(
            f"incident has {len(pack.detections)} linked detection(s), playbook requires "
            f"at least {playbook.minimum_detection_count}"
        )
    else:
        reasons.append(f"incident has {len(pack.detections)} linked detection(s)")

    if playbook.allowed_asset_types:
        mission_role = pack.asset_context.mission_role if pack.asset_context else None
        if mission_role is None:
            blocking.append(
                "playbook requires an asset with mission_role in "
                f"{playbook.allowed_asset_types}, but this incident has no asset context"
            )
        elif mission_role not in playbook.allowed_asset_types:
            blocking.append(
                f"asset mission_role {mission_role!r} not in playbook's allowed asset types "
                f"{playbook.allowed_asset_types}"
            )
        else:
            reasons.append(f"asset mission_role {mission_role!r} is allowed")
    else:
        reasons.append("playbook is asset-agnostic")

    unknown_actions = [a.action_id for a in playbook.actions if a.action_id not in ACTION_REGISTRY]
    if unknown_actions:
        blocking.append(f"playbook references unknown action_id(s): {unknown_actions}")
    else:
        reasons.append("all playbook actions are registered")

    allowed = not blocking
    return PolicyDecision(
        decision="ALLOW" if allowed else "DENY",
        playbook_id=playbook.id,
        allowed=allowed,
        reasons=reasons,
        blocking_reasons=blocking,
        requires_human_approval=playbook.requires_human_approval,
    )


def compute_eligible_playbook_ids(pack: EvidencePack) -> list[str]:
    """Every playbook this incident is currently eligible for - what the AI Analyst's evidence
    pack advertises as `available_playbook_ids`, and what an analyst manually choosing a playbook
    is allowed to pick from. A playbook only appears here if `evaluate_policy` allows it outright -
    "requires_human_approval" does not affect eligibility, since approval happens after a response
    plan is created, not before."""
    return [
        playbook.id
        for playbook in list_playbooks()
        if evaluate_policy(playbook, pack).allowed
    ]
