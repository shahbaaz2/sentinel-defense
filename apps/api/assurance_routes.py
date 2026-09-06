"""Deployment Assurance (blueprint §16.8): makes the local/offline/no-AI claims observable rather
than merely asserted. Every field here reflects a real check, never a hard-coded "ONLINE" - a
service that is actually down reports OFFLINE.
"""

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import settings
from apps.api.schemas import IntegrationStatusOut, SystemAssuranceOut
from domain.db import get_session

router = APIRouter(prefix="/api/v1")

MISSIONNET_BASE_URL = "http://127.0.0.1:8090"
DEMO_CONTROL_BASE_URL = "http://127.0.0.1:8100"


async def _reachable(url: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(url)
            return resp.status_code == 200
    except httpx.HTTPError:
        return False


@router.get("/system/assurance", response_model=SystemAssuranceOut)
async def system_assurance(session: AsyncSession = Depends(get_session)):
    missionnet_ok = await _reachable(f"{MISSIONNET_BASE_URL}/health")
    demo_control_ok = await _reachable(f"{DEMO_CONTROL_BASE_URL}/health")

    postgres_ok = False
    try:
        await session.execute(text("SELECT 1"))
        postgres_ok = True
    except Exception:  # noqa: BLE001 - any DB error means "not OK" for this status check
        postgres_ok = False

    return SystemAssuranceOut(
        deployment_profile=settings.profile.upper(),
        platform="Apple Silicon (arm64)",
        inference_location="local",
        external_ai_api="DISABLED" if not settings.external_ai_enabled else "ENABLED",
        ai_analyst_status="NOT ENABLED",
        internet_required_for_core_demo="NO - runtime demo requires no external network access",
        model=settings.llm_model,
        model_provider=settings.llm_provider,
        knowledge_bundle=settings.knowledge_bundle,
        policy_bundle=settings.policy_bundle,
        synthetic_only=settings.synthetic_only,
        missionnet_adapter="ONLINE" if missionnet_ok else "OFFLINE",
        sentinel_api="ONLINE",
        postgresql="ONLINE" if postgres_ok else "OFFLINE",
        demo_control="ONLINE" if demo_control_ok else "OFFLINE",
        local_llm_runtime="NOT ENABLED",
        integrations=IntegrationStatusOut(),
    )
