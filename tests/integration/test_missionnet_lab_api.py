"""Integration tests against the real MissionNet Postgres database (requires `make dev-up`).

Covers Phase 1 acceptance: MissionNet runs independently, seeded baseline is real, lab-control
mutations are auth-gated and produce an attributable audit trail, and reset restores the exact
baseline (blueprint §7.5, §7.6, Phase 1 acceptance criteria).
"""

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
    # This suite shares one live Postgres with every other test file (no per-test transaction
    # rollback), so the last test here must not leave MissionNet mutated for tests that run after.
    await reset_and_seed()


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_seeded_baseline_sizes():
    async with await _client() as client:
        assets = (await client.get("/assets")).json()
        users = (await client.get("/identity/users")).json()
        tokens = (await client.get("/identity/tokens")).json()
        records = (await client.get("/mission-data/records")).json()

    assert 8 <= len(assets) <= 15
    assert 6 <= len(users) <= 10
    assert 3 <= len(tokens) <= 5
    assert 10 <= len(records) <= 30


async def test_health_reports_nominal_on_fresh_baseline():
    async with await _client() as client:
        resp = await client.get("/health")
    body = resp.json()
    assert body["status"] == "nominal"
    assert body["classification"] == "SYNTHETIC"


async def test_lab_endpoint_rejects_missing_or_wrong_secret():
    async with await _client() as client:
        no_secret = await client.post("/lab/state/telemetry-gateway-02/degrade")
        wrong_secret = await client.post(
            "/lab/state/telemetry-gateway-02/degrade", headers={"X-Lab-Secret": "wrong"}
        )
    assert no_secret.status_code == 403
    assert wrong_secret.status_code == 403


async def test_lab_endpoint_rejects_asset_not_in_inventory():
    async with await _client() as client:
        resp = await client.post("/lab/state/not-a-real-asset/degrade", headers=LAB_HEADERS)
    assert resp.status_code == 404


async def test_degrade_reflects_in_health_and_audit_trail():
    async with await _client() as client:
        degrade_resp = await client.post(
            "/lab/state/telemetry-gateway-02/degrade",
            headers=LAB_HEADERS,
            json={
                "actor_type": "scenario_controller",
                "actor_id": "SCN-TEST",
                "scenario_id": "SCN-TEST",
            },
        )
        assert degrade_resp.status_code == 200

        health = (await client.get("/health")).json()
        assert health["status"] == "degraded"
        assert "telemetry-gateway-02" in health["degraded_assets"]

        audit = (await client.get("/audit")).json()

    latest = audit[0]
    assert latest["action"] == "asset.degrade"
    assert latest["actor_type"] == "scenario_controller"
    assert latest["scenario_id"] == "SCN-TEST"
    assert latest["object_id"] == "telemetry-gateway-02"


async def test_token_revoke_marks_token_invalid():
    async with await _client() as client:
        tokens = (await client.get("/identity/tokens")).json()
        token_id = tokens[0]["token_id"]
        assert tokens[0]["valid"] is True

        resp = await client.post(f"/lab/tokens/{token_id}/revoke", headers=LAB_HEADERS)
        assert resp.status_code == 200

        tokens_after = (await client.get("/identity/tokens")).json()

    revoked = next(t for t in tokens_after if t["token_id"] == token_id)
    assert revoked["valid"] is False
    assert revoked["revoked_at"] is not None


async def test_quarantine_then_restore_round_trip():
    async with await _client() as client:
        quarantine = await client.post(
            "/lab/assets/telemetry-gateway-02/quarantine", headers=LAB_HEADERS
        )
        assert quarantine.json() == {
            "asset_id": "telemetry-gateway-02",
            "status": "quarantined",
            "network_state": "quarantined",
        }

        health_during = (await client.get("/health")).json()
        assert health_during["status"] == "containment_in_progress"
        assert "telemetry-gateway-02" in health_during["quarantined_assets"]

        restore = await client.post("/lab/assets/telemetry-gateway-02/restore", headers=LAB_HEADERS)
        assert restore.json() == {
            "asset_id": "telemetry-gateway-02",
            "status": "nominal",
            "network_state": "normal",
        }

        health_after = (await client.get("/health")).json()
    assert health_after["status"] == "nominal"


async def test_reset_restores_exact_baseline_after_mutation():
    async with await _client() as client:
        await client.post("/lab/state/telemetry-gateway-02/degrade", headers=LAB_HEADERS)
        assert (await client.get("/health")).json()["status"] == "degraded"

        reset_resp = await client.post("/lab/reset", headers=LAB_HEADERS)
        assert reset_resp.status_code == 200

        health = (await client.get("/health")).json()
        audit = (await client.get("/audit")).json()

    assert health["status"] == "nominal"
    assert audit[0]["action"] == "seed.reset"
