"""The action registry (blueprint Phase 6 §5): a closed set of defensive action *definitions*, not
functions. Nothing in this file executes anything - there is no `execute()`, no shell call, no
HTTP call. Each entry only declares what a future executor phase (not this one) would be allowed to
do, its risk profile, and whether it can be rolled back. Playbooks (`playbooks/*.yaml`) may only
reference `action_id`s that exist here (`services/policy_engine/playbooks.py` enforces this at load
time) - there is no way for a playbook, or the AI, to invent a new action.
"""

from dataclasses import dataclass
from typing import Literal

RiskLevel = Literal["low", "medium", "high", "critical"]


@dataclass(frozen=True)
class ActionDefinition:
    action_id: str
    description: str
    allowed_target_types: tuple[str, ...]
    """What kind of thing this action would apply to, e.g. "asset", "identity_user",
    "service_token", "incident" - matched loosely against a playbook action's `target_source` at
    review time, not enforced by strict validation in Phase 6 (no execution to validate against)."""
    risk_level: RiskLevel
    reversible: bool
    requires_approval: bool
    expected_verification: str
    rollback_capable: bool


ACTIONS: tuple[ActionDefinition, ...] = (
    ActionDefinition(
        action_id="revoke_test_token",
        description="Revoke a MissionNet service token used by the affected identity/asset.",
        allowed_target_types=("service_token",),
        risk_level="medium",
        reversible=True,
        requires_approval=True,
        expected_verification="token_invalid",
        rollback_capable=True,
    ),
    ActionDefinition(
        action_id="rotate_test_token",
        description="Issue a new MissionNet service token and mark the old one revoked.",
        allowed_target_types=("service_token",),
        risk_level="low",
        reversible=True,
        requires_approval=True,
        expected_verification="token_rotated",
        rollback_capable=True,
    ),
    ActionDefinition(
        action_id="suspend_test_user",
        description="Suspend a MissionNet identity user account pending investigation.",
        allowed_target_types=("identity_user",),
        risk_level="medium",
        reversible=True,
        requires_approval=True,
        expected_verification="user_suspended",
        rollback_capable=True,
    ),
    ActionDefinition(
        action_id="quarantine_workload",
        description="Isolate a MissionNet service's network access pending investigation.",
        allowed_target_types=("asset",),
        risk_level="high",
        reversible=True,
        requires_approval=True,
        expected_verification="workload_isolated",
        rollback_capable=True,
    ),
    ActionDefinition(
        action_id="restore_workload_network",
        description="Restore network access to a previously quarantined workload (the rollback "
        "for quarantine_workload).",
        allowed_target_types=("asset",),
        risk_level="medium",
        reversible=True,
        requires_approval=True,
        expected_verification="network_restored",
        rollback_capable=False,
    ),
    ActionDefinition(
        action_id="preserve_evidence",
        description="Snapshot MissionNet audit/telemetry evidence for the incident before any "
        "other action runs.",
        allowed_target_types=("incident",),
        risk_level="low",
        reversible=True,
        requires_approval=False,
        expected_verification="evidence_snapshot_created",
        rollback_capable=False,
    ),
    ActionDefinition(
        action_id="request_replacement_instance",
        description="Request a replacement instance for a degraded asset (synthetic - no real "
        "infrastructure is provisioned by this action definition).",
        allowed_target_types=("asset",),
        risk_level="medium",
        reversible=False,
        requires_approval=True,
        expected_verification="replacement_provisioned",
        rollback_capable=False,
    ),
    ActionDefinition(
        action_id="verify_service_health",
        description="Re-check a MissionNet asset's health/status after a response action.",
        allowed_target_types=("asset",),
        risk_level="low",
        reversible=True,
        requires_approval=False,
        expected_verification="service_healthy",
        rollback_capable=False,
    ),
)

ACTION_REGISTRY: dict[str, ActionDefinition] = {a.action_id: a for a in ACTIONS}


def get_action(action_id: str) -> ActionDefinition | None:
    return ACTION_REGISTRY.get(action_id)
