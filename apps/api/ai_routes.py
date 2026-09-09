"""AI Analyst API.

The AI surface is intentionally narrow: requests analyze one existing Sentinel incident using the
controlled evidence pack. AI cannot create detections/incidents or execute response actions.
Provider diagnostics are exposed separately so operators can distinguish external API billing,
authentication, rate limiting, and availability failures from Sentinel's deterministic pipeline.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai.providers import get_provider
from ai.providers.base import LLMProvider, ProviderStatus
from apps.api.config import settings
from apps.api.schemas import AIAssessmentOut, AIStatusOut
from domain.db import get_session
from domain.models.orm import AIAssessment
from services.ai_analyst.service import get_latest_assessment, list_assessments, run_analysis

router = APIRouter(prefix="/api/v1")


def get_llm_provider() -> LLMProvider:
    return get_provider(
        settings.llm_provider,
        settings.llm_model,
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
    )


@router.get("/ai/status", response_model=AIStatusOut)
async def ai_status(
    provider: LLMProvider = Depends(get_llm_provider),
    session: AsyncSession = Depends(get_session),
):
    if not settings.ai_enabled:
        status = ProviderStatus.DISABLED
    else:
        status = await provider.get_status()
    provenance = provider.get_provenance()

    last_latency: int | None = None
    last_row = (
        await session.execute(
            select(AIAssessment.latency_ms).order_by(AIAssessment.created_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    if last_row is not None:
        last_latency = last_row

    return AIStatusOut(
        ai_enabled=settings.ai_enabled,
        runtime=provenance.runtime,
        provider=provenance.model_provider,
        model=provenance.model_name,
        status=status.value,
        external_ai_api="DISABLED" if not settings.external_ai_enabled else "ENABLED",
        last_latency_ms=last_latency,
    )


@router.get("/ai/provider-diagnostics")
async def ai_provider_diagnostics(provider: LLMProvider = Depends(get_llm_provider)) -> dict:
    """Operational provider state safe for an analyst-facing status panel.

    No secret, raw upstream response, token, account identifier, or balance amount is returned.
    The purpose is classification: an operator should know whether advisory AI is unavailable due
    to provider billing/auth/rate-limit/network health rather than misdiagnosing Sentinel itself.
    """
    if not settings.ai_enabled:
        return {
            "status": "DISABLED",
            "code": "AI_DISABLED",
            "message": "AI Analyst is disabled on this deployment.",
            "provider": settings.llm_provider,
            "model": settings.llm_model,
            "sentinel_core_affected": False,
        }

    status = await provider.get_status()
    code = getattr(provider, "last_error_code", None)
    message = getattr(provider, "last_error_message", None)
    if status == ProviderStatus.READY:
        code = None
        message = "AI provider is available for advisory analysis."

    return {
        "status": status.value,
        "code": code,
        "message": message,
        "provider": provider.get_provenance().model_provider,
        "model": provider.get_provenance().model_name,
        "sentinel_core_affected": False,
    }


@router.post("/incidents/{incident_id}/ai/analyze", response_model=AIAssessmentOut)
async def analyze_incident(
    incident_id: str,
    provider: LLMProvider = Depends(get_llm_provider),
    session: AsyncSession = Depends(get_session),
):
    if not settings.ai_enabled:
        raise HTTPException(status_code=503, detail="AI Analyst is not enabled on this deployment")

    row = await run_analysis(
        session,
        incident_id=incident_id,
        provider=provider,
        max_tokens=settings.llm_max_tokens,
        timeout_seconds=settings.llm_timeout_seconds,
        actor="analyst-requested",
    )
    if row is None:
        raise HTTPException(status_code=404, detail="incident not found")
    return AIAssessmentOut.model_validate(row, from_attributes=True)


@router.get("/incidents/{incident_id}/ai/assessment", response_model=AIAssessmentOut | None)
async def latest_assessment(incident_id: str, session: AsyncSession = Depends(get_session)):
    row = await get_latest_assessment(session, incident_id)
    if row is None:
        return None
    return AIAssessmentOut.model_validate(row, from_attributes=True)


@router.get("/incidents/{incident_id}/ai/assessments", response_model=list[AIAssessmentOut])
async def assessment_history(incident_id: str, session: AsyncSession = Depends(get_session)):
    rows = await list_assessments(session, incident_id)
    return [AIAssessmentOut.model_validate(r, from_attributes=True) for r in rows]
