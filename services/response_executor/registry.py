"""The closed set of MissionNet action handlers (blueprint Phase 7 §3-4). Each handler makes
exactly one real HTTP call to one specific, named MissionNet endpoint - there is no generic
`execute(url, method, body)` capability anywhere here, and no handler accepts a caller-supplied URL,
command, or query. This mirrors `apps/demo_control/actions.py`'s closed-action pattern exactly,
because the same safety argument applies: a fixed, reviewable list of functions is what makes "the
LLM can never execute a response action" a structural fact rather than a policy.
"""

from collections.abc import Awaitable, Callable

import httpx

from services.response_executor.models import ActionOutcome, ExecutionContext, ResolvedTarget


def _lab_headers(ctx: ExecutionContext) -> dict[str, str]:
    return {"X-Lab-Secret": ctx.missionnet_lab_secret}


def _error_from_response(resp: httpx.Response) -> ActionOutcome:
    return ActionOutcome(
        success=False, error_code=str(resp.status_code), error_message=resp.text[:500]
    )


async def handle_revoke_test_token(
    client: httpx.AsyncClient, target: ResolvedTarget, ctx: ExecutionContext
) -> ActionOutcome:
    resp = await client.post(
        f"/lab/tokens/{target.target_id}/revoke",
        headers=_lab_headers(ctx),
        json={"reason": "response_executor", "scenario_id": ctx.scenario_id},
    )
    if resp.status_code >= 400:
        return _error_from_response(resp)
    body = resp.json()
    return ActionOutcome(success=True, result_metadata={"valid": body.get("valid")})


async def handle_rotate_test_token(
    client: httpx.AsyncClient, target: ResolvedTarget, ctx: ExecutionContext
) -> ActionOutcome:
    resp = await client.post(
        f"/lab/tokens/{target.target_id}/rotate",
        headers=_lab_headers(ctx),
        json={"reason": "response_executor", "scenario_id": ctx.scenario_id},
    )
    if resp.status_code >= 400:
        return _error_from_response(resp)
    body = resp.json()
    return ActionOutcome(
        success=True,
        result_metadata={
            "old_token_id": body["old_token_id"],
            "new_token_id": body["new_token_id"],
        },
    )


async def handle_suspend_test_user(
    client: httpx.AsyncClient, target: ResolvedTarget, ctx: ExecutionContext
) -> ActionOutcome:
    resp = await client.post(
        f"/lab/users/{target.target_id}/suspend",
        headers=_lab_headers(ctx),
        json={"reason": "response_executor", "scenario_id": ctx.scenario_id},
    )
    if resp.status_code >= 400:
        return _error_from_response(resp)
    body = resp.json()
    return ActionOutcome(success=True, result_metadata={"status": body.get("status")})


async def handle_quarantine_workload(
    client: httpx.AsyncClient, target: ResolvedTarget, ctx: ExecutionContext
) -> ActionOutcome:
    resp = await client.post(
        f"/lab/assets/{target.target_id}/quarantine",
        headers=_lab_headers(ctx),
        json={"reason": "response_executor", "scenario_id": ctx.scenario_id},
    )
    if resp.status_code >= 400:
        return _error_from_response(resp)
    body = resp.json()
    return ActionOutcome(
        success=True,
        result_metadata={"status": body.get("status"), "network_state": body.get("network_state")},
    )


async def handle_preserve_evidence(
    client: httpx.AsyncClient, target: ResolvedTarget, ctx: ExecutionContext
) -> ActionOutcome:
    resp = await client.post(
        "/lab/evidence/snapshot",
        headers=_lab_headers(ctx),
        json={
            "reason": f"response_executor for incident {target.target_id}",
            "scenario_id": ctx.scenario_id,
        },
    )
    if resp.status_code >= 400:
        return _error_from_response(resp)
    body = resp.json()
    return ActionOutcome(success=True, result_metadata={"snapshot_id": body["snapshot_id"]})


async def handle_request_replacement_instance(
    client: httpx.AsyncClient, target: ResolvedTarget, ctx: ExecutionContext
) -> ActionOutcome:
    resp = await client.post(
        f"/lab/assets/{target.target_id}/request-replacement",
        headers=_lab_headers(ctx),
        json={"reason": "response_executor", "scenario_id": ctx.scenario_id},
    )
    if resp.status_code >= 400:
        return _error_from_response(resp)
    body = resp.json()
    return ActionOutcome(
        success=True, result_metadata={"replacement_asset_id": body["replacement_asset_id"]}
    )


async def handle_verify_service_health(
    client: httpx.AsyncClient, target: ResolvedTarget, ctx: ExecutionContext
) -> ActionOutcome:
    """A read, not a mutation - no lab secret needed. Recording the asset's status is the action
    itself; `verifier.py`'s `service_healthy` check independently re-reads the same state to decide
    pass/fail, so the two are never the same HTTP call trusting itself."""
    resp = await client.get(f"/assets/{target.target_id}")
    if resp.status_code >= 400:
        return _error_from_response(resp)
    body = resp.json()
    return ActionOutcome(success=True, result_metadata={"status": body.get("status")})


ActionHandler = Callable[
    [httpx.AsyncClient, ResolvedTarget, ExecutionContext], Awaitable[ActionOutcome]
]

ACTION_HANDLERS: dict[str, ActionHandler] = {
    "revoke_test_token": handle_revoke_test_token,
    "rotate_test_token": handle_rotate_test_token,
    "suspend_test_user": handle_suspend_test_user,
    "quarantine_workload": handle_quarantine_workload,
    "preserve_evidence": handle_preserve_evidence,
    "request_replacement_instance": handle_request_replacement_instance,
    "verify_service_health": handle_verify_service_health,
}
"""Deliberately missing `restore_workload_network` - it exists in the Phase 6 action registry as a
schema/description, but only ever runs as a *rollback* handler (`rollback.py`), never as a forward
playbook action - no playbook lists it as a step. There is no other action_id any playbook can
reference that isn't a key here (`tests/unit/test_response_executor_registry.py` checks this)."""
