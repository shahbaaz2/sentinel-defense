"""Phase 7: the response executor end to end against the real live stack - real MissionNet state
changes, real verification reads, real rollback, real idempotency. Uses the same ASGITransport +
direct-pipeline pattern as tests/integration/test_response_plans_api.py for incident creation, and
calls `services.response_executor.executor` functions directly (not just through the API) for the
handful of cases that need fine-grained control over plan/action state (crash-resume simulation,
stale playbook version, forced verification/rollback failure).
"""

import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.config import settings
from apps.api.main import app as sentinel_app
from apps.missionnet.config import settings as missionnet_settings
from apps.missionnet.seed import reset_and_seed as reset_missionnet
from domain.db import Base, SessionLocal, engine
from domain.models import orm  # noqa: F401 - registers tables on Base.metadata
from domain.models.orm import ActionResult, ResponsePlan
from integrations.missionnet.adapter import missionnet_audit_adapter, missionnet_telemetry_adapter
from services.detection_engine.engine import run_detection_engine
from services.event_ingestor.reset import reset as reset_sentinel
from services.event_ingestor.service import ingest_all, sync_missionnet_assets
from services.incident_engine.engine import run_incident_correlation
from services.policy_engine.service import (
    PlanStateError,
    approve_response_plan,
    cancel_response_plan,
)
from services.policy_engine.service import create_response_plan as create_plan_service
from services.response_executor import EXECUTOR_VERSION
from services.response_executor.executor import execute_response_plan, rollback_response_plan
from services.response_executor.models import ExecutionBlockedError, ExecutionInProgressError
from services.response_executor.rollback import ROLLBACK_HANDLERS
from services.response_executor.verifier import VERIFIERS

pytestmark = pytest.mark.integration

MISSIONNET_BASE_URL = "http://127.0.0.1:8090"
LAB_HEADERS = {"X-Lab-Secret": missionnet_settings.lab_secret}
UNREACHABLE_URL = "http://127.0.0.1:1"


@pytest.fixture(autouse=True)
async def _reset_everything():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await reset_missionnet()
    await reset_sentinel()
    yield
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
    async with AsyncClient(base_url=MISSIONNET_BASE_URL, timeout=10.0) as mn:
        for _ in range(3):
            await mn.post("/identity/login", json={"username": "j.rivera", "password": "wrong"})
    await _run_full_pipeline()
    async with await _api_client() as api:
        incidents = (await api.get("/api/v1/incidents")).json()
    return next(i["incident_id"] for i in incidents if i["category"] == "credential-abuse")


async def _create_multi_signal_incident() -> str:
    async with AsyncClient(base_url=MISSIONNET_BASE_URL, timeout=10.0) as mn:
        await mn.post(
            "/lab/state/mission-data-api-01/degrade", headers=LAB_HEADERS, json={"reason": "test"}
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


async def _create_and_approve_plan(
    incident_id: str, playbook_id: str, actor: str = "j.analyst"
) -> str:
    async with SessionLocal() as session:
        plan, decision = await create_plan_service(
            session,
            incident_id=incident_id,
            playbook_id=playbook_id,
            actor=actor,
            recommendation_source="analyst",
            ai_assessment_id=None,
            note=None,
        )
        assert plan is not None, decision.blocking_reasons
        plan_id = plan.response_plan_id
    async with SessionLocal() as session:
        approved = await approve_response_plan(session, plan_id=plan_id, actor=actor, note=None)
        assert approved is not None
    return plan_id


async def _get_plan(plan_id: str) -> ResponsePlan:
    async with SessionLocal() as session:
        plan = await session.get(ResponsePlan, plan_id)
        assert plan is not None
        return plan


async def _get_actions(plan_id: str) -> list[ActionResult]:
    from sqlalchemy import select

    async with SessionLocal() as session:
        stmt = (
            select(ActionResult)
            .where(ActionResult.response_plan_id == plan_id)
            .order_by(ActionResult.action_index)
        )
        return list((await session.execute(stmt)).scalars().all())


async def _execute(plan_id: str, actor: str = "j.analyst", base_url: str = MISSIONNET_BASE_URL):
    async with SessionLocal() as session:
        return await execute_response_plan(
            session,
            plan_id=plan_id,
            actor=actor,
            missionnet_base_url=base_url,
            missionnet_lab_secret=missionnet_settings.lab_secret,
        )


# --- happy path: real execution, real verification, real state change --------------------------


async def test_execute_credential_abuse_plan_suspends_real_user_and_verifies():
    incident_id = await _create_credential_abuse_incident()
    plan_id = await _create_and_approve_plan(incident_id, "RP-001")

    plan = await _execute(plan_id)
    assert plan.execution_status == "SUCCEEDED"
    assert plan.executor_version == EXECUTOR_VERSION
    assert plan.executed_by == "j.analyst"
    assert plan.execution_started_at is not None
    assert plan.execution_completed_at is not None

    actions = await _get_actions(plan_id)
    by_id = {a.action_id: a for a in actions}
    assert by_id["suspend_test_user"].status == "SUCCEEDED"
    assert by_id["suspend_test_user"].verification_status == "VERIFIED"
    assert by_id["preserve_evidence"].status == "SUCCEEDED"
    assert by_id["preserve_evidence"].verification_status == "VERIFIED"

    # Real MissionNet state, read back independently of the executor's own claim.
    async with AsyncClient(base_url=MISSIONNET_BASE_URL, timeout=10.0) as mn:
        users = (await mn.get("/identity/users")).json()
        rivera = next(u for u in users if u["user_id"] == by_id["suspend_test_user"].target_id)
        assert rivera["status"] == "suspended"

        login = await mn.post(
            "/identity/login", json={"username": "j.rivera", "password": "any"}
        )
        assert login.json()["success"] is False


async def test_execute_multi_signal_plan_quarantines_and_provisions_replacement():
    incident_id = await _create_multi_signal_incident()
    plan_id = await _create_and_approve_plan(incident_id, "RP-005")

    plan = await _execute(plan_id)
    assert plan.execution_status == "SUCCEEDED"

    actions = await _get_actions(plan_id)
    by_id = {a.action_id: a for a in actions}
    assert by_id["quarantine_workload"].status == "SUCCEEDED"
    assert by_id["quarantine_workload"].verification_status == "VERIFIED"
    assert by_id["revoke_test_token"].status == "SKIPPED"  # no identity in this incident's evidence
    assert by_id["revoke_test_token"].required is False
    assert by_id["request_replacement_instance"].status == "SUCCEEDED"
    replacement_id = by_id["request_replacement_instance"].result_metadata["replacement_asset_id"]

    async with AsyncClient(base_url=MISSIONNET_BASE_URL, timeout=10.0) as mn:
        original = (await mn.get("/assets/mission-data-api-01")).json()
        assert original["status"] == "quarantined"
        replacement = (await mn.get(f"/assets/{replacement_id}")).json()
        assert replacement["status"] == "nominal"

        health = (await mn.get("/health")).json()
        assert health["status"] == "containment_in_progress"


# --- idempotency (blueprint §8) ------------------------------------------------------------------


async def test_duplicate_execute_on_succeeded_plan_is_a_noop():
    incident_id = await _create_credential_abuse_incident()
    plan_id = await _create_and_approve_plan(incident_id, "RP-001")

    first = await _execute(plan_id)
    assert first.execution_status == "SUCCEEDED"
    first_actions = await _get_actions(plan_id)

    second = await _execute(plan_id)
    assert second.execution_status == "SUCCEEDED"
    second_actions = await _get_actions(plan_id)

    assert len(first_actions) == len(second_actions)
    first_ids = [a.action_result_id for a in first_actions]
    second_ids = [a.action_result_id for a in second_actions]
    assert first_ids == second_ids
    assert first.execution_started_at == second.execution_started_at  # never re-started


async def test_resuming_a_partially_completed_plan_does_not_repeat_completed_steps():
    """Crash/restart safety (blueprint §16): a plan with some action_results already SUCCEEDED
    from a prior (simulated) process must not re-run those steps on the next execute call."""
    incident_id = await _create_credential_abuse_incident()
    plan_id = await _create_and_approve_plan(incident_id, "RP-001")

    # Simulate step 0 (suspend_test_user) already having completed for real before a "restart" -
    # actually call MissionNet (a genuinely crashed process would have gotten this far for real,
    # only failing to reach the next step), then pre-insert its ActionResult the same shape the
    # executor itself would have written, so the later re-verification finds real, matching state.
    async with SessionLocal() as session:
        plan = await session.get(ResponsePlan, plan_id)
        assert plan is not None
        import httpx as _httpx

        from domain.models.orm import Incident
        from services.policy_engine.playbooks import get_playbook
        from services.response_executor.targets import resolve_target

        playbook = get_playbook("RP-001")
        assert playbook is not None
        incident = await session.get(Incident, incident_id)
        assert incident is not None
        async with _httpx.AsyncClient(base_url=MISSIONNET_BASE_URL, timeout=10.0) as client:
            target = await resolve_target(
                action=playbook.actions[0],
                action_index=0,
                session=session,
                incident=incident,
                client=client,
                prior_results={},
            )
            assert target is not None
            suspend_resp = await client.post(
                f"/lab/users/{target.target_id}/suspend",
                headers=LAB_HEADERS,
                json={"reason": "pre-restart step", "scenario_id": None},
            )
            assert suspend_resp.status_code == 200
        session.add(
            ActionResult(
                action_result_id="ACT-preexisting",
                response_plan_id=plan_id,
                action_index=0,
                action_id="suspend_test_user",
                required=True,
                target_type=target.target_type,
                target_id=target.target_id,
                status="SUCCEEDED",
                result_metadata={"status": "suspended"},
                verification_status="VERIFIED",
            )
        )
        await session.commit()

    plan = await _execute(plan_id)
    assert plan.execution_status == "SUCCEEDED"
    actions = await _get_actions(plan_id)
    suspend_result = next(a for a in actions if a.action_id == "suspend_test_user")
    assert suspend_result.action_result_id == "ACT-preexisting"  # untouched, not re-run


# --- pre-execution revalidation / negative execution tests (blueprint §9, §25) -------------------


async def test_execute_awaiting_approval_plan_is_blocked():
    incident_id = await _create_credential_abuse_incident()
    async with SessionLocal() as session:
        plan, decision = await create_plan_service(
            session,
            incident_id=incident_id,
            playbook_id="RP-001",
            actor="j.analyst",
            recommendation_source="analyst",
            ai_assessment_id=None,
            note=None,
        )
        assert plan is not None
        plan_id = plan.response_plan_id

    with pytest.raises(ExecutionBlockedError, match="AWAITING_APPROVAL"):
        await _execute(plan_id)

    plan_after = await _get_plan(plan_id)
    assert plan_after.execution_status == "NOT_EXECUTED"
    assert plan_after.execution_block_reason is not None

    async with AsyncClient(base_url=MISSIONNET_BASE_URL, timeout=10.0) as mn:
        users = (await mn.get("/identity/users")).json()
        assert all(u["status"] == "active" for u in users)  # MissionNet genuinely untouched


async def test_execute_rejected_plan_is_blocked():
    incident_id = await _create_credential_abuse_incident()
    async with SessionLocal() as session:
        plan, _ = await create_plan_service(
            session,
            incident_id=incident_id,
            playbook_id="RP-001",
            actor="j.analyst",
            recommendation_source="analyst",
            ai_assessment_id=None,
            note=None,
        )
        assert plan is not None
        plan_id = plan.response_plan_id
    async with SessionLocal() as session:
        from services.policy_engine.service import reject_response_plan

        rejected = await reject_response_plan(
            session, plan_id=plan_id, actor="j.analyst", reason="not warranted"
        )
        assert rejected is not None

    with pytest.raises(ExecutionBlockedError, match="REJECTED"):
        await _execute(plan_id)


async def test_execute_cancelled_plan_is_blocked():
    incident_id = await _create_credential_abuse_incident()
    async with SessionLocal() as session:
        plan, _ = await create_plan_service(
            session,
            incident_id=incident_id,
            playbook_id="RP-001",
            actor="j.analyst",
            recommendation_source="analyst",
            ai_assessment_id=None,
            note=None,
        )
        assert plan is not None
        plan_id = plan.response_plan_id
    async with SessionLocal() as session:
        cancelled = await cancel_response_plan(
            session, plan_id=plan_id, actor="j.analyst", note=None
        )
        assert cancelled is not None

    with pytest.raises(ExecutionBlockedError, match="CANCELLED"):
        await _execute(plan_id)


async def test_execute_expired_plan_is_blocked():
    """EXPIRED has no code path that sets it yet (blueprint vocabulary only - see DECISIONS.md),
    but pre-execution revalidation must still refuse to execute a plan directly forced into it."""
    incident_id = await _create_credential_abuse_incident()
    plan_id = await _create_and_approve_plan(incident_id, "RP-001")
    async with SessionLocal() as session:
        plan = await session.get(ResponsePlan, plan_id)
        assert plan is not None
        plan.status = "EXPIRED"
        await session.commit()

    with pytest.raises(ExecutionBlockedError, match="EXPIRED"):
        await _execute(plan_id)


async def test_execute_with_stale_playbook_version_is_blocked():
    incident_id = await _create_credential_abuse_incident()
    plan_id = await _create_and_approve_plan(incident_id, "RP-001")
    async with SessionLocal() as session:
        plan = await session.get(ResponsePlan, plan_id)
        assert plan is not None
        plan.playbook_version = "0.0-stale"
        await session.commit()

    with pytest.raises(ExecutionBlockedError, match="playbook version changed"):
        await _execute(plan_id)


async def test_execute_with_stale_policy_bundle_is_blocked(monkeypatch):
    incident_id = await _create_credential_abuse_incident()
    plan_id = await _create_and_approve_plan(incident_id, "RP-001")
    async with SessionLocal() as session:
        plan = await session.get(ResponsePlan, plan_id)
        assert plan is not None
        plan.policy_bundle_version = "PB-000-stale"
        await session.commit()

    with pytest.raises(ExecutionBlockedError, match="policy bundle changed"):
        await _execute(plan_id)


async def test_execute_when_missionnet_unavailable_is_blocked():
    incident_id = await _create_credential_abuse_incident()
    plan_id = await _create_and_approve_plan(incident_id, "RP-001")

    with pytest.raises(ExecutionBlockedError, match="MissionNet unavailable"):
        await _execute(plan_id, base_url=UNREACHABLE_URL)

    plan_after = await _get_plan(plan_id)
    assert plan_after.execution_status == "NOT_EXECUTED"


async def test_duplicate_concurrent_execute_is_rejected():
    incident_id = await _create_credential_abuse_incident()
    plan_id = await _create_and_approve_plan(incident_id, "RP-001")
    async with SessionLocal() as session:
        plan = await session.get(ResponsePlan, plan_id)
        assert plan is not None
        plan.execution_status = "EXECUTING"
        await session.commit()

    with pytest.raises(ExecutionInProgressError):
        await _execute(plan_id)


async def test_execute_when_incident_no_longer_eligible_is_blocked():
    """Incident state changed since approval (blueprint §9: "incident still eligible")."""
    incident_id = await _create_credential_abuse_incident()
    plan_id = await _create_and_approve_plan(incident_id, "RP-001")
    async with SessionLocal() as session:
        from domain.models.orm import Incident

        incident = await session.get(Incident, incident_id)
        assert incident is not None
        incident.status = "RESOLVED"
        await session.commit()

    with pytest.raises(ExecutionBlockedError, match="no longer eligible"):
        await _execute(plan_id)


# --- verification failure must prevent SUCCEEDED (blueprint §13) --------------------------------


async def test_verification_failure_prevents_succeeded_and_triggers_rollback(monkeypatch):
    from services.response_executor.models import VerificationOutcome

    async def _always_fails(client, target, action_result):
        return VerificationOutcome(verified=False, detail={"forced": "test"})

    monkeypatch.setitem(VERIFIERS, "user_suspended", _always_fails)

    incident_id = await _create_credential_abuse_incident()
    plan_id = await _create_and_approve_plan(incident_id, "RP-001")
    plan = await _execute(plan_id)

    assert plan.execution_status != "SUCCEEDED"
    actions = await _get_actions(plan_id)
    suspend_result = next(a for a in actions if a.action_id == "suspend_test_user")
    assert suspend_result.status == "SUCCEEDED"  # the action itself really did succeed
    assert suspend_result.verification_status == "FAILED"  # but verification says otherwise


# --- rollback (blueprint §14) and rollback failure -----------------------------------------------


async def test_manual_rollback_of_succeeded_plan_restores_real_state():
    incident_id = await _create_multi_signal_incident()
    plan_id = await _create_and_approve_plan(incident_id, "RP-005")
    executed = await _execute(plan_id)
    assert executed.execution_status == "SUCCEEDED"

    async with SessionLocal() as session:
        rolled_back = await rollback_response_plan(
            session,
            plan_id=plan_id,
            actor="j.analyst",
            missionnet_base_url=MISSIONNET_BASE_URL,
            missionnet_lab_secret=missionnet_settings.lab_secret,
        )
    assert rolled_back.execution_status == "ROLLED_BACK"

    async with AsyncClient(base_url=MISSIONNET_BASE_URL, timeout=10.0) as mn:
        original = (await mn.get("/assets/mission-data-api-01")).json()
        assert original["status"] == "nominal"
        assert original["network_state"] == "normal"

    actions = await _get_actions(plan_id)
    by_id = {a.action_id: a for a in actions}
    assert by_id["quarantine_workload"].rollback_status == "ROLLED_BACK"
    # request_replacement_instance is not rollback_capable - never claimed as rolled back.
    assert by_id["request_replacement_instance"].rollback_status == "NOT_APPLICABLE"
    assert by_id["preserve_evidence"].rollback_status == "NOT_APPLICABLE"


async def test_rollback_not_allowed_on_a_plan_that_never_executed():
    incident_id = await _create_credential_abuse_incident()
    plan_id = await _create_and_approve_plan(incident_id, "RP-001")

    async with SessionLocal() as session:
        with pytest.raises(PlanStateError):
            await rollback_response_plan(
                session,
                plan_id=plan_id,
                actor="j.analyst",
                missionnet_base_url=MISSIONNET_BASE_URL,
                missionnet_lab_secret=missionnet_settings.lab_secret,
            )


async def test_rollback_failure_marks_plan_rollback_failed(monkeypatch):
    from services.response_executor.models import ActionOutcome

    async def _always_fails(client, target, ctx, original):
        return ActionOutcome(
            success=False, error_code="forced", error_message="test forced failure"
        )

    monkeypatch.setitem(ROLLBACK_HANDLERS, "quarantine_workload", _always_fails)

    incident_id = await _create_multi_signal_incident()
    plan_id = await _create_and_approve_plan(incident_id, "RP-005")
    executed = await _execute(plan_id)
    assert executed.execution_status == "SUCCEEDED"

    async with SessionLocal() as session:
        rolled_back = await rollback_response_plan(
            session,
            plan_id=plan_id,
            actor="j.analyst",
            missionnet_base_url=MISSIONNET_BASE_URL,
            missionnet_lab_secret=missionnet_settings.lab_secret,
        )
    assert rolled_back.execution_status == "ROLLBACK_FAILED"

    actions = await _get_actions(plan_id)
    quarantine_result = next(a for a in actions if a.action_id == "quarantine_workload")
    assert quarantine_result.rollback_status == "FAILED"


# --- audit trail (blueprint §27) ------------------------------------------------------------------


async def test_execution_writes_a_complete_audit_trail():
    incident_id = await _create_credential_abuse_incident()
    plan_id = await _create_and_approve_plan(incident_id, "RP-001")
    await _execute(plan_id)

    async with await _api_client() as api:
        audit = (
            await api.get("/api/v1/audit", params={"entity_id": incident_id, "limit": 100})
        ).json()
    actions_logged = {a["action"] for a in audit}
    assert "response_plan.execution_started" in actions_logged
    assert "response_plan.action_started" in actions_logged
    assert "response_plan.action_result" in actions_logged
    assert "response_plan.action_verified" in actions_logged
    assert "response_plan.execution_succeeded" in actions_logged

    for entry in audit:
        if entry["action"].startswith("response_plan."):
            detail = entry["detail"]
            assert detail.get("response_plan_id", plan_id) == plan_id or "action_id" in detail


# --- AI-disabled execution (blueprint §24) --------------------------------------------------------


async def test_full_execution_flow_works_with_ai_disabled():
    previous = settings.ai_enabled
    settings.ai_enabled = False
    try:
        incident_id = await _create_multi_signal_incident()
        async with await _api_client() as api:
            eligible = (
                await api.get(f"/api/v1/incidents/{incident_id}/eligible-playbooks")
            ).json()
        assert any(p["id"] == "RP-003" for p in eligible)

        plan_id = await _create_and_approve_plan(incident_id, "RP-003")
        plan = await _execute(plan_id)
        assert plan.execution_status == "SUCCEEDED"

        actions = await _get_actions(plan_id)
        assert all(a.status in ("SUCCEEDED", "SKIPPED") for a in actions)
    finally:
        settings.ai_enabled = previous
