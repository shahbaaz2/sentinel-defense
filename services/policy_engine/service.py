"""Response plan orchestration (blueprint Phase 6 §10-11) - the only place that persists a
`ResponsePlan` row. Route handlers in `apps/api/response_routes.py` call these functions and
nothing else, mirroring `services/ai_analyst/service.py`'s separation from its routes.

The core invariant: a `ResponsePlan` row exists if and only if `evaluate_policy` already said
`allowed=True` for that exact (playbook, incident) pair at creation time - there is no code path
that persists a denied plan and no code path that lets approval logic override a policy denial.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.audit import write_audit
from domain.models.orm import ResponsePlan
from services.ai_analyst.evidence import build_evidence_pack
from services.policy_engine.engine import POLICY_BUNDLE_VERSION, PolicyDecision, evaluate_policy
from services.policy_engine.playbooks import get_playbook

TERMINAL_PLAN_STATUSES = ("APPROVED", "REJECTED", "CANCELLED", "EXPIRED")


class IncidentNotFoundError(Exception):
    pass


async def create_response_plan(
    session: AsyncSession,
    *,
    incident_id: str,
    playbook_id: str,
    actor: str,
    recommendation_source: str,
    ai_assessment_id: str | None,
    note: str | None,
) -> tuple[ResponsePlan | None, PolicyDecision]:
    """Returns (plan, decision). `plan` is None whenever `decision.allowed` is False - see the
    module docstring. Raises IncidentNotFoundError for an unknown incident (a real 404, not a
    policy denial) so the API layer can distinguish the two."""
    pack = await build_evidence_pack(session, incident_id)
    if pack is None:
        raise IncidentNotFoundError(incident_id)

    playbook = get_playbook(playbook_id)
    decision = evaluate_policy(playbook, pack)

    await write_audit(
        session,
        entity_type="incident",
        entity_id=incident_id,
        action="response_plan.policy_evaluated",
        actor=actor,
        scenario_id=pack.scenario_id,
        detail={
            "playbook_id": playbook_id,
            "policy_bundle_version": POLICY_BUNDLE_VERSION,
            "decision": decision.decision,
            "allowed": decision.allowed,
            "blocking_reasons": decision.blocking_reasons,
        },
    )

    if not decision.allowed or playbook is None:
        await session.commit()
        return None, decision

    plan_id = f"RESP-{uuid.uuid4()}"
    plan = ResponsePlan(
        response_plan_id=plan_id,
        incident_id=incident_id,
        playbook_id=playbook.id,
        playbook_version=playbook.version,
        created_by=actor,
        recommendation_source=recommendation_source,
        ai_assessment_id=ai_assessment_id,
        policy_bundle_version=POLICY_BUNDLE_VERSION,
        policy_decision=decision.decision,
        policy_reasons=decision.reasons,
        risk_level=playbook.risk.mission_impact,
        reversible=playbook.reversible,
        status="AWAITING_APPROVAL",
        scenario_id=pack.scenario_id,
        execution_status="EXECUTION_NOT_ENABLED",
    )
    session.add(plan)

    await write_audit(
        session,
        entity_type="incident",
        entity_id=incident_id,
        action="response_plan.created",
        actor=actor,
        scenario_id=pack.scenario_id,
        detail={
            "response_plan_id": plan_id,
            "playbook_id": playbook.id,
            "playbook_version": playbook.version,
            "recommendation_source": recommendation_source,
            "ai_assessment_id": ai_assessment_id,
            "note": note,
        },
    )
    await session.commit()
    await session.refresh(plan)
    return plan, decision


class PlanStateError(Exception):
    """Raised when an approve/reject/cancel is attempted against a plan that isn't in a state
    where that transition is valid - e.g. approving an already-rejected or cancelled plan."""


async def approve_response_plan(
    session: AsyncSession, *, plan_id: str, actor: str, note: str | None
) -> ResponsePlan | None:
    plan = await session.get(ResponsePlan, plan_id)
    if plan is None:
        return None
    if plan.status != "AWAITING_APPROVAL":
        raise PlanStateError(f"cannot approve a plan in status {plan.status}")

    plan.status = "APPROVED"
    plan.approved_by = actor
    plan.approved_at = datetime.now(UTC)

    await write_audit(
        session,
        entity_type="incident",
        entity_id=plan.incident_id,
        action="response_plan.approved",
        actor=actor,
        scenario_id=plan.scenario_id,
        detail={"response_plan_id": plan_id, "playbook_id": plan.playbook_id, "note": note},
    )
    await session.commit()
    await session.refresh(plan)
    return plan


async def reject_response_plan(
    session: AsyncSession, *, plan_id: str, actor: str, reason: str
) -> ResponsePlan | None:
    plan = await session.get(ResponsePlan, plan_id)
    if plan is None:
        return None
    if plan.status != "AWAITING_APPROVAL":
        raise PlanStateError(f"cannot reject a plan in status {plan.status}")

    plan.status = "REJECTED"
    plan.rejected_by = actor
    plan.rejected_at = datetime.now(UTC)
    plan.rejection_reason = reason

    await write_audit(
        session,
        entity_type="incident",
        entity_id=plan.incident_id,
        action="response_plan.rejected",
        actor=actor,
        scenario_id=plan.scenario_id,
        detail={"response_plan_id": plan_id, "playbook_id": plan.playbook_id, "reason": reason},
    )
    await session.commit()
    await session.refresh(plan)
    return plan


async def cancel_response_plan(
    session: AsyncSession, *, plan_id: str, actor: str, note: str | None
) -> ResponsePlan | None:
    plan = await session.get(ResponsePlan, plan_id)
    if plan is None:
        return None
    if plan.status in TERMINAL_PLAN_STATUSES:
        raise PlanStateError(f"cannot cancel a plan already in terminal status {plan.status}")

    plan.status = "CANCELLED"
    plan.cancelled_by = actor
    plan.cancelled_at = datetime.now(UTC)

    await write_audit(
        session,
        entity_type="incident",
        entity_id=plan.incident_id,
        action="response_plan.cancelled",
        actor=actor,
        scenario_id=plan.scenario_id,
        detail={"response_plan_id": plan_id, "playbook_id": plan.playbook_id, "note": note},
    )
    await session.commit()
    await session.refresh(plan)
    return plan


async def get_response_plan(session: AsyncSession, plan_id: str) -> ResponsePlan | None:
    return await session.get(ResponsePlan, plan_id)


async def list_response_plans_for_incident(
    session: AsyncSession, incident_id: str
) -> list[ResponsePlan]:
    result = await session.execute(
        select(ResponsePlan)
        .where(ResponsePlan.incident_id == incident_id)
        .order_by(ResponsePlan.created_at.desc())
    )
    return list(result.scalars().all())


async def list_response_plans(
    session: AsyncSession, *, status: str | None = None, limit: int = 100
) -> list[ResponsePlan]:
    """Across every incident - what the Response Center page shows. `status=AWAITING_APPROVAL`
    is the default view an analyst wants; omitting it returns the full history, newest first."""
    stmt = select(ResponsePlan).order_by(ResponsePlan.created_at.desc()).limit(limit)
    if status is not None:
        stmt = stmt.where(ResponsePlan.status == status)
    result = await session.execute(stmt)
    return list(result.scalars().all())
