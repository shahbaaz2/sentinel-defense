"""MissionNet: the synthetic mission-information application Sentinel protects (blueprint §7).

Independently runnable - has its own database, seeded fictional data, Operations Console, and an
internal lab-control API reserved for Sentinel's response executor and the Demo Control Plane.
"""

from fastapi import Depends, FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from apps.missionnet.db import get_session
from apps.missionnet.lab import router as lab_router
from apps.missionnet.routes import router as api_router
from apps.missionnet.state import compute_system_state

app = FastAPI(title="MissionNet", version="0.2.0")
app.include_router(api_router)
app.include_router(lab_router)


@app.get("/health")
async def health():
    """Fast liveness probe used by the cloud runtime.

    Keep this endpoint independent of PostgreSQL so a sleeping free-tier instance can be marked
    alive as soon as the application process is accepting HTTP traffic. Database-backed readiness
    is still verified through /state before Demo Control allows a scenario to execute.
    """
    return {
        "status": "HEALTHY",
        "classification": "SYNTHETIC",
        "service": "missionnet",
    }


@app.get("/ready")
async def ready(session: AsyncSession = Depends(get_session)):
    """Database-aware readiness probe for operators and orchestration."""
    state = await compute_system_state(session)
    return {
        "status": state.status,
        "classification": "SYNTHETIC",
        "service": "missionnet",
        "degraded_assets": state.degraded_assets,
        "quarantined_assets": state.quarantined_assets,
    }
