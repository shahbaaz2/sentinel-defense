"""Deployment Assurance (blueprint §16.8): makes the local/offline/no-AI claims observable rather
than merely asserted. Every field here reflects a real check, never a hard-coded "ONLINE" - a
service that is actually down reports OFFLINE.
"""

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ai.providers.base import LLMProvider, ProviderStatus
from apps.api.ai_routes import get_llm_provider
from apps.api.config import settings
from apps.api.schemas import IntegrationStatusOut, SystemAssuranceOut
from domain.db import get_session
from services.event_ingestor.registry import build_adapter_registry
from services.policy_engine.engine import POLICY_BUNDLE_VERSION

router = APIRouter(prefix="/api/v1")


async def _reachable(url: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(url)
            return resp.status_code == 200
    except httpx.HTTPError:
        return False


@router.get("/system/assurance", response_model=SystemAssuranceOut)
async def system_assurance(
    session: AsyncSession = Depends(get_session),
    provider: LLMProvider = Depends(get_llm_provider),
):
    missionnet_ok = await _reachable(f"{settings.missionnet_base_url}/health")
    demo_control_ok = await _reachable(f"{settings.demo_control_base_url}/health")

    postgres_ok = False
    try:
        await session.execute(text("SELECT 1"))
        postgres_ok = True
    except Exception:  # noqa: BLE001 - any DB error means "not OK" for this status check
        postgres_ok = False

    # Phase 5: distinguish "AI Analyst disabled by config" from "enabled but the provider is
    # actually degraded" - deterministic detection/correlation stay OPERATIONAL either way (see
    # DECISIONS.md: AI failure must never affect Sentinel's core functions).
    if not settings.ai_enabled:
        ai_status = "NOT ENABLED"
        local_llm_runtime = "NOT ENABLED"
    else:
        provider_status = await provider.get_status()
        ai_status = {
            ProviderStatus.READY: "OPERATIONAL",
            ProviderStatus.LOADING: "LOADING",
            ProviderStatus.DEGRADED: "DEGRADED",
            ProviderStatus.DISABLED: "NOT ENABLED",
        }[provider_status]
        local_llm_runtime = provider.get_provenance().runtime

    registry = build_adapter_registry(settings)
    integration_statuses = {d.adapter_id: await d.status() for d in registry}

    # A cloud deployment with SENTINEL_LLM_PROVIDER=deepseek genuinely does call an external API -
    # this must say so honestly rather than keep asserting the local/offline claim regardless of
    # configuration (see docs/deployment.md and DECISIONS.md).
    uses_cloud_ai = settings.ai_enabled and settings.llm_provider == "deepseek"
    inference_location = "cloud (DeepSeek API)" if uses_cloud_ai else "local"
    internet_required_for_core_demo = (
        "YES - the AI Analyst calls the DeepSeek API"
        if uses_cloud_ai
        else "NO - runtime demo requires no external network access"
    )

    return SystemAssuranceOut(
        deployment_profile=settings.profile.upper(),
        platform=settings.platform_label,
        inference_location=inference_location,
        external_ai_api="DISABLED" if not settings.external_ai_enabled else "ENABLED",
        ai_analyst_status=ai_status,
        internet_required_for_core_demo=internet_required_for_core_demo,
        model=settings.llm_model,
        model_provider=settings.llm_provider,
        knowledge_bundle=settings.knowledge_bundle,
        policy_bundle=POLICY_BUNDLE_VERSION,
        synthetic_only=settings.synthetic_only,
        missionnet_adapter="ONLINE" if missionnet_ok else "OFFLINE",
        sentinel_api="ONLINE",
        postgresql="ONLINE" if postgres_ok else "OFFLINE",
        demo_control="ONLINE" if demo_control_ok else "OFFLINE",
        local_llm_runtime=local_llm_runtime,
        response_execution=(
            "ENABLED - BOUNDED" if settings.response_execution_enabled else "DISABLED"
        ),
        integrations=IntegrationStatusOut(**integration_statuses),
    )
