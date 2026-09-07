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
from apps.missionnet.models import Asset, AuditEvent, IdentityUser, ServiceToken, TelemetrySample
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
    await _write_audit(
        session,
        ctx,
        "token.revoke",
        "service_token",
        token_id,
        severity="high",
        detail={"reason": ctx.reason, "owner_user_id": token.owner_user_id},
    )
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


class TelemetryInjection(ScenarioContext):
    """Controlled synthetic telemetry sample for testing detection rules (e.g. low battery /
    poor link quality). Not exposed to the LLM; used by lab operators and the Demo Control Plane."""

    battery: int = Field(default=90, ge=0, le=100)
    link_quality: int = Field(default=95, ge=0, le=100)
    latitude: float | None = Field(default=None)
    longitude: float | None = Field(default=None)


@router.post("/telemetry/{asset_id}/inject")
async def inject_telemetry(
    asset_id: str,
    sample: TelemetryInjection = TelemetryInjection(),
    session: AsyncSession = Depends(get_session),
):
    asset = await session.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="asset not in synthetic inventory")

    sample_id = str(uuid.uuid4())
    session.add(
        TelemetrySample(
            sample_id=sample_id,
            asset_id=asset_id,
            battery=sample.battery,
            link_quality=sample.link_quality,
            latitude=sample.latitude,
            longitude=sample.longitude,
        )
    )
    await _write_audit(
        session,
        sample,
        "telemetry.inject",
        "asset",
        asset_id,
        severity="info",
        detail={
            "sample_id": sample_id,
            "battery": sample.battery,
            "link_quality": sample.link_quality,
        },
    )
    await session.commit()
    return {"sample_id": sample_id, "asset_id": asset_id}


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


# --------------------------------------------------------------------------------------------
# Phase 7: added specifically for Sentinel's deterministic response executor. Each endpoint is
# idempotent - calling it twice with the same target never duplicates state or creates a second
# row - since the executor must be able to safely retry/resume without double-applying an action.
# --------------------------------------------------------------------------------------------


@router.post("/users/{user_id}/suspend")
async def suspend_user(
    user_id: str,
    ctx: ScenarioContext = ScenarioContext(),
    session: AsyncSession = Depends(get_session),
):
    user = await session.get(IdentityUser, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="identity user not in synthetic inventory")
    already_suspended = user.status == "suspended"
    user.status = "suspended"
    if not already_suspended:
        await _write_audit(session, ctx, "user.suspend", "identity_user", user_id, severity="high")
    await session.commit()
    return {"user_id": user_id, "status": user.status}


@router.post("/users/{user_id}/reinstate")
async def reinstate_user(
    user_id: str,
    ctx: ScenarioContext = ScenarioContext(),
    session: AsyncSession = Depends(get_session),
):
    """Rollback for `suspend_user`."""
    user = await session.get(IdentityUser, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="identity user not in synthetic inventory")
    already_active = user.status == "active"
    user.status = "active"
    if not already_active:
        await _write_audit(
            session, ctx, "user.reinstate", "identity_user", user_id, severity="info"
        )
    await session.commit()
    return {"user_id": user_id, "status": user.status}


@router.post("/tokens/{token_id}/reactivate")
async def reactivate_token(
    token_id: str,
    ctx: ScenarioContext = ScenarioContext(),
    session: AsyncSession = Depends(get_session),
):
    """Rollback for `revoke_token`."""
    token = await session.get(ServiceToken, token_id)
    if token is None:
        raise HTTPException(status_code=404, detail="token not in synthetic inventory")
    already_valid = token.valid
    token.valid = True
    token.revoked_at = None
    if not already_valid:
        await _write_audit(
            session, ctx, "token.reactivate", "service_token", token_id, severity="info"
        )
    await session.commit()
    return {"token_id": token_id, "valid": token.valid}


@router.post("/tokens/{token_id}/rotate")
async def rotate_token(
    token_id: str,
    ctx: ScenarioContext = ScenarioContext(),
    session: AsyncSession = Depends(get_session),
):
    """Revokes `token_id` and issues a deterministically-named replacement
    (`{token_id}-rotated`) for the same owner. The deterministic new ID is what makes this
    idempotent: calling it twice returns the same replacement token both times rather than
    minting a second one."""
    token = await session.get(ServiceToken, token_id)
    if token is None:
        raise HTTPException(status_code=404, detail="token not in synthetic inventory")

    new_token_id = f"{token_id}-rotated"
    existing = await session.get(ServiceToken, new_token_id)
    if existing is not None:
        return {"old_token_id": token_id, "new_token_id": new_token_id, "valid": existing.valid}

    token.valid = False
    token.revoked_at = datetime.now(UTC)
    new_token = ServiceToken(
        token_id=new_token_id,
        owner_user_id=token.owner_user_id,
        token_type=token.token_type,
        valid=True,
    )
    session.add(new_token)
    await _write_audit(
        session,
        ctx,
        "token.rotate",
        "service_token",
        token_id,
        severity="info",
        detail={"old_token_id": token_id, "new_token_id": new_token_id},
    )
    await session.commit()
    return {"old_token_id": token_id, "new_token_id": new_token_id, "valid": True}


@router.post("/assets/{asset_id}/request-replacement")
async def request_replacement(
    asset_id: str,
    ctx: ScenarioContext = ScenarioContext(),
    session: AsyncSession = Depends(get_session),
):
    """Synthetic-only: creates a new, healthy Asset row standing in for a replacement instance -
    no real infrastructure is provisioned. The deterministic `{asset_id}-replacement` ID makes
    this idempotent the same way `rotate_token` is."""
    original = await session.get(Asset, asset_id)
    if original is None:
        raise HTTPException(status_code=404, detail="asset not in synthetic inventory")

    replacement_id = f"{asset_id}-replacement"
    existing = await session.get(Asset, replacement_id)
    if existing is not None:
        return {"replacement_asset_id": replacement_id, "status": existing.status}

    replacement = Asset(
        asset_id=replacement_id,
        name=f"{original.name} (Replacement)",
        asset_type=original.asset_type,
        mission_role=original.mission_role,
        criticality=original.criticality,
        dependencies=list(original.dependencies),
        max_allowed_outage_seconds=original.max_allowed_outage_seconds,
        containment_cost=original.containment_cost,
        rollback_supported=False,
        status="nominal",
        network_state="normal",
    )
    session.add(replacement)
    await _write_audit(
        session,
        ctx,
        "asset.replacement_provisioned",
        "asset",
        asset_id,
        severity="info",
        detail={"replacement_asset_id": replacement_id},
    )
    await session.commit()
    return {"replacement_asset_id": replacement_id, "status": replacement.status}
