"""Phase 5: the AI Analyst API end to end - status, analyze, assessment, assessments - against a
real incident, real evidence pack, and real persistence/audit trail. Uses `MockProvider` via
FastAPI's dependency_overrides (the same in-process ASGI pattern already used by
tests/integration/test_sentinel_ingestion_pipeline.py) so these results are fully deterministic
and don't require MLX/a downloaded model to be present - the live local-model verification lives
in test_ai_analyst_mlx_live.py instead, matching blueprint AI Analyst §25's split between
"hallucinated reference rejection" (must be deterministic) and "actual local model runs" (must be
live, but doesn't need to gate every CI run on Apple Silicon hardware).
"""

import pytest
from httpx import ASGITransport, AsyncClient

from ai.providers.base import StructuredCompletionError
from ai.providers.mock_provider import MockProvider
from ai.schemas import AIIncidentAssessment, DetectionReference, EvidenceReference
from apps.api.ai_routes import get_llm_provider
from apps.api.config import settings
from apps.api.main import app as sentinel_app
from apps.missionnet.config import settings as missionnet_settings
from apps.missionnet.seed import reset_and_seed as reset_missionnet
from domain.db import Base, engine
from domain.models import orm  # noqa: F401 - registers tables on Base.metadata
from integrations.missionnet.adapter import missionnet_audit_adapter, missionnet_telemetry_adapter
from services.detection_engine.engine import run_detection_engine
from services.event_ingestor.reset import reset as reset_sentinel
from services.event_ingestor.service import ingest_all, sync_missionnet_assets
from services.incident_engine.engine import run_incident_correlation

pytestmark = pytest.mark.integration

MISSIONNET_BASE_URL = "http://127.0.0.1:8090"
LAB_HEADERS = {"X-Lab-Secret": missionnet_settings.lab_secret}


@pytest.fixture(autouse=True)
async def _reset_everything():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await reset_missionnet()
    await reset_sentinel()
    settings.ai_enabled = True
    yield
    settings.ai_enabled = False
    sentinel_app.dependency_overrides.pop(get_llm_provider, None)
    await reset_missionnet()
    await reset_sentinel()


def _override_provider(provider) -> None:
    sentinel_app.dependency_overrides[get_llm_provider] = lambda: provider


async def _api_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=sentinel_app), base_url="http://test")


async def _create_real_incident() -> str:
    """Three failed logins for the same (real, seeded) user -> DET-001 -> one incident. Identical
    signal shape to test_sentinel_ingestion_pipeline.py's idempotency test."""
    async with AsyncClient(base_url=MISSIONNET_BASE_URL, timeout=10.0) as mn:
        for _ in range(3):
            await mn.post("/identity/login", json={"username": "j.rivera", "password": "wrong"})

    from domain.db import SessionLocal

    async with SessionLocal() as session:
        await sync_missionnet_assets(session, MISSIONNET_BASE_URL)
    async with SessionLocal() as session:
        adapters = {
            "audit": missionnet_audit_adapter(MISSIONNET_BASE_URL),
            "telemetry": missionnet_telemetry_adapter(MISSIONNET_BASE_URL),
        }
        await ingest_all(session, adapters)
    async with SessionLocal() as session:
        await run_detection_engine(session)
    async with SessionLocal() as session:
        incident_result = await run_incident_correlation(session)
    assert incident_result.incidents_created == 1

    async with await _api_client() as api:
        incidents = (await api.get("/api/v1/incidents")).json()
    return incidents[0]["incident_id"]


def _assessment(**overrides) -> AIIncidentAssessment:
    defaults: dict = dict(
        classification="credential-stuffing",
        confidence=0.85,
        summary="Repeated failed logins consistent with automated credential stuffing.",
        affected_assets=[],
        evidence_refs=[],
        detection_refs=[],
        hypotheses=["Automated login attempt"],
        recommended_investigation_steps=["Check source reputation"],
        attack_techniques=["T1110"],
        recommended_playbook_id=None,
        limitations=["Synthetic evidence only"],
    )
    defaults.update(overrides)
    return AIIncidentAssessment(**defaults)


async def test_ai_status_reports_disabled_when_config_off():
    settings.ai_enabled = False
    async with await _api_client() as api:
        resp = await api.get("/api/v1/ai/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ai_enabled"] is False
    assert body["status"] == "DISABLED"


async def test_analyze_returns_503_when_ai_disabled():
    settings.ai_enabled = False
    incident_id = await _create_real_incident()
    async with await _api_client() as api:
        resp = await api.post(f"/api/v1/incidents/{incident_id}/ai/analyze")
    assert resp.status_code == 503


async def test_analyze_unknown_incident_returns_404():
    _override_provider(MockProvider(raise_error=StructuredCompletionError("unused")))
    async with await _api_client() as api:
        resp = await api.post("/api/v1/incidents/INC-does-not-exist/ai/analyze")
    assert resp.status_code == 404


async def test_assessment_endpoint_returns_null_when_none_exists():
    incident_id = await _create_real_incident()
    async with await _api_client() as api:
        resp = await api.get(f"/api/v1/incidents/{incident_id}/ai/assessment")
    assert resp.status_code == 200
    assert resp.json() is None


async def test_successful_analysis_cites_real_evidence_and_is_audited():
    incident_id = await _create_real_incident()
    async with await _api_client() as api:
        detail = (await api.get(f"/api/v1/incidents/{incident_id}")).json()
    event_id = detail["event_ids"][0]
    detection_id = detail["detection_ids"][0]

    fixed = _assessment(
        evidence_refs=[EvidenceReference(event_id=event_id, relevance="shows the failures")],
        detection_refs=[DetectionReference(detection_id=detection_id, relevance="fired")],
    )
    _override_provider(MockProvider(fixed_output=fixed))

    async with await _api_client() as api:
        analyze_resp = await api.post(f"/api/v1/incidents/{incident_id}/ai/analyze")
        assert analyze_resp.status_code == 200
        body = analyze_resp.json()
        assert body["validation_status"] == "VALID"
        assert body["assessment"]["classification"] == "credential-stuffing"
        assert body["assessment"]["evidence_refs"][0]["event_id"] == event_id
        assert body["model_provider"] == "mock"
        assert body["prompt_version"] == "incident_analysis_v1"

        latest = (await api.get(f"/api/v1/incidents/{incident_id}/ai/assessment")).json()
        assert latest["assessment_id"] == body["assessment_id"]

        history = (await api.get(f"/api/v1/incidents/{incident_id}/ai/assessments")).json()
        assert len(history) == 1

        audit = (
            await api.get(
                "/api/v1/audit",
                params={"entity_id": incident_id, "action": "incident.ai_analyzed"},
            )
        ).json()
    assert len(audit) == 1
    assert audit[0]["detail"]["validation_status"] == "VALID"


async def test_reanalysis_creates_new_history_entry_without_deleting_the_old_one():
    incident_id = await _create_real_incident()

    _override_provider(MockProvider(fixed_output=_assessment(summary="first pass")))
    async with await _api_client() as api:
        first = (await api.post(f"/api/v1/incidents/{incident_id}/ai/analyze")).json()

    _override_provider(MockProvider(fixed_output=_assessment(summary="second pass")))
    async with await _api_client() as api:
        second = (await api.post(f"/api/v1/incidents/{incident_id}/ai/analyze")).json()
        history = (await api.get(f"/api/v1/incidents/{incident_id}/ai/assessments")).json()
        latest = (await api.get(f"/api/v1/incidents/{incident_id}/ai/assessment")).json()

    assert first["assessment_id"] != second["assessment_id"]
    assert len(history) == 2
    history_ids = {h["assessment_id"] for h in history}
    assert history_ids == {first["assessment_id"], second["assessment_id"]}
    assert latest["assessment_id"] == second["assessment_id"]
    assert latest["assessment"]["summary"] == "second pass"


async def test_hallucinated_event_id_is_rejected_and_not_displayed_as_evidence():
    incident_id = await _create_real_incident()
    fake = _assessment(
        evidence_refs=[EvidenceReference(event_id="EVT-does-not-exist", relevance="fabricated")]
    )
    _override_provider(MockProvider(fixed_output=fake))

    async with await _api_client() as api:
        resp = await api.post(f"/api/v1/incidents/{incident_id}/ai/analyze")
        assert resp.status_code == 200
        body = resp.json()
        assert body["validation_status"] == "REJECTED_HALLUCINATION"
        assert body["assessment"] is None
        assert "EVT-does-not-exist" in body["error"]

        # The incident itself must be completely unaffected by a rejected assessment.
        detail = (await api.get(f"/api/v1/incidents/{incident_id}")).json()
    assert detail["status"] == "OPEN"


async def test_hallucinated_detection_id_is_rejected():
    incident_id = await _create_real_incident()
    fake = _assessment(
        detection_refs=[DetectionReference(detection_id="DET-999-fake", relevance="fabricated")]
    )
    _override_provider(MockProvider(fixed_output=fake))
    async with await _api_client() as api:
        resp = await api.post(f"/api/v1/incidents/{incident_id}/ai/analyze")
    assert resp.json()["validation_status"] == "REJECTED_HALLUCINATION"


async def test_provider_timeout_is_isolated_and_incident_state_unaffected():
    incident_id = await _create_real_incident()
    _override_provider(
        MockProvider(raise_error=StructuredCompletionError("MLX inference exceeded 90.0s timeout"))
    )
    async with await _api_client() as api:
        resp = await api.post(f"/api/v1/incidents/{incident_id}/ai/analyze")
        assert resp.status_code == 200
        body = resp.json()
        assert body["validation_status"] == "TIMEOUT"
        assert body["assessment"] is None

        detail = (await api.get(f"/api/v1/incidents/{incident_id}")).json()
    assert detail["status"] == "OPEN"
    assert detail["severity"] is not None  # unchanged, still whatever deterministic code set


async def test_provider_error_other_than_timeout_is_isolated():
    incident_id = await _create_real_incident()
    _override_provider(MockProvider(raise_error=StructuredCompletionError("model load failed")))
    async with await _api_client() as api:
        resp = await api.post(f"/api/v1/incidents/{incident_id}/ai/analyze")
    body = resp.json()
    assert body["validation_status"] == "PROVIDER_ERROR"
    assert body["assessment"] is None


async def test_evidence_pack_hash_is_recorded_and_stable_for_same_incident():
    incident_id = await _create_real_incident()
    _override_provider(MockProvider(fixed_output=_assessment()))
    async with await _api_client() as api:
        first = (await api.post(f"/api/v1/incidents/{incident_id}/ai/analyze")).json()
        second = (await api.post(f"/api/v1/incidents/{incident_id}/ai/analyze")).json()
    assert first["evidence_pack_hash"] == second["evidence_pack_hash"]
    assert len(first["evidence_pack_hash"]) == 64  # sha256 hex digest
