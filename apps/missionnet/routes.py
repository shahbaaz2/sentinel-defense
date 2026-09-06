from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
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


@router.get("/mission-data/records", response_model=list[MissionRecordOut])
async def list_records(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(MissionRecord).order_by(MissionRecord.record_id))
    return result.scalars().all()


@router.get("/telemetry", response_model=list[TelemetryOut])
async def list_telemetry(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(TelemetrySample).order_by(TelemetrySample.generated_at.desc()).limit(100)
    )
    return result.scalars().all()


@router.get("/audit", response_model=list[AuditEventOut])
async def list_audit_events(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(AuditEvent).order_by(AuditEvent.timestamp.desc()).limit(100)
    )
    return result.scalars().all()


@router.get("/state")
async def get_state(session: AsyncSession = Depends(get_session)):
    return await compute_system_state(session)
