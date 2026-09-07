"""Deterministic verification (blueprint Phase 7 §12-13). HTTP 200 from an action's own call does
NOT mean containment succeeded - every check here independently re-reads real MissionNet state
through a separate GET call and inspects the actual field that matters, never just re-checking that
the earlier POST didn't error. A response plan only becomes SUCCEEDED when every mandatory action's
verification here returns `verified=True` - see `executor.py`.
"""

from collections.abc import Awaitable, Callable

import httpx

from domain.models.orm import ActionResult
from services.response_executor.models import ResolvedTarget, VerificationOutcome


async def verify_token_invalid(
    client: httpx.AsyncClient, target: ResolvedTarget, action_result: ActionResult
) -> VerificationOutcome:
    resp = await client.get("/identity/tokens")
    resp.raise_for_status()
    token = next((t for t in resp.json() if t["token_id"] == target.target_id), None)
    if token is None:
        return VerificationOutcome(verified=False, detail={"reason": "token not found"})
    return VerificationOutcome(verified=token["valid"] is False, detail={"valid": token["valid"]})


async def verify_token_rotated(
    client: httpx.AsyncClient, target: ResolvedTarget, action_result: ActionResult
) -> VerificationOutcome:
    new_token_id = action_result.result_metadata.get("new_token_id")
    old_token_id = action_result.result_metadata.get("old_token_id")
    resp = await client.get("/identity/tokens")
    resp.raise_for_status()
    tokens = {t["token_id"]: t for t in resp.json()}
    new_token = tokens.get(new_token_id)
    old_token = tokens.get(old_token_id)
    verified = bool(new_token and new_token["valid"] and old_token and not old_token["valid"])
    return VerificationOutcome(
        verified=verified,
        detail={
            "new_token_valid": new_token["valid"] if new_token else None,
            "old_token_valid": old_token["valid"] if old_token else None,
        },
    )


async def verify_user_suspended(
    client: httpx.AsyncClient, target: ResolvedTarget, action_result: ActionResult
) -> VerificationOutcome:
    resp = await client.get("/identity/users")
    resp.raise_for_status()
    user = next((u for u in resp.json() if u["user_id"] == target.target_id), None)
    if user is None:
        return VerificationOutcome(verified=False, detail={"reason": "user not found"})
    return VerificationOutcome(
        verified=user["status"] == "suspended", detail={"status": user["status"]}
    )


async def verify_workload_isolated(
    client: httpx.AsyncClient, target: ResolvedTarget, action_result: ActionResult
) -> VerificationOutcome:
    resp = await client.get(f"/assets/{target.target_id}")
    if resp.status_code >= 400:
        return VerificationOutcome(verified=False, detail={"reason": f"http {resp.status_code}"})
    asset = resp.json()
    verified = asset["status"] == "quarantined" and asset["network_state"] == "quarantined"
    return VerificationOutcome(
        verified=verified,
        detail={"status": asset["status"], "network_state": asset["network_state"]},
    )


async def verify_network_restored(
    client: httpx.AsyncClient, target: ResolvedTarget, action_result: ActionResult
) -> VerificationOutcome:
    resp = await client.get(f"/assets/{target.target_id}")
    if resp.status_code >= 400:
        return VerificationOutcome(verified=False, detail={"reason": f"http {resp.status_code}"})
    asset = resp.json()
    verified = asset["network_state"] == "normal"
    return VerificationOutcome(verified=verified, detail={"network_state": asset["network_state"]})


async def verify_evidence_snapshot_created(
    client: httpx.AsyncClient, target: ResolvedTarget, action_result: ActionResult
) -> VerificationOutcome:
    snapshot_id = action_result.result_metadata.get("snapshot_id")
    resp = await client.get("/audit", params={"limit": 50})
    resp.raise_for_status()
    found = any(
        e["object_id"] == snapshot_id and e["action"] == "evidence.snapshot" for e in resp.json()
    )
    return VerificationOutcome(verified=found, detail={"snapshot_id": snapshot_id})


async def verify_replacement_provisioned(
    client: httpx.AsyncClient, target: ResolvedTarget, action_result: ActionResult
) -> VerificationOutcome:
    replacement_id = action_result.result_metadata.get("replacement_asset_id")
    resp = await client.get(f"/assets/{replacement_id}")
    if resp.status_code >= 400:
        return VerificationOutcome(verified=False, detail={"reason": f"http {resp.status_code}"})
    asset = resp.json()
    return VerificationOutcome(
        verified=asset["status"] == "nominal", detail={"status": asset["status"]}
    )


async def verify_service_healthy(
    client: httpx.AsyncClient, target: ResolvedTarget, action_result: ActionResult
) -> VerificationOutcome:
    resp = await client.get(f"/assets/{target.target_id}")
    if resp.status_code >= 400:
        return VerificationOutcome(verified=False, detail={"reason": f"http {resp.status_code}"})
    asset = resp.json()
    return VerificationOutcome(
        verified=asset["status"] == "nominal", detail={"status": asset["status"]}
    )


VerifierFn = Callable[
    [httpx.AsyncClient, ResolvedTarget, ActionResult], Awaitable[VerificationOutcome]
]

VERIFIERS: dict[str, VerifierFn] = {
    "token_invalid": verify_token_invalid,
    "token_rotated": verify_token_rotated,
    "user_suspended": verify_user_suspended,
    "workload_isolated": verify_workload_isolated,
    "network_restored": verify_network_restored,
    "evidence_snapshot_created": verify_evidence_snapshot_created,
    "replacement_provisioned": verify_replacement_provisioned,
    "service_healthy": verify_service_healthy,
}
"""Keyed by `ActionDefinition.expected_verification` (services/policy_engine/actions.py), not by
action_id - `network_restored` is only ever used to verify a *rollback* (of quarantine_workload),
never a forward action, since no action's own `expected_verification` is "network_restored"."""
