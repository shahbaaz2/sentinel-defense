"""MissionNet's internal lab-control API (blueprint §7.5).

Reserved for two callers only: Sentinel's deterministic response executor (Phase 7, calling one
specific endpoint per approved playbook step) and the Demo Control / Scenario Engine (Phase 3,
calling only predefined scenario operations). It is never exposed to the LLM as a tool, and
it is not the regular MissionNet application API - it is bound to the lab network and requires
the shared lab secret on every call.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.missionnet.config import settings
from apps.missionnet.db import get_session
from apps.missionnet.models import Asset, AuditEvent, ServiceToken
from apps.missionnet.seed import reset_and_seed
from apps.missionnet.state import compute_system_state


def require_lab_secret(x_lab_secret: str = Header(default="")) -> None:
    if x_lab_secret != settings.lab_secret:
        raise HTTPException(status_code=403, detail="invalid or missing lab secret")


# Applied once at the router level (not per-route) so a new /lab endpoint can't ship unguarded.
router = APIRouter(prefix="/lab", tags=["lab-control"], dependencies=[Depends(require_lab_secret)])


class ScenarioContext(BaseModel):
    """Every lab-control mutation is attributable: who/what caused it, and which scenario run (if
    any). This is what lets MissionNet's own audit stream distinguish a scenario-injected anomaly
    from Sentinel's own deterministic response later in Phase 7."""

    actor_type: str = Field(default="lab_control", max_length=64)
    actor_id: str = Field(default="lab_control", max_length=128)
    scenario_id: str | None = Field(default=None, max_length=128)
    reason: str = Field(default="", max_length=500)


async def _write_audit(
    session: AsyncSession,
    ctx: ScenarioContext,
    action: str,
    object_type: str,
    object_id: str,
    severity: str = "info",
    detail: dict | None = None,
) -> None:
    session.add(
        AuditEvent(
            audit_id=str(uuid.uuid4()),
            actor_type=ctx.actor_type,
            actor_id=ctx.actor_id,
            action=action,
            object_type=object_type,
            object_id=object_id,
            detail=detail or {"reason": ctx.reason},
            severity=severity,
            scenario_id=ctx.scenario_id,
        )
    )


@router.post("/reset")
async def lab_reset():
    await reset_and_seed()
    return {"status": "reset", "classification": "SYNTHETIC"}


@router.get("/state")
async def lab_state(session: AsyncSession = Depends(get_session)):
    return await compute_system_state(session)


@router.post("/state/{asset_id}/degrade")
async def degrade_asset(
    asset_id: str,
    ctx: ScenarioContext = ScenarioContext(),
    session: AsyncSession = Depends(get_session),
):
    asset = await session.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="asset not in synthetic inventory")
    asset.status = "degraded"
    await _write_audit(session, ctx, "asset.degrade", "asset", asset_id, severity="medium")
    await session.commit()
    return {"asset_id": asset_id, "status": asset.status}


@router.post("/tokens/{token_id}/revoke")
async def revoke_token(
    token_id: str,
    ctx: ScenarioContext = ScenarioContext(),
    session: AsyncSession = Depends(get_session),
):
    token = await session.get(ServiceToken, token_id)
    if token is None:
        raise HTTPException(status_code=404, detail="token not in synthetic inventory")
    token.valid = False
    token.revoked_at = datetime.now(UTC)
    await _write_audit(session, ctx, "token.revoke", "service_token", token_id, severity="high")
    await session.commit()
    return {"token_id": token_id, "valid": token.valid}


@router.post("/assets/{asset_id}/quarantine")
async def quarantine_asset(
    asset_id: str,
    ctx: ScenarioContext = ScenarioContext(),
    session: AsyncSession = Depends(get_session),
):
    asset = await session.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="asset not in synthetic inventory")
    asset.status = "quarantined"
    asset.network_state = "quarantined"
    await _write_audit(session, ctx, "asset.quarantine", "asset", asset_id, severity="high")
    await session.commit()
    return {"asset_id": asset_id, "status": asset.status, "network_state": asset.network_state}


@router.post("/assets/{asset_id}/restore")
async def restore_asset(
    asset_id: str,
    ctx: ScenarioContext = ScenarioContext(),
    session: AsyncSession = Depends(get_session),
):
    asset = await session.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="asset not in synthetic inventory")
    asset.status = "nominal"
    asset.network_state = "normal"
    await _write_audit(session, ctx, "asset.restore", "asset", asset_id, severity="info")
    await session.commit()
    return {"asset_id": asset_id, "status": asset.status, "network_state": asset.network_state}


@router.post("/evidence/snapshot")
async def snapshot_evidence(
    ctx: ScenarioContext = ScenarioContext(),
    session: AsyncSession = Depends(get_session),
):
    snapshot_id = str(uuid.uuid4())
    await _write_audit(
        session,
        ctx,
        "evidence.snapshot",
        "missionnet",
        snapshot_id,
        severity="info",
        detail={"snapshot_id": snapshot_id, "reason": ctx.reason},
    )
    await session.commit()
    return {"snapshot_id": snapshot_id}
