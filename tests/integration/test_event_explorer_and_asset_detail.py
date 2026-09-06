"""Phase 4: Event Explorer filters/pagination, event detail enrichment (raw payload + linked
detections/incidents), and Asset Detail enrichment (active counts, recent activity).
"""

import asyncio

import httpx
import pytest

from apps.missionnet.seed import reset_and_seed as reset_missionnet
from services.event_ingestor.reset import reset as reset_sentinel

pytestmark = pytest.mark.integration

SENTINEL_BASE_URL = "http://127.0.0.1:8080"
DEMO_CONTROL_BASE_URL = "http://127.0.0.1:8100"
TERMINAL_RUN_STATES = {"PASSED", "FAILED", "CANCELLED"}


@pytest.fixture(autouse=True)
async def _reset_everything():
    await reset_missionnet()
    await reset_sentinel()
    yield
    await reset_missionnet()
    await reset_sentinel()


async def _sentinel_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=SENTINEL_BASE_URL, timeout=15.0)


async def _run_scenario(scenario_id: str) -> dict:
    async with httpx.AsyncClient(base_url=DEMO_CONTROL_BASE_URL, timeout=15.0) as dc:
        resp = await dc.post(f"/api/v1/scenarios/{scenario_id}/run", json={})
        run_id = resp.json()["run_id"]
        deadline = asyncio.get_event_loop().time() + 30.0
        while True:
            run = (await dc.get(f"/api/v1/runs/{run_id}")).json()
            if run["status"] in TERMINAL_RUN_STATES:
                return run
            if asyncio.get_event_loop().time() >= deadline:
                raise AssertionError(f"run did not finish in time: {run}")
            await asyncio.sleep(0.5)


async def test_event_explorer_filters_by_scenario_and_category():
    run = await _run_scenario("SCN-003")
    assert run["status"] == "PASSED"

    async with await _sentinel_client() as sentinel:
        by_scenario = (
            await sentinel.get("/api/v1/events", params={"scenario_id": "SCN-003"})
        ).json()
        by_category = (
            await sentinel.get("/api/v1/events", params={"event_category": "application"})
        ).json()
        by_bogus_scenario = (
            await sentinel.get("/api/v1/events", params={"scenario_id": "SCN-999"})
        ).json()

    assert len(by_scenario) >= 1
    assert all(e["scenario_id"] == "SCN-003" for e in by_scenario)
    assert all(e["event_category"] == "application" for e in by_category)
    assert by_bogus_scenario == []


async def test_event_explorer_pagination():
    run = await _run_scenario("SCN-010")
    assert run["status"] == "PASSED"

    async with await _sentinel_client() as sentinel:
        page1 = (await sentinel.get("/api/v1/events", params={"limit": 3, "offset": 0})).json()
        page2 = (await sentinel.get("/api/v1/events", params={"limit": 3, "offset": 3})).json()

    assert len(page1) == 3
    page1_ids = {e["event_id"] for e in page1}
    page2_ids = {e["event_id"] for e in page2}
    assert page1_ids.isdisjoint(page2_ids)


async def test_event_detail_exposes_raw_payload_and_links():
    run = await _run_scenario("SCN-003")
    assert run["status"] == "PASSED"

    async with await _sentinel_client() as sentinel:
        events = (await sentinel.get("/api/v1/events")).json()
        event_id = events[0]["event_id"]
        detail = (await sentinel.get(f"/api/v1/events/{event_id}")).json()

    assert detail["raw_payload"], "raw_payload should be populated, not empty"
    assert detail["raw_sha256"]
    assert isinstance(detail["detection_ids"], list)
    assert isinstance(detail["incident_ids"], list)


async def test_event_detail_404_for_unknown_event():
    async with await _sentinel_client() as sentinel:
        resp = await sentinel.get("/api/v1/events/not-a-real-event")
    assert resp.status_code == 404


async def test_asset_detail_reflects_active_incident_and_detection_counts():
    run = await _run_scenario("SCN-003")
    assert run["status"] == "PASSED"

    async with await _sentinel_client() as sentinel:
        detail = (await sentinel.get("/api/v1/assets/missionnet:mission-data-api-01")).json()

    assert detail["active_incident_count"] >= 1
    assert detail["active_detection_count"] >= 1
    assert len(detail["recent_events"]) >= 1
    assert detail["vulnerability_posture"] == "NOT YET INTEGRATED"


async def test_asset_detail_404_for_unknown_asset():
    async with await _sentinel_client() as sentinel:
        resp = await sentinel.get("/api/v1/assets/missionnet:not-a-real-asset")
    assert resp.status_code == 404


async def test_asset_list_filters_by_criticality():
    async with await _sentinel_client() as sentinel:
        # Sync assets first via an ingestion cycle so the assets table is populated.
        await sentinel.post("/api/v1/ingest/run")
        critical = (await sentinel.get("/api/v1/assets", params={"criticality": 5})).json()

    assert all(a["criticality"] == 5 for a in critical)
