"""Data Sources / Integrations (Phase 8): the real status of every adapter Sentinel can ingest
from - MissionNet plus every sensor adapter - computed from a live health check and persisted
ingestion history, never hardcoded. See docs/integrations.md.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import settings
from apps.api.schemas import IntegrationDetailOut
from domain.db import get_session
from domain.models.orm import IngestionAdapterStatus, NormalizedEventRecord
from services.event_ingestor.registry import build_adapter_registry

router = APIRouter(prefix="/api/v1", tags=["integrations"])


@router.get("/integrations", response_model=list[IntegrationDetailOut])
async def list_integrations(session: AsyncSession = Depends(get_session)):
    registry = build_adapter_registry(settings)
    results = []
    for descriptor in registry:
        status = await descriptor.status()

        event_count = (
            await session.execute(
                select(func.count(NormalizedEventRecord.event_id)).where(
                    NormalizedEventRecord.source == descriptor.adapter_id
                )
            )
        ).scalar_one()

        status_rows = (
            (
                await session.execute(
                    select(IngestionAdapterStatus)
                    .where(IngestionAdapterStatus.source == descriptor.adapter_id)
                    .order_by(IngestionAdapterStatus.last_attempt_at.desc())
                )
            )
            .scalars()
            .all()
        )
        last_successful_ingest_at = max(
            (r.last_success_at for r in status_rows if r.last_success_at is not None),
            default=None,
        )
        last_error = next((r.last_error for r in status_rows if r.last_error is not None), None)

        results.append(
            IntegrationDetailOut(
                adapter_id=descriptor.adapter_id,
                name=descriptor.name,
                version=descriptor.version,
                status=status,
                capabilities=descriptor.capabilities,
                configuration_requirements=descriptor.configuration_requirements,
                supported_event_categories=descriptor.supported_event_categories,
                last_successful_ingest_at=last_successful_ingest_at,
                event_count=event_count,
                last_error=last_error,
            )
        )
    return results
