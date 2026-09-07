"""The response executor's orchestration (blueprint Phase 7 §2, §9, §13, §14). This is the ONLY
function that moves a `ResponsePlan.execution_status` off `NOT_EXECUTED` - route handlers in
`apps/api/execution_routes.py` call `execute_response_plan`/`rollback_response_plan` and nothing
else. No import here, at any depth, reaches `ai/` or `services/ai_analyst/` - see
`tests/adversarial/test_executor_ai_isolation.py`.
"""

import uuid
from datetime import UTC, datetime
from typing import cast

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.audit import write_audit
from domain.models.orm import ActionResult, Incident, ResponsePlan
from services.ai_analyst.evidence import build_evidence_pack
from services.policy_engine.actions import ACTION_REGISTRY
from services.policy_engine.engine import POLICY_BUNDLE_VERSION, evaluate_policy
from services.policy_engine.playbooks import PlaybookDefinition, get_playbook
from services.policy_engine.service import PlanStateError
from services.response_executor import EXECUTOR_VERSION
from services.response_executor.models import (
    ExecutionBlockedError,
    ExecutionContext,
    ExecutionInProgressError,
    PlanNotFoundError,
    ResolvedTarget,
    TargetType,
)
from services.response_executor.registry import ACTION_HANDLERS
from services.response_executor.rollback import ROLLBACK_HANDLERS
from services.response_executor.targets import resolve_target
from services.response_executor.verifier import VERIFIERS

TERMINAL_EXECUTION_STATUSES = ("SUCCEEDED", "FAILED", "ROLLED_BACK", "ROLLBACK_FAILED")
IN_PROGRESS_EXECUTION_STATUSES = ("EXECUTING", "VERIFYING", "ROLLING_BACK")
ROLLBACK_ELIGIBLE_EXECUTION_STATUSES = ("SUCCEEDED", "FAILED")


def _target_from_record(record: ActionResult) -> ResolvedTarget:
    """Reconstructs a ResolvedTarget from a persisted ActionResult - used when verifying or
    rolling back an action whose target was resolved (and stored) in an earlier step or run."""
    return ResolvedTarget(
        target_type=cast(TargetType, record.target_type or "incident"),
        target_id=record.target_id or "",
    )


async def _load_action_results(session: AsyncSession, plan_id: str) -> dict[int, ActionResult]:
    stmt = select(ActionResult).where(ActionResult.response_plan_id == plan_id)
    rows = (await session.execute(stmt)).scalars().all()
    return {r.action_index: r for r in rows}


async def _block(session: AsyncSession, plan: ResponsePlan, reason: str) -> None:
    """Pre-execution revalidation failed (blueprint §9): record why, but never move
    execution_status off NOT_EXECUTED - a blocked attempt is not a failed execution."""
    plan.execution_block_reason = reason
    await session.commit()
    raise ExecutionBlockedError(reason)


async def _revalidate(
    session: AsyncSession, plan: ResponsePlan
) -> tuple[Incident, PlaybookDefinition]:
    if plan.status != "APPROVED":
        await _block(session, plan, f"plan status is {plan.status}, not APPROVED")

    incident = await session.get(Incident, plan.incident_id)
    if incident is None:
        await _block(session, plan, "incident no longer exists")

    playbook = get_playbook(plan.playbook_id)
    if playbook is None or not playbook.enabled:
        await _block(session, plan, f"playbook {plan.playbook_id} no longer exists or is disabled")
    assert playbook is not None  # narrowed by _block raising above

    if playbook.version != plan.playbook_version:
        await _block(
            session,
            plan,
            f"playbook version changed since approval "
            f"({plan.playbook_version} -> {playbook.version})",
        )

    if POLICY_BUNDLE_VERSION != plan.policy_bundle_version:
        await _block(
            session,
            plan,
            f"policy bundle changed since approval "
            f"({plan.policy_bundle_version} -> {POLICY_BUNDLE_VERSION})",
        )

    pack = await build_evidence_pack(session, plan.incident_id)
    if pack is None:
        await _block(session, plan, "incident evidence no longer available")
    assert pack is not None

    decision = evaluate_policy(playbook, pack)
    if not decision.allowed:
        await _block(
            session, plan, f"incident no longer eligible: {'; '.join(decision.blocking_reasons)}"
        )

    assert incident is not None
    return incident, playbook


async def execute_response_plan(
    session: AsyncSession,
    *,
    plan_id: str,
    actor: str,
    missionnet_base_url: str,
    missionnet_lab_secret: str,
) -> ResponsePlan:
    """Idempotent: calling this on a plan already in a terminal execution state (SUCCEEDED/FAILED/
    ROLLED_BACK/ROLLBACK_FAILED) just returns it unchanged rather than re-running anything. Calling
    it while a previous execute is genuinely mid-flight raises ExecutionInProgressError instead of
    silently queuing a second attempt."""
    plan = await session.get(ResponsePlan, plan_id)
    if plan is None:
        raise PlanNotFoundError(plan_id)

    if plan.execution_status in TERMINAL_EXECUTION_STATUSES:
        return plan
    if plan.execution_status in IN_PROGRESS_EXECUTION_STATUSES:
        raise ExecutionInProgressError(
            f"plan {plan_id} execution already in progress ({plan.execution_status})"
        )

    incident, playbook = await _revalidate(session, plan)

    ctx = ExecutionContext(
        missionnet_base_url=missionnet_base_url,
        missionnet_lab_secret=missionnet_lab_secret,
        scenario_id=plan.scenario_id,
        executor_version=EXECUTOR_VERSION,
    )

    async with httpx.AsyncClient(base_url=missionnet_base_url, timeout=15.0) as client:
        try:
            health_resp = await client.get("/health")
            health_resp.raise_for_status()
        except httpx.HTTPError as exc:
            await _block(session, plan, f"MissionNet unavailable: {exc}")

        prior_results = await _load_action_results(session, plan_id)

        resolved: dict[int, ResolvedTarget | None] = {}
        for idx, action in enumerate(playbook.actions):
            target = await resolve_target(
                action=action,
                action_index=idx,
                session=session,
                incident=incident,
                client=client,
                prior_results=prior_results,
            )
            if target is None and action.required:
                await _block(
                    session,
                    plan,
                    f"cannot resolve required target for action[{idx}] {action.action_id} "
                    f"(target_source={action.target_source})",
                )
            resolved[idx] = target

        plan.execution_status = "EXECUTING"
        plan.executed_by = actor
        plan.execution_started_at = datetime.now(UTC)
        plan.executor_version = EXECUTOR_VERSION
        plan.execution_block_reason = None
        await write_audit(
            session,
            entity_type="incident",
            entity_id=plan.incident_id,
            action="response_plan.execution_started",
            actor=actor,
            scenario_id=plan.scenario_id,
            detail={"response_plan_id": plan_id, "executor_version": EXECUTOR_VERSION},
        )
        await session.commit()

        for idx, action in enumerate(playbook.actions):
            existing = prior_results.get(idx)
            if existing is not None and existing.status in ("SUCCEEDED", "SKIPPED"):
                continue  # idempotent resume: already done

            record = existing
            if record is None:
                record = ActionResult(
                    action_result_id=f"ACT-{uuid.uuid4()}",
                    response_plan_id=plan_id,
                    action_index=idx,
                    action_id=action.action_id,
                    required=action.required,
                )
                session.add(record)

            # Re-resolve now, not just re-use the up-front `resolved[idx]` - a target like
            # verify_service_health's may legitimately depend on another action's outcome *from
            # earlier in this same execution* (e.g. the replacement asset request_replacement_
            # instance just created a moment ago), which the up-front pass - computed before any
            # action had actually run - could not yet see. The up-front pass exists only to
            # decide whether to block execution before it starts; this is the resolution that
            # actually governs what runs.
            target = await resolve_target(
                action=action,
                action_index=idx,
                session=session,
                incident=incident,
                client=client,
                prior_results=prior_results,
            )
            if target is None:
                record.status = "SKIPPED"
                record.verification_status = "NOT_APPLICABLE"
                record.rollback_status = "NOT_APPLICABLE"
                record.completed_at = datetime.now(UTC)
                await write_audit(
                    session,
                    entity_type="incident",
                    entity_id=plan.incident_id,
                    action="response_plan.action_skipped",
                    actor=actor,
                    scenario_id=plan.scenario_id,
                    detail={
                        "action_index": idx,
                        "action_id": action.action_id,
                        "required": action.required,
                    },
                )
                await session.commit()
                prior_results[idx] = record
                continue

            record.target_type = target.target_type
            record.target_id = target.target_id
            record.status = "RUNNING"
            record.started_at = datetime.now(UTC)
            await write_audit(
                session,
                entity_type="incident",
                entity_id=plan.incident_id,
                action="response_plan.action_started",
                actor=actor,
                scenario_id=plan.scenario_id,
                detail={
                    "action_index": idx,
                    "action_id": action.action_id,
                    "target_type": target.target_type,
                    "target_id": target.target_id,
                },
            )
            await session.commit()

            handler = ACTION_HANDLERS[action.action_id]
            outcome = await handler(client, target, ctx)
            record.completed_at = datetime.now(UTC)
            record.result_metadata = outcome.result_metadata
            record.status = "SUCCEEDED" if outcome.success else "FAILED"
            record.error_code = outcome.error_code
            record.error_message = outcome.error_message
            await write_audit(
                session,
                entity_type="incident",
                entity_id=plan.incident_id,
                action="response_plan.action_result",
                actor=actor,
                scenario_id=plan.scenario_id,
                detail={
                    "action_index": idx,
                    "action_id": action.action_id,
                    "status": record.status,
                    "error_code": outcome.error_code,
                },
            )
            await session.commit()
            prior_results[idx] = record

            if not outcome.success and action.required:
                break  # fail fast: don't attempt later actions once a mandatory one has failed

        plan.execution_status = "VERIFYING"
        await session.commit()

        for idx, action in enumerate(playbook.actions):
            record = prior_results.get(idx)
            if record is None or record.status != "SUCCEEDED":
                continue
            action_def = ACTION_REGISTRY[action.action_id]
            verifier = VERIFIERS.get(action_def.expected_verification)
            if verifier is None:
                record.verification_status = "NOT_APPLICABLE"
            else:
                target = _target_from_record(record)
                v_outcome = await verifier(client, target, record)
                record.verification_status = "VERIFIED" if v_outcome.verified else "FAILED"
                record.verification_detail = v_outcome.detail
                await write_audit(
                    session,
                    entity_type="incident",
                    entity_id=plan.incident_id,
                    action="response_plan.action_verified",
                    actor=actor,
                    scenario_id=plan.scenario_id,
                    detail={
                        "action_index": idx,
                        "action_id": action.action_id,
                        "verification_status": record.verification_status,
                    },
                )
            await session.commit()

        success = all(
            (r := prior_results.get(idx)) is not None
            and r.status == "SUCCEEDED"
            and r.verification_status in ("VERIFIED", "NOT_APPLICABLE")
            for idx, action in enumerate(playbook.actions)
            if action.required
        )

        if success:
            plan.execution_status = "SUCCEEDED"
            plan.execution_completed_at = datetime.now(UTC)
            await write_audit(
                session,
                entity_type="incident",
                entity_id=plan.incident_id,
                action="response_plan.execution_succeeded",
                actor=actor,
                scenario_id=plan.scenario_id,
                detail={"response_plan_id": plan_id},
            )
            await session.commit()
            await session.refresh(plan)
            return plan

        plan.execution_status = "FAILED"
        await write_audit(
            session,
            entity_type="incident",
            entity_id=plan.incident_id,
            action="response_plan.execution_failed",
            actor=actor,
            scenario_id=plan.scenario_id,
            detail={"response_plan_id": plan_id},
        )
        await session.commit()

        if plan.reversible:
            await _run_rollback(
                session, plan=plan, prior_results=prior_results, client=client, ctx=ctx, actor=actor
            )

        await session.refresh(plan)
        return plan


async def _run_rollback(
    session: AsyncSession,
    *,
    plan: ResponsePlan,
    prior_results: dict[int, ActionResult],
    client: httpx.AsyncClient,
    ctx: ExecutionContext,
    actor: str,
) -> None:
    plan.execution_status = "ROLLING_BACK"
    await write_audit(
        session,
        entity_type="incident",
        entity_id=plan.incident_id,
        action="response_plan.rollback_started",
        actor=actor,
        scenario_id=plan.scenario_id,
        detail={"response_plan_id": plan.response_plan_id},
    )
    await session.commit()

    any_rolled_back = False
    any_failed = False
    for idx in sorted(prior_results.keys(), reverse=True):
        record = prior_results[idx]
        if record.status != "SUCCEEDED":
            continue
        handler = ROLLBACK_HANDLERS.get(record.action_id)
        if handler is None:
            record.rollback_status = "NOT_APPLICABLE"
            await session.commit()
            continue

        record.rollback_status = "PENDING"
        await session.commit()
        target = _target_from_record(record)
        outcome = await handler(client, target, ctx, record)
        if outcome.success:
            record.rollback_status = "ROLLED_BACK"
            record.rolled_back_at = datetime.now(UTC)
            any_rolled_back = True
        else:
            record.rollback_status = "FAILED"
            record.error_message = outcome.error_message
            any_failed = True
        await write_audit(
            session,
            entity_type="incident",
            entity_id=plan.incident_id,
            action="response_plan.rollback_result",
            actor=actor,
            scenario_id=plan.scenario_id,
            detail={
                "action_index": idx,
                "action_id": record.action_id,
                "rollback_status": record.rollback_status,
            },
        )
        await session.commit()

    if any_failed:
        plan.execution_status = "ROLLBACK_FAILED"
    elif any_rolled_back:
        plan.execution_status = "ROLLED_BACK"
    # else: nothing was rollback-capable among what succeeded - stays FAILED, correctly.
    plan.execution_completed_at = datetime.now(UTC)
    await write_audit(
        session,
        entity_type="incident",
        entity_id=plan.incident_id,
        action="response_plan.rollback_completed",
        actor=actor,
        scenario_id=plan.scenario_id,
        detail={
            "response_plan_id": plan.response_plan_id,
            "execution_status": plan.execution_status,
        },
    )
    await session.commit()


async def rollback_response_plan(
    session: AsyncSession,
    *,
    plan_id: str,
    actor: str,
    missionnet_base_url: str,
    missionnet_lab_secret: str,
) -> ResponsePlan:
    """Manual rollback (blueprint §11) - for a plan that finished SUCCEEDED (or FAILED with some
    successful steps) but an analyst now wants undone, independent of the automatic rollback-on-
    failure `execute_response_plan` already attempts internally."""
    plan = await session.get(ResponsePlan, plan_id)
    if plan is None:
        raise PlanNotFoundError(plan_id)
    if not plan.reversible:
        raise PlanStateError(f"playbook {plan.playbook_id} is not reversible")
    if plan.execution_status not in ROLLBACK_ELIGIBLE_EXECUTION_STATUSES:
        raise PlanStateError(f"cannot roll back a plan in execution_status {plan.execution_status}")

    prior_results = await _load_action_results(session, plan_id)
    if not any(r.status == "SUCCEEDED" for r in prior_results.values()):
        raise PlanStateError("no successful actions to roll back")

    ctx = ExecutionContext(
        missionnet_base_url=missionnet_base_url,
        missionnet_lab_secret=missionnet_lab_secret,
        scenario_id=plan.scenario_id,
        executor_version=EXECUTOR_VERSION,
    )
    async with httpx.AsyncClient(base_url=missionnet_base_url, timeout=15.0) as client:
        await _run_rollback(
            session, plan=plan, prior_results=prior_results, client=client, ctx=ctx, actor=actor
        )

    await session.refresh(plan)
    return plan
