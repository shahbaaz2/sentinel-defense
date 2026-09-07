"""Phase 6: the Response Center API end to end - eligible playbooks, response plan creation
(policy-gated), and the full approve/reject/cancel lifecycle, against real incidents produced by
the real deterministic pipeline. Also covers the AI Analyst's playbook recommendation boundary
(allowlist-only, hallucination rejected) and the AI-disabled manual workflow, using MockProvider
via dependency overrides exactly like tests/integration/test_ai_analyst_api.py.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from ai.providers.mock_provider import MockProvider
from ai.schemas import AIIncidentAssessment
from apps.api.ai_routes import get_llm_provider
from apps.api.config import settings
from apps.api.main import app as sentinel_app
from apps.missionnet.config import settings as missionnet_settings
from apps.missionnet.seed import reset_and_seed as reset_missionnet
from domain.db import Base, SessionLocal, engine
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
    yield
    settings.ai_enabled = False
    sentinel_app.dependency_overrides.pop(get_llm_provider, None)
    await reset_missionnet()
    await reset_sentinel()


async def _api_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=sentinel_app), base_url="http://test")


async def _run_full_pipeline() -> None:
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
        await run_incident_correlation(session)


async def _create_credential_abuse_incident() -> str:
    """3 failed logins for a real seeded user -> DET-001 -> credential-abuse incident, medium
    severity - eligible for RP-001 only."""
    async with AsyncClient(base_url=MISSIONNET_BASE_URL, timeout=10.0) as mn:
        for _ in range(3):
            await mn.post("/identity/login", json={"username": "j.rivera", "password": "wrong"})
    await _run_full_pipeline()
    async with await _api_client() as api:
        incidents = (await api.get("/api/v1/incidents")).json()
    return next(i["incident_id"] for i in incidents if i["category"] == "credential-abuse")


async def _create_multi_signal_incident() -> str:
    """degrade + inject_telemetry on the same asset -> DET-002+DET-004(+DET-005) correlated into
    one asset-degradation incident with >=2 detections - eligible for RP-003 and RP-005."""
    async with AsyncClient(base_url=MISSIONNET_BASE_URL, timeout=10.0) as mn:
        await mn.post(
            "/lab/state/mission-data-api-01/degrade",
            headers=LAB_HEADERS,
            json={"reason": "test"},
        )
        await mn.post(
            "/lab/telemetry/mission-data-api-01/inject",
            headers=LAB_HEADERS,
            json={"battery": 5, "link_quality": 3},
        )
    await _run_full_pipeline()
    async with await _api_client() as api:
        incidents = (await api.get("/api/v1/incidents")).json()
    return next(i["incident_id"] for i in incidents if i["category"] == "asset-degradation")


def _override_provider(provider) -> None:
    sentinel_app.dependency_overrides[get_llm_provider] = lambda: provider


def _plan_body(playbook_id: str, actor: str = "j.analyst") -> dict:
    return {"playbook_id": playbook_id, "actor": actor, "recommendation_source": "analyst"}


# --- eligible playbooks ----------------------------------------------------------------------


async def test_eligible_playbooks_for_credential_abuse_incident():
    incident_id = await _create_credential_abuse_incident()
    async with await _api_client() as api:
        resp = await api.get(f"/api/v1/incidents/{incident_id}/eligible-playbooks")
    assert resp.status_code == 200
    ids = {p["id"] for p in resp.json()}
    assert ids == {"RP-001"}


async def test_eligible_playbooks_unknown_incident_404():
    async with await _api_client() as api:
        resp = await api.get("/api/v1/incidents/INC-does-not-exist/eligible-playbooks")
    assert resp.status_code == 404


# --- response plan creation, policy-gated -----------------------------------------------------


async def test_create_response_plan_for_eligible_playbook_persists_and_audits():
    incident_id = await _create_credential_abuse_incident()
    async with await _api_client() as api:
        resp = await api.post(
            f"/api/v1/incidents/{incident_id}/response-plan", json=_plan_body("RP-001")
        )
        assert resp.status_code == 200
        plan = resp.json()
        assert plan["status"] == "AWAITING_APPROVAL"
        assert plan["policy_decision"] == "ALLOW"
        assert plan["execution_status"] == "EXECUTION_NOT_ENABLED"
        assert plan["playbook_id"] == "RP-001"

        audit = (
            await api.get(
                "/api/v1/audit",
                params={"entity_id": incident_id, "action": "response_plan.created"},
            )
        ).json()
    assert len(audit) == 1
    assert audit[0]["detail"]["response_plan_id"] == plan["response_plan_id"]


async def test_create_response_plan_denied_by_policy_creates_no_plan():
    incident_id = await _create_credential_abuse_incident()
    async with await _api_client() as api:
        resp = await api.post(
            f"/api/v1/incidents/{incident_id}/response-plan", json=_plan_body("RP-003")
        )
        assert resp.status_code == 422
        body = resp.json()["detail"]
        assert body["allowed"] is False
        assert len(body["blocking_reasons"]) > 0

        plans = (await api.get(f"/api/v1/incidents/{incident_id}/response-plans")).json()
    assert plans == []


async def test_create_response_plan_nonexistent_playbook_422():
    incident_id = await _create_credential_abuse_incident()
    async with await _api_client() as api:
        resp = await api.post(
            f"/api/v1/incidents/{incident_id}/response-plan", json=_plan_body("RP-999")
        )
    assert resp.status_code == 422
    assert "does not exist" in str(resp.json()["detail"]["blocking_reasons"])


async def test_create_response_plan_unknown_incident_404():
    async with await _api_client() as api:
        resp = await api.post(
            "/api/v1/incidents/INC-does-not-exist/response-plan", json=_plan_body("RP-001")
        )
    assert resp.status_code == 404


# --- approval lifecycle ------------------------------------------------------------------------


async def _create_plan(incident_id: str, playbook_id: str = "RP-001") -> dict:
    async with await _api_client() as api:
        resp = await api.post(
            f"/api/v1/incidents/{incident_id}/response-plan", json=_plan_body(playbook_id)
        )
    assert resp.status_code == 200
    return resp.json()


async def test_approve_response_plan_records_actor_and_timestamp():
    incident_id = await _create_credential_abuse_incident()
    plan = await _create_plan(incident_id)
    async with await _api_client() as api:
        resp = await api.post(
            f"/api/v1/response-plans/{plan['response_plan_id']}/approve",
            json={"actor": "m.osei", "note": "go ahead"},
        )
        assert resp.status_code == 200
        approved = resp.json()
        assert approved["status"] == "APPROVED"
        assert approved["approved_by"] == "m.osei"
        assert approved["approved_at"] is not None
        assert approved["execution_status"] == "EXECUTION_NOT_ENABLED"

        audit = (
            await api.get(
                "/api/v1/audit",
                params={"entity_id": incident_id, "action": "response_plan.approved"},
            )
        ).json()
    assert len(audit) == 1
    assert audit[0]["actor"] == "m.osei"


async def test_reject_response_plan_requires_reason():
    incident_id = await _create_credential_abuse_incident()
    plan = await _create_plan(incident_id)
    async with await _api_client() as api:
        resp = await api.post(
            f"/api/v1/response-plans/{plan['response_plan_id']}/reject",
            json={"actor": "m.osei", "reason": ""},
        )
    assert resp.status_code == 422


async def test_reject_response_plan_lifecycle():
    incident_id = await _create_credential_abuse_incident()
    plan = await _create_plan(incident_id)
    async with await _api_client() as api:
        resp = await api.post(
            f"/api/v1/response-plans/{plan['response_plan_id']}/reject",
            json={"actor": "m.osei", "reason": "not warranted yet"},
        )
        assert resp.status_code == 200
        rejected = resp.json()
        assert rejected["status"] == "REJECTED"
        assert rejected["rejected_by"] == "m.osei"
        assert rejected["rejection_reason"] == "not warranted yet"


async def test_cancel_response_plan_lifecycle():
    incident_id = await _create_credential_abuse_incident()
    plan = await _create_plan(incident_id)
    async with await _api_client() as api:
        resp = await api.post(
            f"/api/v1/response-plans/{plan['response_plan_id']}/cancel",
            json={"actor": "j.analyst", "note": "duplicate plan"},
        )
        assert resp.status_code == 200
        cancelled = resp.json()
        assert cancelled["status"] == "CANCELLED"
        assert cancelled["cancelled_by"] == "j.analyst"


# --- approval bypass attempts must fail (blueprint §19, §23) -----------------------------------


async def test_cannot_approve_a_plan_twice():
    incident_id = await _create_credential_abuse_incident()
    plan = await _create_plan(incident_id)
    async with await _api_client() as api:
        first = await api.post(
            f"/api/v1/response-plans/{plan['response_plan_id']}/approve", json={"actor": "a"}
        )
        assert first.status_code == 200
        second = await api.post(
            f"/api/v1/response-plans/{plan['response_plan_id']}/approve", json={"actor": "b"}
        )
    assert second.status_code == 409


async def test_cannot_approve_after_rejection():
    incident_id = await _create_credential_abuse_incident()
    plan = await _create_plan(incident_id)
    async with await _api_client() as api:
        rejected = await api.post(
            f"/api/v1/response-plans/{plan['response_plan_id']}/reject",
            json={"actor": "a", "reason": "no"},
        )
        assert rejected.status_code == 200
        approve_attempt = await api.post(
            f"/api/v1/response-plans/{plan['response_plan_id']}/approve", json={"actor": "b"}
        )
    assert approve_attempt.status_code == 409


async def test_cannot_approve_a_cancelled_plan():
    incident_id = await _create_credential_abuse_incident()
    plan = await _create_plan(incident_id)
    async with await _api_client() as api:
        cancelled = await api.post(
            f"/api/v1/response-plans/{plan['response_plan_id']}/cancel", json={"actor": "a"}
        )
        assert cancelled.status_code == 200
        approve_attempt = await api.post(
            f"/api/v1/response-plans/{plan['response_plan_id']}/approve", json={"actor": "b"}
        )
    assert approve_attempt.status_code == 409


async def test_approve_unknown_plan_404():
    async with await _api_client() as api:
        resp = await api.post(
            "/api/v1/response-plans/RESP-does-not-exist/approve", json={"actor": "a"}
        )
    assert resp.status_code == 404


# --- AI playbook recommendation boundary (blueprint §9, §20, §24) ------------------------------


def _assessment(**overrides) -> AIIncidentAssessment:
    defaults: dict = dict(
        classification="credential-stuffing",
        confidence=0.9,
        summary="Automated login attempts.",
        affected_assets=[],
        evidence_refs=[],
        detection_refs=[],
        hypotheses=[],
        recommended_investigation_steps=[],
        attack_techniques=[],
        recommended_playbook_id=None,
        limitations=[],
    )
    defaults.update(overrides)
    return AIIncidentAssessment(**defaults)


async def test_ai_recommends_only_from_the_eligible_allowlist():
    settings.ai_enabled = True
    incident_id = await _create_credential_abuse_incident()
    _override_provider(MockProvider(fixed_output=_assessment(recommended_playbook_id="RP-001")))
    async with await _api_client() as api:
        resp = await api.post(f"/api/v1/incidents/{incident_id}/ai/analyze")
        assert resp.status_code == 200
        result = resp.json()
        assert result["validation_status"] == "VALID"
        assert result["assessment"]["recommended_playbook_id"] == "RP-001"

        # The recommendation can now be turned into a real response plan.
        plan_resp = await api.post(
            f"/api/v1/incidents/{incident_id}/response-plan",
            json={
                "playbook_id": "RP-001",
                "actor": "j.analyst",
                "recommendation_source": "ai",
                "ai_assessment_id": result["assessment_id"],
            },
        )
    assert plan_resp.status_code == 200
    assert plan_resp.json()["recommendation_source"] == "ai"
    assert plan_resp.json()["ai_assessment_id"] == result["assessment_id"]


async def test_hallucinated_playbook_id_rejected_zero_percent_acceptance():
    """RP-999 is not a real playbook and therefore never appears in any incident's
    available_playbook_ids - a model returning it must be rejected outright, exactly like a
    hallucinated event or detection ID."""
    settings.ai_enabled = True
    incident_id = await _create_credential_abuse_incident()
    _override_provider(MockProvider(fixed_output=_assessment(recommended_playbook_id="RP-999")))
    async with await _api_client() as api:
        resp = await api.post(f"/api/v1/incidents/{incident_id}/ai/analyze")
        assert resp.status_code == 200
        result = resp.json()
        assert result["validation_status"] == "REJECTED_HALLUCINATION"
        assert result["assessment"] is None
        assert "RP-999" in result["error"]

        # No response plan can be created from a rejected assessment - there's no assessment_id
        # to reference, and the plan-creation endpoint itself re-validates against the real
        # allowlist regardless of what any assessment claimed.
        plan_resp = await api.post(
            f"/api/v1/incidents/{incident_id}/response-plan", json=_plan_body("RP-999")
        )
    assert plan_resp.status_code == 422


async def test_hallucinated_playbook_outside_eligible_set_for_this_incident_rejected():
    """RP-003 is a real playbook, but not eligible for a credential-abuse incident - citing it
    anyway must be rejected the same way as citing a nonexistent playbook."""
    settings.ai_enabled = True
    incident_id = await _create_credential_abuse_incident()
    _override_provider(MockProvider(fixed_output=_assessment(recommended_playbook_id="RP-003")))
    async with await _api_client() as api:
        resp = await api.post(f"/api/v1/incidents/{incident_id}/ai/analyze")
    result = resp.json()
    assert result["validation_status"] == "REJECTED_HALLUCINATION"


# --- AI-disabled manual workflow (blueprint §16, §22) -------------------------------------------


async def test_full_manual_workflow_with_ai_disabled():
    settings.ai_enabled = False
    incident_id = await _create_multi_signal_incident()

    async with await _api_client() as api:
        # 1. open incident (already have incident_id)
        detail = (await api.get(f"/api/v1/incidents/{incident_id}")).json()
        assert detail["status"] == "OPEN"

        # 2. inspect eligible playbooks
        eligible = (await api.get(f"/api/v1/incidents/{incident_id}/eligible-playbooks")).json()
        eligible_ids = {p["id"] for p in eligible}
        assert "RP-003" in eligible_ids

        # 3-5. choose one, submit for policy evaluation, create response plan
        plan_resp = await api.post(
            f"/api/v1/incidents/{incident_id}/response-plan",
            json={
                "playbook_id": "RP-003",
                "actor": "j.analyst",
                "recommendation_source": "analyst",
            },
        )
        assert plan_resp.status_code == 200
        plan = plan_resp.json()
        assert plan["recommendation_source"] == "analyst"
        assert plan["ai_assessment_id"] is None

        # 6. approve
        approved = await api.post(
            f"/api/v1/response-plans/{plan['response_plan_id']}/approve",
            json={"actor": "j.analyst"},
        )
    assert approved.status_code == 200
    assert approved.json()["status"] == "APPROVED"
    assert approved.json()["execution_status"] == "EXECUTION_NOT_ENABLED"
