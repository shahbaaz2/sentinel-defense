import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from apps.missionnet.db import get_session
from apps.missionnet.models import (
    Asset,
    AuditEvent,
    IdentityUser,
    MissionRecord,
    ServiceToken,
    TelemetrySample,
)
from apps.missionnet.schemas import (
    AssetOut,
    AuditEventOut,
    LoginRequest,
    LoginResponse,
    MissionRecordOut,
    TelemetryOut,
    TokenOut,
    UserOut,
)
from apps.missionnet.state import compute_system_state

router = APIRouter()


@router.get("/assets", response_model=list[AssetOut])
async def list_assets(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Asset).order_by(Asset.asset_id))
    return result.scalars().all()


@router.get("/assets/{asset_id}", response_model=AssetOut)
async def get_asset(asset_id: str, session: AsyncSession = Depends(get_session)):
    asset = await session.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="asset not found")
    return asset


@router.get("/identity/users", response_model=list[UserOut])
async def list_users(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(IdentityUser).order_by(IdentityUser.user_id))
    return result.scalars().all()


@router.get("/identity/tokens", response_model=list[TokenOut])
async def list_tokens(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(ServiceToken).order_by(ServiceToken.token_id))
    return result.scalars().all()


@router.post("/identity/login", response_model=LoginResponse)
async def login(body: LoginRequest, session: AsyncSession = Depends(get_session)):
    """Genuine (if minimal) authentication against seeded synthetic identities.

    Exists so MissionNet can produce real auth.success/auth.failure audit events - Sentinel's
    detection rules must observe genuine signals, never events fabricated on Sentinel's side.
    """
    result = await session.execute(
        select(IdentityUser).where(IdentityUser.username == body.username)
    )
    user = result.scalar_one_or_none()

    success = (
        user is not None
        and user.status == "active"
        and user.synthetic_password == body.password
    )
    actor_type = "human" if (user is None or user.user_type == "human") else "service_account"
    session.add(
        AuditEvent(
            audit_id=str(uuid.uuid4()),
            actor_type=actor_type,
            actor_id=user.user_id if user else body.username,
            action="auth.success" if success else "auth.failure",
            object_type="identity_user",
            object_id=user.user_id if user else body.username,
            detail={},
            severity="info" if success else "low",
            scenario_id=body.scenario_id,
        )
    )
    await session.commit()

    if not success or user is None:
        return LoginResponse(success=False, reason="invalid credentials")
    return LoginResponse(success=True, user_id=user.user_id)


@router.get("/mission-data/records", response_model=list[MissionRecordOut])
async def list_records(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(MissionRecord).order_by(MissionRecord.record_id))
    return result.scalars().all()


@router.get("/mission-data/records/{record_id}", response_model=MissionRecordOut)
async def get_record(
    record_id: str,
    actor_user_id: str = Query(..., description="Identity performing the access, for audit."),
    scenario_id: str | None = Query(default=None),
    run_id: str | None = Query(
        default=None, description="Demo Control run ID - enables idempotent retry (with step_id)."
    ),
    step_id: str | None = Query(
        default=None, description="Demo Control step ID - enables idempotent retry (with run_id)."
    ),
    session: AsyncSession = Depends(get_session),
):
    record = await session.get(MissionRecord, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="mission record not found")

    if run_id and step_id:
        # Deterministic ID from (run_id, step_id, record_id): a caller retrying the exact same
        # scenario step (e.g. after a transient 502) reuses the same audit_id, so the
        # on_conflict_do_nothing below makes a retried record.access a genuine no-op instead of a
        # second AuditEvent - see docs/demo-runbook.md and DECISIONS.md. Callers that don't pass
        # run_id/step_id (anything outside the scenario runner) keep today's behavior: a fresh
        # random ID every call, since there's no step identity to key idempotency on.
        idempotency_name = f"record.access:{run_id}:{step_id}:{record_id}"
        audit_id = str(uuid.uuid5(uuid.NAMESPACE_URL, idempotency_name))
    else:
        audit_id = str(uuid.uuid4())

    stmt = pg_insert(AuditEvent).values(
        audit_id=audit_id,
        actor_type="human",
        actor_id=actor_user_id,
        action="record.access",
        object_type="mission_record",
        object_id=record_id,
        detail={},
        severity="info",
        scenario_id=scenario_id,
    )
    stmt = stmt.on_conflict_do_nothing(index_elements=["audit_id"])
    await session.execute(stmt)
    await session.commit()
    return record


@router.get("/telemetry", response_model=list[TelemetryOut])
async def list_telemetry(
    since: datetime | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(TelemetrySample)
    if since is not None:
        stmt = stmt.where(TelemetrySample.generated_at > since)
        stmt = stmt.order_by(TelemetrySample.generated_at)
    else:
        stmt = stmt.order_by(TelemetrySample.generated_at.desc())
    result = await session.execute(stmt.limit(limit))
    return result.scalars().all()


@router.get("/audit", response_model=list[AuditEventOut])
async def list_audit_events(
    since: datetime | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(AuditEvent)
    if since is not None:
        stmt = stmt.where(AuditEvent.timestamp > since).order_by(AuditEvent.timestamp)
    else:
        stmt = stmt.order_by(AuditEvent.timestamp.desc())
    result = await session.execute(stmt.limit(limit))
    return result.scalars().all()


@router.get("/state")
async def get_state(session: AsyncSession = Depends(get_session)):
    return await compute_system_state(session)
