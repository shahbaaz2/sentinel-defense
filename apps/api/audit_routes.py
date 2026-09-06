"""Read-only access to Sentinel's own audit_log (domain/audit.py writes it; this only ever reads).
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.schemas import AuditLogEntryOut
from domain.db import get_session
from domain.models.orm import AuditLogEntry

router = APIRouter(prefix="/api/v1")


@router.get("/audit", response_model=list[AuditLogEntryOut])
async def list_audit_log(
    entity_type: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    action: str | None = Query(default=None),
    scenario_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(AuditLogEntry)
    if entity_type:
        stmt = stmt.where(AuditLogEntry.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditLogEntry.entity_id == entity_id)
    if action:
        stmt = stmt.where(AuditLogEntry.action == action)
    if scenario_id:
        stmt = stmt.where(AuditLogEntry.scenario_id == scenario_id)
    stmt = stmt.order_by(AuditLogEntry.timestamp.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    return result.scalars().all()
