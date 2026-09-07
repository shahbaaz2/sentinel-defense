"""Execution API (blueprint Phase 7 §11). Narrow by design, mirroring `apps/api/response_routes.py`:
the browser executes a RESPONSE PLAN, never an arbitrary action - `POST .../execute` and
`POST .../rollback` take only `{"actor": "..."}`, nothing else. Everything the executor needs
(playbook, target, evidence) is resolved server-side from trusted stored state, never accepted from
the request body.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import settings
from apps.api.schemas import (
    ActionResultOut,
    ExecutionOut,
    ResponsePlanExecute,
    ResponsePlanOut,
    ResponsePlanRollback,
)
from domain.db import get_session
from domain.models.orm import ActionResult, ResponsePlan
from services.policy_engine.service import PlanStateError
from services.response_executor.executor import execute_response_plan, rollback_response_plan
from services.response_executor.models import (
    ExecutionBlockedError,
    ExecutionInProgressError,
    PlanNotFoundError,
)

router = APIRouter(prefix="/api/v1")


def _require_execution_enabled() -> None:
    if not settings.response_execution_enabled:
        raise HTTPException(
            status_code=503, detail="response execution is disabled on this deployment"
        )


async def _load_actions(session: AsyncSession, plan_id: str) -> list[ActionResult]:
    stmt = (
        select(ActionResult)
        .where(ActionResult.response_plan_id == plan_id)
        .order_by(ActionResult.action_index)
    )
    return list((await session.execute(stmt)).scalars().all())


@router.post("/response-plans/{plan_id}/execute", response_model=ResponsePlanOut)
async def execute_response_plan_route(
    plan_id: str, body: ResponsePlanExecute, session: AsyncSession = Depends(get_session)
):
    _require_execution_enabled()
    try:
        plan = await execute_response_plan(
            session,
            plan_id=plan_id,
            actor=body.actor,
            missionnet_base_url=settings.missionnet_base_url,
            missionnet_lab_secret=settings.missionnet_lab_secret,
        )
    except PlanNotFoundError as exc:
        raise HTTPException(status_code=404, detail="response plan not found") from exc
    except ExecutionInProgressError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ExecutionBlockedError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ResponsePlanOut.model_validate(plan, from_attributes=True)


@router.post("/response-plans/{plan_id}/rollback", response_model=ResponsePlanOut)
async def rollback_response_plan_route(
    plan_id: str, body: ResponsePlanRollback, session: AsyncSession = Depends(get_session)
):
    _require_execution_enabled()
    try:
        plan = await rollback_response_plan(
            session,
            plan_id=plan_id,
            actor=body.actor,
            missionnet_base_url=settings.missionnet_base_url,
            missionnet_lab_secret=settings.missionnet_lab_secret,
        )
    except PlanNotFoundError as exc:
        raise HTTPException(status_code=404, detail="response plan not found") from exc
    except PlanStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ResponsePlanOut.model_validate(plan, from_attributes=True)


@router.get("/response-plans/{plan_id}/execution", response_model=ExecutionOut)
async def get_execution_route(plan_id: str, session: AsyncSession = Depends(get_session)):
    plan = await session.get(ResponsePlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="response plan not found")
    actions = await _load_actions(session, plan_id)
    return ExecutionOut(
        response_plan_id=plan.response_plan_id,
        execution_status=plan.execution_status,
        executed_by=plan.executed_by,
        execution_started_at=plan.execution_started_at,
        execution_completed_at=plan.execution_completed_at,
        executor_version=plan.executor_version,
        execution_block_reason=plan.execution_block_reason,
        actions=[ActionResultOut.model_validate(a, from_attributes=True) for a in actions],
    )


@router.get("/response-plans/{plan_id}/actions", response_model=list[ActionResultOut])
async def list_actions_route(plan_id: str, session: AsyncSession = Depends(get_session)):
    plan = await session.get(ResponsePlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="response plan not found")
    actions = await _load_actions(session, plan_id)
    return [ActionResultOut.model_validate(a, from_attributes=True) for a in actions]
