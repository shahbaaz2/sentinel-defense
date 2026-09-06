"""Computes MissionNet's overall system state from asset rows (blueprint §7.4).

`NOMINAL -> DEGRADED -> CONTAINMENT_IN_PROGRESS -> RECOVERING -> NOMINAL`. This is always derived
from live asset state, never hard-coded, so a scenario or the lab-control API can move it just by
changing asset rows.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.missionnet.models import Asset
from apps.missionnet.schemas import SystemStateOut


async def compute_system_state(session: AsyncSession) -> SystemStateOut:
    result = await session.execute(select(Asset))
    assets = result.scalars().all()

    degraded = [a.asset_id for a in assets if a.status == "degraded"]
    quarantined = [a.asset_id for a in assets if a.status == "quarantined"]
    contained = [a.asset_id for a in assets if a.status == "contained"]
    recovering = [a.asset_id for a in assets if a.status == "recovering"]

    if quarantined or contained:
        status = "containment_in_progress"
    elif recovering:
        status = "recovering"
    elif degraded:
        status = "degraded"
    else:
        status = "nominal"

    return SystemStateOut(
        status=status,
        degraded_assets=degraded,
        quarantined_assets=quarantined + contained,
    )
