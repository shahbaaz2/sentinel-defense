"""Rollback handlers (blueprint Phase 7 §14) - one per action_id that can genuinely be undone. An
action_id with no entry here has no rollback capability at all; the executor checks this dict's
keys, not a hopeful assumption, before ever attempting a rollback. Never claim rollback support for
an action that cannot actually be restored (`request_replacement_instance`, `preserve_evidence`,
`verify_service_health` are intentionally absent - see docs/response-executor.md).
"""

from collections.abc import Awaitable, Callable

import httpx

from domain.models.orm import ActionResult
from services.response_executor.models import ActionOutcome, ExecutionContext, ResolvedTarget


def _lab_headers(ctx: ExecutionContext) -> dict[str, str]:
    return {"X-Lab-Secret": ctx.missionnet_lab_secret}


def _error_from_response(resp: httpx.Response) -> ActionOutcome:
    return ActionOutcome(
        success=False, error_code=str(resp.status_code), error_message=resp.text[:500]
    )


async def rollback_quarantine_workload(
    client: httpx.AsyncClient, target: ResolvedTarget, ctx: ExecutionContext, original: ActionResult
) -> ActionOutcome:
    resp = await client.post(
        f"/lab/assets/{target.target_id}/restore",
        headers=_lab_headers(ctx),
        json={"reason": "response_executor_rollback", "scenario_id": ctx.scenario_id},
    )
    if resp.status_code >= 400:
        return _error_from_response(resp)
    body = resp.json()
    return ActionOutcome(success=True, result_metadata={"status": body.get("status")})


async def rollback_suspend_test_user(
    client: httpx.AsyncClient, target: ResolvedTarget, ctx: ExecutionContext, original: ActionResult
) -> ActionOutcome:
    resp = await client.post(
        f"/lab/users/{target.target_id}/reinstate",
        headers=_lab_headers(ctx),
        json={"reason": "response_executor_rollback", "scenario_id": ctx.scenario_id},
    )
    if resp.status_code >= 400:
        return _error_from_response(resp)
    body = resp.json()
    return ActionOutcome(success=True, result_metadata={"status": body.get("status")})


async def rollback_revoke_test_token(
    client: httpx.AsyncClient, target: ResolvedTarget, ctx: ExecutionContext, original: ActionResult
) -> ActionOutcome:
    resp = await client.post(
        f"/lab/tokens/{target.target_id}/reactivate",
        headers=_lab_headers(ctx),
        json={"reason": "response_executor_rollback", "scenario_id": ctx.scenario_id},
    )
    if resp.status_code >= 400:
        return _error_from_response(resp)
    body = resp.json()
    return ActionOutcome(success=True, result_metadata={"valid": body.get("valid")})


async def rollback_rotate_test_token(
    client: httpx.AsyncClient, target: ResolvedTarget, ctx: ExecutionContext, original: ActionResult
) -> ActionOutcome:
    """Undoing a rotation means both halves: reactivate the old token and revoke the new one -
    both IDs come from the original action's own persisted `result_metadata`, never re-derived."""
    old_token_id = original.result_metadata.get("old_token_id")
    new_token_id = original.result_metadata.get("new_token_id")
    if not old_token_id or not new_token_id:
        return ActionOutcome(
            success=False,
            error_code="missing_metadata",
            error_message="original rotate_test_token result has no old/new token IDs to reverse",
        )
    headers = _lab_headers(ctx)
    body_json = {"reason": "response_executor_rollback", "scenario_id": ctx.scenario_id}
    reactivate = await client.post(
        f"/lab/tokens/{old_token_id}/reactivate", headers=headers, json=body_json
    )
    if reactivate.status_code >= 400:
        return _error_from_response(reactivate)
    revoke_new = await client.post(
        f"/lab/tokens/{new_token_id}/revoke", headers=headers, json=body_json
    )
    if revoke_new.status_code >= 400:
        return _error_from_response(revoke_new)
    return ActionOutcome(
        success=True, result_metadata={"reactivated": old_token_id, "revoked": new_token_id}
    )


RollbackHandler = Callable[
    [httpx.AsyncClient, ResolvedTarget, ExecutionContext, ActionResult], Awaitable[ActionOutcome]
]

ROLLBACK_HANDLERS: dict[str, RollbackHandler] = {
    "quarantine_workload": rollback_quarantine_workload,
    "suspend_test_user": rollback_suspend_test_user,
    "revoke_test_token": rollback_revoke_test_token,
    "rotate_test_token": rollback_rotate_test_token,
}
