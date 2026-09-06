import uuid

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.demo_control.config import settings
from apps.demo_control.db import get_session
from apps.demo_control.models import ScenarioRun
from apps.demo_control.runner import reset_after_run, run_scenario
from apps.demo_control.scenarios import list_scenarios, load_scenario
from apps.demo_control.schemas import (
    RunScenarioRequest,
    ScenarioRunOut,
    ScenarioSummary,
    SystemStatusOut,
)

router = APIRouter(prefix="/api/v1")


@router.get("/status", response_model=SystemStatusOut)
async def system_status():
    missionnet_status = "UNREACHABLE"
    sentinel_status = "OFFLINE"
    async with httpx.AsyncClient(timeout=3.0) as client:
        try:
            resp = await client.get(f"{settings.missionnet_base_url}/health")
            missionnet_status = resp.json().get("status", "unknown").upper()
        except httpx.HTTPError:
            pass
        try:
            resp = await client.get(f"{settings.sentinel_base_url}/api/v1/health")
            sentinel_status = "ONLINE" if resp.status_code == 200 else "OFFLINE"
        except httpx.HTTPError:
            pass
    return SystemStatusOut(missionnet_status=missionnet_status, sentinel_status=sentinel_status)


@router.get("/scenarios", response_model=list[ScenarioSummary])
async def get_scenarios():
    return [
        ScenarioSummary(
            id=s.id,
            version=s.version,
            name=s.name,
            description=s.description,
            risk_level=s.risk_level,
            step_count=len(s.steps),
        )
        for s in list_scenarios()
    ]


@router.get("/scenarios/{scenario_id}")
async def get_scenario(scenario_id: str):
    try:
        return load_scenario(scenario_id)
    except FileNotFoundError as err:
        raise HTTPException(status_code=404, detail="scenario not found") from err


@router.post("/scenarios/{scenario_id}/run", response_model=ScenarioRunOut)
async def start_scenario_run(
    scenario_id: str,
    body: RunScenarioRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    try:
        scenario = load_scenario(scenario_id)
    except FileNotFoundError as err:
        raise HTTPException(status_code=404, detail="scenario not found") from err

    run_id = f"RUN-{uuid.uuid4()}"
    run = ScenarioRun(
        run_id=run_id,
        scenario_id=scenario.id,
        scenario_version=scenario.version,
        actor=body.actor,
        status="PENDING",
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)

    background_tasks.add_task(run_scenario, run_id)
    return run


@router.get("/runs", response_model=list[ScenarioRunOut])
async def list_runs(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(ScenarioRun).order_by(ScenarioRun.started_at.desc()))
    return result.scalars().all()


@router.get("/runs/{run_id}", response_model=ScenarioRunOut)
async def get_run(run_id: str, session: AsyncSession = Depends(get_session)):
    run = await session.get(ScenarioRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return run


@router.get("/runs/{run_id}/timeline")
async def get_run_timeline(run_id: str, session: AsyncSession = Depends(get_session)):
    run = await session.get(ScenarioRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return run.timeline


@router.get("/runs/{run_id}/verification")
async def get_run_verification(run_id: str, session: AsyncSession = Depends(get_session)):
    run = await session.get(ScenarioRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return run.verification


@router.post("/runs/{run_id}/cancel", response_model=ScenarioRunOut)
async def cancel_run(run_id: str, session: AsyncSession = Depends(get_session)):
    run = await session.get(ScenarioRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    if run.status in ("PASSED", "FAILED", "CANCELLED"):
        raise HTTPException(status_code=409, detail=f"run already terminal: {run.status}")
    run.cancel_requested = True
    await session.commit()
    await session.refresh(run)
    return run


@router.post("/runs/{run_id}/reset", response_model=ScenarioRunOut)
async def reset_run(run_id: str, session: AsyncSession = Depends(get_session)):
    run = await session.get(ScenarioRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    try:
        await reset_after_run(run_id)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"reset failed: {exc}") from exc
    await session.refresh(run)
    return run
