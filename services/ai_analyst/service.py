"""AI Analyst orchestration (blueprint AI Analyst §5). This is the ONLY place that ties the
evidence pack, the LLM provider, output validation, and persistence together - route handlers in
`apps/api/ai_routes.py` call `run_analysis` and nothing else, so none of this logic is buried
inside a FastAPI handler.

Failure isolation is the core contract: whatever goes wrong (provider unavailable, timeout,
malformed JSON, hallucinated reference), `run_analysis` always returns a persisted `AIAssessment`
row describing what happened - it never raises out to the caller, and it never touches any table
other than `ai_assessments` and `audit_log`. Nothing here can create/modify a detection or an
incident.
"""

import time
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai.providers.base import LLMProvider, StructuredCompletionError
from ai.schemas import OUTPUT_SCHEMA_VERSION, AIIncidentAssessment
from domain.audit import write_audit
from domain.models.orm import AIAssessment
from services.ai_analyst.evidence import (
    build_evidence_pack,
    evidence_pack_hash,
    evidence_pack_to_model_input,
)
from services.ai_analyst.prompts import PROMPT_VERSION, load_system_prompt
from services.ai_analyst.validation import ReferenceValidationError, validate_assessment


async def run_analysis(
    session: AsyncSession,
    *,
    incident_id: str,
    provider: LLMProvider,
    max_tokens: int,
    timeout_seconds: float,
    actor: str = "system",
) -> AIAssessment | None:
    """Returns None only if `incident_id` does not exist (a real 404, not an AI failure).
    Every other outcome - success, timeout, invalid output, hallucinated reference - is returned
    as a persisted AIAssessment row so the caller always has something to show the analyst."""
    pack = await build_evidence_pack(session, incident_id)
    if pack is None:
        return None

    pack_hash = evidence_pack_hash(pack)
    system_prompt = load_system_prompt()
    evidence_dict = evidence_pack_to_model_input(pack)
    provenance = provider.get_provenance()

    assessment_id = f"AIA-{uuid.uuid4()}"
    validation_status: str
    assessment_payload: dict | None = None
    error: str | None = None

    start = time.monotonic()
    try:
        result: AIIncidentAssessment = await provider.structured_completion(
            system_prompt=system_prompt,
            evidence=evidence_dict,
            output_schema=AIIncidentAssessment,
            max_tokens=max_tokens,
            timeout_seconds=timeout_seconds,
        )
        validate_assessment(result, pack)
        assessment_payload = result.model_dump()
        validation_status = "VALID"
    except ReferenceValidationError as exc:
        error = str(exc)
        validation_status = "REJECTED_HALLUCINATION"
    except StructuredCompletionError as exc:
        error = str(exc)
        validation_status = "TIMEOUT" if "timeout" in str(exc).lower() else "PROVIDER_ERROR"
    latency_ms = int((time.monotonic() - start) * 1000)

    row = AIAssessment(
        assessment_id=assessment_id,
        incident_id=incident_id,
        model_name=provenance.model_name,
        model_provider=provenance.model_provider,
        model_revision=provenance.model_revision,
        model_quantization=provenance.model_quantization,
        prompt_version=PROMPT_VERSION,
        evidence_pack_hash=pack_hash,
        output_schema_version=OUTPUT_SCHEMA_VERSION,
        assessment=assessment_payload,
        validation_status=validation_status,
        latency_ms=latency_ms,
        error=error,
        scenario_id=pack.scenario_id,
    )
    session.add(row)

    await write_audit(
        session,
        entity_type="incident",
        entity_id=incident_id,
        action="incident.ai_analyzed",
        actor=actor,
        scenario_id=pack.scenario_id,
        detail={
            "assessment_id": assessment_id,
            "validation_status": validation_status,
            "latency_ms": latency_ms,
            "model_name": provenance.model_name,
        },
    )
    await session.commit()
    await session.refresh(row)
    return row


async def get_latest_assessment(session: AsyncSession, incident_id: str) -> AIAssessment | None:
    result = await session.execute(
        select(AIAssessment)
        .where(AIAssessment.incident_id == incident_id)
        .order_by(AIAssessment.created_at.desc())
        .limit(1)
    )
    return result.scalars().first()


async def list_assessments(session: AsyncSession, incident_id: str) -> list[AIAssessment]:
    result = await session.execute(
        select(AIAssessment)
        .where(AIAssessment.incident_id == incident_id)
        .order_by(AIAssessment.created_at.desc())
    )
    return list(result.scalars().all())
