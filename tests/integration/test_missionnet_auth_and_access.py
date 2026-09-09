"""Covers the MissionNet extensions added for Phase 2: genuine auth/record-access audit events and
cursor-based polling support - these are what Sentinel's adapter ingests, not fabricated signals."""

import pytest
from httpx import ASGITransport, AsyncClient

from apps.missionnet.config import settings
from apps.missionnet.main import app
from apps.missionnet.seed import reset_and_seed

pytestmark = pytest.mark.integration

LAB_HEADERS = {"X-Lab-Secret": settings.lab_secret}


@pytest.fixture(autouse=True)
async def _reset_baseline():
    await reset_and_seed()
    yield
    # Shared live Postgres across all test files (no per-test rollback) - reset on teardown too.
    await reset_and_seed()


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_login_success_writes_auth_success_audit_event():
    async with await _client() as client:
        resp = await client.post(
            "/identity/login", json={"username": "j.rivera", "password": "SynthLab#2026"}
        )
        assert resp.json() == {"success": True, "user_id": "u-operator-01", "reason": None}

        audit = (await client.get("/audit")).json()
    assert audit[0]["action"] == "auth.success"
    assert audit[0]["object_id"] == "u-operator-01"


async def test_login_failure_writes_auth_failure_audit_event():
    async with await _client() as client:
        resp = await client.post(
            "/identity/login", json={"username": "j.rivera", "password": "wrong"}
        )
        assert resp.json()["success"] is False

        audit = (await client.get("/audit")).json()
    assert audit[0]["action"] == "auth.failure"
    assert audit[0]["severity"] == "low"


async def test_login_unknown_user_fails_without_error():
    async with await _client() as client:
        resp = await client.post(
            "/identity/login", json={"username": "not-a-real-user", "password": "x"}
        )
    assert resp.status_code == 200
    assert resp.json()["success"] is False


async def test_record_access_requires_actor_and_writes_audit_event():
    async with await _client() as client:
        missing_actor = await client.get("/mission-data/records/rec-000")
        assert missing_actor.status_code == 422

        resp = await client.get(
            "/mission-data/records/rec-000", params={"actor_user_id": "u-analyst-01"}
        )
        assert resp.status_code == 200

        audit = (await client.get("/audit")).json()
    assert audit[0]["action"] == "record.access"
    assert audit[0]["actor_id"] == "u-analyst-01"
    assert audit[0]["object_id"] == "rec-000"


async def test_record_access_without_run_id_creates_a_fresh_event_every_call():
    """Callers outside the scenario runner (no run_id/step_id) keep the pre-existing behavior -
    no idempotency key to dedupe on, so every call is its own genuine access."""
    async with await _client() as client:
        params = {"actor_user_id": "u-analyst-01"}
        await client.get("/mission-data/records/rec-000", params=params)
        await client.get("/mission-data/records/rec-000", params=params)
        audit = (await client.get("/audit")).json()
    record_accesses = [a for a in audit if a["action"] == "record.access"]
    assert len(record_accesses) == 2


async def test_record_access_retry_with_same_run_and_step_id_is_idempotent():
    """The exact scenario this exists for: Demo Control retries the same scenario step after a
    transient gateway error - MissionNet must not record a second record.access AuditEvent for
    what is really one logical action (see apps/demo_control/actions.py::access_record and
    DECISIONS.md)."""
    async with await _client() as client:
        params = {
            "actor_user_id": "svc-mission-data-01",
            "run_id": "RUN-test-123",
            "step_id": "step-3",
        }
        first = await client.get("/mission-data/records/rec-000", params=params)
        second = await client.get("/mission-data/records/rec-000", params=params)
        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json() == second.json()

        audit = (await client.get("/audit")).json()
    record_accesses = [a for a in audit if a["action"] == "record.access"]
    assert len(record_accesses) == 1  # not 2 - the retry was a genuine no-op


async def test_record_access_different_step_id_is_a_genuinely_new_event():
    """Idempotency must be scoped to (run_id, step_id) - a different step in the same run (or a
    different run) accessing the same record is a real, distinct access, not a duplicate."""
    async with await _client() as client:
        await client.get(
            "/mission-data/records/rec-000",
            params={"actor_user_id": "u-analyst-01", "run_id": "RUN-a", "step_id": "step-3"},
        )
        await client.get(
            "/mission-data/records/rec-000",
            params={"actor_user_id": "u-analyst-01", "run_id": "RUN-a", "step_id": "step-7"},
        )
        audit = (await client.get("/audit")).json()
    record_accesses = [a for a in audit if a["action"] == "record.access"]
    assert len(record_accesses) == 2


async def test_audit_since_filters_and_orders_ascending():
    async with await _client() as client:
        baseline_audit = (await client.get("/audit")).json()
        reset_time = baseline_audit[0]["timestamp"]

        await client.post("/identity/login", json={"username": "j.rivera", "password": "wrong"})
        await client.post(
            "/identity/login", json={"username": "j.rivera", "password": "SynthLab#2026"}
        )

        since_page = (await client.get("/audit", params={"since": reset_time})).json()

    assert len(since_page) == 2
    assert since_page[0]["action"] == "auth.failure"
    assert since_page[1]["action"] == "auth.success"


async def test_telemetry_inject_requires_lab_secret_and_appears_in_since_query():
    async with await _client() as client:
        baseline = (await client.get("/telemetry")).json()
        watermark = baseline[0]["generated_at"]

        no_secret = await client.post(
            "/lab/telemetry/sim-uav-017/inject", json={"battery": 5, "link_quality": 10}
        )
        assert no_secret.status_code == 403

        injected = await client.post(
            "/lab/telemetry/sim-uav-017/inject",
            headers=LAB_HEADERS,
            json={"battery": 5, "link_quality": 10},
        )
        assert injected.status_code == 200

        since_page = (
            await client.get("/telemetry", params={"since": watermark})
        ).json()

    assert len(since_page) == 1
    assert since_page[0]["battery"] == 5
    assert since_page[0]["asset_id"] == "sim-uav-017"
