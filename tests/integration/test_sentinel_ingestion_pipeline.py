"""The canonical Phase 2 proof: MissionNet produces genuine signals -> Sentinel's adapter ingests
them over real HTTP -> normalization -> deterministic detection -> deterministic correlation ->
incident, exposed through Sentinel's own API. No AI anywhere in this chain.

Requires BOTH `make dev-up` (Postgres) AND a live MissionNet server (`make missionnet` on :8090) -
unlike the MissionNet-only integration tests, this suite deliberately crosses a real network hop
rather than calling MissionNet's ASGI app in-process, because proving that hop is Phase 2's point.
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

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
    yield
    # Tear down too: this suite shares one live Postgres with every other test file (no per-test
    # transaction rollback), so whichever test runs last must not leave MissionNet/Sentinel mutated
    # for unrelated tests that run afterward.
    await reset_missionnet()
    await reset_sentinel()


async def _missionnet_client() -> AsyncClient:
    """A real HTTP client against the live MissionNet process, not ASGI transport - Sentinel's
    adapter must genuinely cross the network, so the test drives MissionNet the same way."""
    return AsyncClient(base_url=MISSIONNET_BASE_URL, timeout=10.0)


async def _run_full_pipeline(sentinel_session_factory) -> dict:
    async with sentinel_session_factory() as session:
        assets_synced = await sync_missionnet_assets(session, MISSIONNET_BASE_URL)

    async with sentinel_session_factory() as session:
        adapters = {
            "audit": missionnet_audit_adapter(MISSIONNET_BASE_URL),
            "telemetry": missionnet_telemetry_adapter(MISSIONNET_BASE_URL),
        }
        ingestion_results = await ingest_all(session, adapters)

    async with sentinel_session_factory() as session:
        detection_result = await run_detection_engine(session)

    async with sentinel_session_factory() as session:
        incident_result = await run_incident_correlation(session)

    return {
        "assets_synced": assets_synced,
        "ingestion": ingestion_results,
        "detections": detection_result,
        "incidents": incident_result,
    }


@pytest.fixture
def sentinel_session():
    from domain.db import SessionLocal

    return SessionLocal


async def test_no_ai_pipeline_end_to_end_detects_critical_asset_degradation(sentinel_session):
    async with await _missionnet_client() as mn:
        health = (await mn.get("/health")).json()
        assert health["status"] == "nominal"

        degrade = await mn.post(
            "/lab/state/mission-data-api-01/degrade",
            headers=LAB_HEADERS,
            json={"reason": "phase2 e2e test"},
        )
        assert degrade.status_code == 200

    result = await _run_full_pipeline(sentinel_session)
    assert result["detections"].detections_created >= 1
    assert result["incidents"].incidents_created >= 1

    transport = ASGITransport(app=sentinel_app)
    async with AsyncClient(transport=transport, base_url="http://test") as api:
        incidents = (await api.get("/api/v1/incidents")).json()
        assert len(incidents) >= 1
        incident = next(i for i in incidents if i["primary_asset_id"] == "mission-data-api-01")
        assert incident["severity"] == "high"
        assert incident["category"] == "asset-degradation"

        detail = (await api.get(f"/api/v1/incidents/{incident['incident_id']}")).json()
        assert len(detail["event_ids"]) >= 1
        # Evidence must trace back to a real, fetchable normalized event.
        evidence_event = (await api.get(f"/api/v1/events/{detail['event_ids'][0]}")).json()
        assert evidence_event["source"] == "missionnet"
        assert evidence_event["asset_id"] == "mission-data-api-01"


async def test_repeated_ingestion_is_idempotent_no_duplicate_events_or_detections(sentinel_session):
    async with await _missionnet_client() as mn:
        for _ in range(3):
            await mn.post(
                "/identity/login", json={"username": "j.rivera", "password": "wrong"}
            )

    first_run = await _run_full_pipeline(sentinel_session)
    assert first_run["detections"].detections_created == 1  # DET-001 fires once

    second_run = await _run_full_pipeline(sentinel_session)
    assert second_run["ingestion"][0].ingested == 0  # no new audit events to ingest
    assert second_run["detections"].detections_created == 0
    assert second_run["incidents"].incidents_created == 0
    assert second_run["incidents"].incidents_updated == 0

    transport = ASGITransport(app=sentinel_app)
    async with AsyncClient(transport=transport, base_url="http://test") as api:
        events = (await api.get("/api/v1/events")).json()
        event_ids = [e["event_id"] for e in events]
        assert len(event_ids) == len(set(event_ids)), "duplicate normalized events were ingested"


async def test_benign_activity_creates_no_high_severity_incident(sentinel_session):
    """A single normal login should not trip any detection rule - proves the engine isn't
    trigger-happy on ordinary MissionNet activity."""
    async with await _missionnet_client() as mn:
        resp = await mn.post(
            "/identity/login", json={"username": "j.rivera", "password": "SynthLab#2026"}
        )
        assert resp.json()["success"] is True

    result = await _run_full_pipeline(sentinel_session)
    assert result["detections"].detections_created == 0
    assert result["incidents"].incidents_created == 0


async def test_multi_signal_correlation_merges_into_one_incident(sentinel_session):
    async with await _missionnet_client() as mn:
        await mn.post(
            "/lab/state/telemetry-gateway-02/degrade", headers=LAB_HEADERS, json={"reason": "e2e"}
        )
        await mn.post(
            "/lab/telemetry/telemetry-gateway-02/inject",
            headers=LAB_HEADERS,
            json={"battery": 5, "link_quality": 10},
        )

    result = await _run_full_pipeline(sentinel_session)
    assert result["incidents"].incidents_created == 1

    transport = ASGITransport(app=sentinel_app)
    async with AsyncClient(transport=transport, base_url="http://test") as api:
        incidents = (await api.get("/api/v1/incidents")).json()
        incident = next(i for i in incidents if i["primary_asset_id"] == "telemetry-gateway-02")
        assert len(incident["detection_ids"]) >= 2  # degrade + telemetry + multi-signal rules


async def test_reset_lab_and_sentinel_reset_reproduce_identical_result(sentinel_session):
    """Steps 1 and 14 of the Phase 2 end-state: reset, reproduce the same detection outcome."""
    scenario_asset = "mission-data-api-01"

    async def trigger_and_ingest() -> dict:
        async with await _missionnet_client() as mn:
            await mn.post(
                f"/lab/state/{scenario_asset}/degrade",
                headers=LAB_HEADERS,
                json={"reason": str(uuid.uuid4())},
            )
        return await _run_full_pipeline(sentinel_session)

    first = await trigger_and_ingest()
    assert first["detections"].detections_created == 1
    assert first["incidents"].incidents_created == 1

    await reset_missionnet()
    await reset_sentinel()

    second = await trigger_and_ingest()
    assert second["detections"].detections_created == 1
    assert second["incidents"].incidents_created == 1
