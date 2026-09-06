"""One shared helper for writing to Sentinel's own audit_log (blueprint §10). Every ingestion
cycle, detection, incident, and analyst workflow change goes through this - never a direct
`session.add(AuditLogEntry(...))` elsewhere, so the shape stays consistent and nothing accidentally
logs a raw payload or secret.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from domain.models.orm import AuditLogEntry


async def write_audit(
    session: AsyncSession,
    *,
    entity_type: str,
    entity_id: str,
    action: str,
    actor: str = "system",
    source: str = "sentinel",
    scenario_id: str | None = None,
    detail: dict | None = None,
) -> None:
    session.add(
        AuditLogEntry(
            audit_id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC),
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor=actor,
            source=source,
            scenario_id=scenario_id,
            detail=detail or {},
        )
    )
