"""Response Center API (blueprint Phase 6 §12). Narrow by design: no endpoint accepts an arbitrary
action payload - every response plan references a playbook_id from the fixed catalog, evaluated by
the deterministic policy engine before anything is ever persisted. Approval/rejection require an
explicit actor; nothing in *this* file can execute anything - actual execution is a separate
lifecycle handled entirely by `apps/api/execution_routes.py` / `services/response_executor/`, only
ever reachable from a plan already APPROVED here (see domain/models/orm.py::ResponsePlan).
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.schemas import (
    PlaybookActionOut,
    PlaybookOut,
    PlaybookRiskOut,
    PolicyDecisionOut,
    ResponsePlanApprove,
    ResponsePlanCancel,
    ResponsePlanCreate,
    ResponsePlanOut,
    ResponsePlanReject,
)
from domain.db import get_session
from services.ai_analyst.evidence import build_evidence_pack
from services.policy_engine.actions import ACTION_REGISTRY
from services.policy_engine.engine import evaluate_policy
from services.policy_engine.playbooks import PlaybookDefinition, get_playbook, list_playbooks
from services.policy_engine.service import (
    IncidentNotFoundError,
    PlanStateError,
    approve_response_plan,
    cancel_response_plan,
    create_response_plan,
    get_response_plan,
    list_response_plans,
    list_response_plans_for_incident,
    reject_response_plan,
)

router = APIRouter(prefix="/api/v1")


def _playbook_to_out(playbook: PlaybookDefinition) -> PlaybookOut:
    return PlaybookOut(
        id=playbook.id,
        version=playbook.version,
        name=playbook.name,
        description=playbook.description,
        enabled=playbook.enabled,
        allowed_asset_types=playbook.allowed_asset_types,
        allowed_incident_categories=playbook.allowed_incident_categories,
        minimum_incident_severity=list(playbook.minimum_incident_severity),
        minimum_detection_count=playbook.minimum_detection_count,
        requires_human_approval=playbook.requires_human_approval,
        reversible=playbook.reversible,
        actions=[
            PlaybookActionOut(
                action_id=a.action_id,
                target_source=a.target_source,
                description=ACTION_REGISTRY[a.action_id].description,
                risk_level=ACTION_REGISTRY[a.action_id].risk_level,
                reversible=ACTION_REGISTRY[a.action_id].reversible,
                requires_approval=ACTION_REGISTRY[a.action_id].requires_approval,
                expected_verification=ACTION_REGISTRY[a.action_id].expected_verification,
            )
            for a in playbook.actions
        ],
        verification=playbook.verification,
        rollback=playbook.rollback,
        risk=PlaybookRiskOut(
            mission_impact=playbook.risk.mission_impact, reversibility=playbook.risk.reversibility
        ),
    )


@router.get("/playbooks", response_model=list[PlaybookOut])
async def list_playbooks_route():
    return [_playbook_to_out(p) for p in list_playbooks()]


@router.get("/playbooks/{playbook_id}", response_model=PlaybookOut)
async def get_playbook_route(playbook_id: str):
    playbook = get_playbook(playbook_id)
    if playbook is None:
        raise HTTPException(status_code=404, detail="playbook not found")
    return _playbook_to_out(playbook)


@router.get("/incidents/{incident_id}/eligible-playbooks", response_model=list[PlaybookOut])
async def eligible_playbooks(incident_id: str, session: AsyncSession = Depends(get_session)):
    pack = await build_evidence_pack(session, incident_id)
    if pack is None:
        raise HTTPException(status_code=404, detail="incident not found")
    return [
        _playbook_to_out(p) for p in list_playbooks() if p.id in pack.available_playbook_ids
    ]


@router.post("/incidents/{incident_id}/response-plan", response_model=ResponsePlanOut)
async def create_response_plan_route(
    incident_id: str, body: ResponsePlanCreate, session: AsyncSession = Depends(get_session)
):
    try:
        plan, decision = await create_response_plan(
            session,
            incident_id=incident_id,
            playbook_id=body.playbook_id,
            actor=body.actor,
            recommendation_source=body.recommendation_source,
            ai_assessment_id=body.ai_assessment_id,
            note=body.note,
        )
    except IncidentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="incident not found") from exc

    if plan is None:
        raise HTTPException(
            status_code=422,
            detail=PolicyDecisionOut(
                decision=decision.decision,
                playbook_id=decision.playbook_id,
                allowed=decision.allowed,
                reasons=decision.reasons,
                blocking_reasons=decision.blocking_reasons,
                requires_human_approval=decision.requires_human_approval,
            ).model_dump(),
        )
    return ResponsePlanOut.model_validate(plan, from_attributes=True)


@router.get("/response-plans", response_model=list[ResponsePlanOut])
async def list_response_plans_route(
    status: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
):
    plans = await list_response_plans(session, status=status)
    return [ResponsePlanOut.model_validate(p, from_attributes=True) for p in plans]


@router.get("/incidents/{incident_id}/response-plans", response_model=list[ResponsePlanOut])
async def list_response_plans_for_incident_route(
    incident_id: str, session: AsyncSession = Depends(get_session)
):
    plans = await list_response_plans_for_incident(session, incident_id)
    return [ResponsePlanOut.model_validate(p, from_attributes=True) for p in plans]


@router.get("/response-plans/{plan_id}", response_model=ResponsePlanOut)
async def get_response_plan_route(plan_id: str, session: AsyncSession = Depends(get_session)):
    plan = await get_response_plan(session, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="response plan not found")
    return ResponsePlanOut.model_validate(plan, from_attributes=True)


@router.post("/response-plans/{plan_id}/approve", response_model=ResponsePlanOut)
async def approve_response_plan_route(
    plan_id: str, body: ResponsePlanApprove, session: AsyncSession = Depends(get_session)
):
    try:
        plan = await approve_response_plan(
            session, plan_id=plan_id, actor=body.actor, note=body.note
        )
    except PlanStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if plan is None:
        raise HTTPException(status_code=404, detail="response plan not found")
    return ResponsePlanOut.model_validate(plan, from_attributes=True)


@router.post("/response-plans/{plan_id}/reject", response_model=ResponsePlanOut)
async def reject_response_plan_route(
    plan_id: str, body: ResponsePlanReject, session: AsyncSession = Depends(get_session)
):
    try:
        plan = await reject_response_plan(
            session, plan_id=plan_id, actor=body.actor, reason=body.reason
        )
    except PlanStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if plan is None:
        raise HTTPException(status_code=404, detail="response plan not found")
    return ResponsePlanOut.model_validate(plan, from_attributes=True)


@router.post("/response-plans/{plan_id}/cancel", response_model=ResponsePlanOut)
async def cancel_response_plan_route(
    plan_id: str, body: ResponsePlanCancel, session: AsyncSession = Depends(get_session)
):
    try:
        plan = await cancel_response_plan(
            session, plan_id=plan_id, actor=body.actor, note=body.note
        )
    except PlanStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if plan is None:
        raise HTTPException(status_code=404, detail="response plan not found")
    return ResponsePlanOut.model_validate(plan, from_attributes=True)


@router.get("/incidents/{incident_id}/policy-check/{playbook_id}", response_model=PolicyDecisionOut)
async def policy_check(
    incident_id: str, playbook_id: str, session: AsyncSession = Depends(get_session)
):
    """Read-only preview of what a POST .../response-plan would decide, without creating anything -
    lets the UI show "ELIGIBLE - HUMAN APPROVAL REQUIRED" or the specific blocking reasons before
    the analyst commits to creating a plan."""
    pack = await build_evidence_pack(session, incident_id)
    if pack is None:
        raise HTTPException(status_code=404, detail="incident not found")
    playbook = get_playbook(playbook_id)
    decision = evaluate_policy(playbook, pack)
    return PolicyDecisionOut(
        decision=decision.decision,
        playbook_id=decision.playbook_id,
        allowed=decision.allowed,
        reasons=decision.reasons,
        blocking_reasons=decision.blocking_reasons,
        requires_human_approval=decision.requires_human_approval,
    )
