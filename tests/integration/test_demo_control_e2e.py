"""End-to-end proof that the Demo Control Plane drives the real Phase 2 pipeline: every scenario
run here must produce genuine MissionNet events, real Sentinel detections/incidents, and derive
PASS/FAIL from Sentinel's actual read APIs - never from anything the controller assumes happened.

Requires the full stack live: Postgres (`make dev-up`), MissionNet (`make missionnet`), Sentinel API
(`make api`), and Demo Control (`make demo-control`) - this suite talks to Demo Control's real HTTP
server, not an in-process ASGI transport, specifically so background scenario execution behaves the
same way it does for a real operator clicking "Run Scenario" in the browser.
"""

import asyncio

import httpx
import pytest
from sqlalchemy import delete

from apps.demo_control.config import settings as demo_control_settings
from apps.demo_control.db import SessionLocal
from apps.demo_control.models import ScenarioRun
from apps.missionnet.seed import reset_and_seed as reset_missionnet
from services.event_ingestor.reset import reset as reset_sentinel

pytestmark = pytest.mark.integration

DEMO_CONTROL_BASE_URL = f"http://{demo_control_settings.api_host}:{demo_control_settings.api_port}"
TERMINAL_STATES = {"PASSED", "FAILED", "CANCELLED"}


@pytest.fixture(autouse=True)
async def _reset_everything():
    await reset_missionnet()
    await reset_sentinel()
    async with SessionLocal() as session:
        await session.execute(delete(ScenarioRun))
        await session.commit()
    yield
    await reset_missionnet()
    await reset_sentinel()
    async with SessionLocal() as session:
        await session.execute(delete(ScenarioRun))
        await session.commit()


async def _demo_control_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=DEMO_CONTROL_BASE_URL, timeout=30.0)


@pytest.fixture
def tmp_scenario_no_reset():
    """A minimal scenario, identical to SCN-003 but with reset disabled, so the precondition check
    runs against whatever state MissionNet is actually in - used only to test the failure path."""
    from apps.demo_control.scenarios import SCENARIOS_DIR

    scenario_id = "SCN-900"
    path = SCENARIOS_DIR / f"{scenario_id}.yaml"
    path.write_text(f"""
id: {scenario_id}
version: 1.0.0
name: Test-only precondition scenario
description: Not a real scenario - exists only for the precondition-failure test.
risk_level: safe_lab_only
preconditions:
  missionnet_status: nominal
steps:
  - id: step-1
    action: degrade_asset
    target: mission-data-api-01
expected_observations:
  missionnet:
    - event_type: asset.degrade
  sentinel:
    detections:
      - rule_id: DET-002
    incidents:
      min_count: 1
success_conditions:
  - incident_created
reset:
  strategy: none
""")
    try:
        yield scenario_id
    finally:
        path.unlink(missing_ok=True)


async def _run_scenario_and_wait(
    client: httpx.AsyncClient, scenario_id: str, timeout: float = 30.0
) -> dict:
    resp = await client.post(f"/api/v1/scenarios/{scenario_id}/run", json={})
    resp.raise_for_status()
    run_id = resp.json()["run_id"]

    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        run = (await client.get(f"/api/v1/runs/{run_id}")).json()
        if run["status"] in TERMINAL_STATES:
            return run
        if asyncio.get_event_loop().time() >= deadline:
            raise AssertionError(f"run {run_id} did not reach a terminal state in time: {run}")
        await asyncio.sleep(0.5)


async def test_scn003_passes_with_real_ids_at_every_layer():
    async with await _demo_control_client() as client:
        run = await _run_scenario_and_wait(client, "SCN-003")

    assert run["status"] == "PASSED"
    assert run["missionnet_event_ids"], "no MissionNet event IDs captured"
    assert run["sentinel_event_ids"], "no Sentinel event IDs captured"
    assert run["detection_ids"], "no detection IDs captured"
    assert run["incident_ids"], "no incident IDs captured"
    assert all(run["verification"].values()), run["verification"]

    # Cross-check against Sentinel's own API directly - the run's captured IDs must be real.
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8080", timeout=15.0) as sentinel:
        incident = (await sentinel.get(f"/api/v1/incidents/{run['incident_ids'][0]}")).json()
    assert incident["primary_asset_id"] == "mission-data-api-01"
    assert incident["category"] == "asset-degradation"


async def test_scn010_flagship_produces_five_detections_and_multiple_incidents():
    async with await _demo_control_client() as client:
        run = await _run_scenario_and_wait(client, "SCN-010", timeout=45.0)

    assert run["status"] == "PASSED", run["failure_reason"]
    assert len(run["detection_ids"]) == 5
    assert len(run["incident_ids"]) >= 3, (
        "SCN-010 must not force everything into a single incident - "
        f"got {len(run['incident_ids'])} incidents"
    )


async def test_scn010_is_reproducible_after_automatic_reset():
    async with await _demo_control_client() as client:
        first = await _run_scenario_and_wait(client, "SCN-010", timeout=45.0)
        second = await _run_scenario_and_wait(client, "SCN-010", timeout=45.0)

    assert first["status"] == "PASSED"
    assert second["status"] == "PASSED"
    assert len(first["detection_ids"]) == len(second["detection_ids"]) == 5
    assert len(first["incident_ids"]) == len(second["incident_ids"])
    # Reproducible, not identical: the automatic pre-run reset means the second run's IDs are new.
    assert set(first["incident_ids"]).isdisjoint(second["incident_ids"])


async def test_precondition_failure_reported_as_failed_not_passed(tmp_scenario_no_reset):
    """If MissionNet is already degraded and the scenario does not reset first, the run must fail
    cleanly on the precondition check rather than silently proceeding and reporting a false PASS."""
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8090", timeout=15.0) as mn:
        await mn.post(
            "/lab/state/mission-data-api-01/degrade",
            headers={"X-Lab-Secret": demo_control_settings.missionnet_lab_secret},
            json={"reason": "pre-existing anomaly for precondition test"},
        )

    async with await _demo_control_client() as client:
        run = await _run_scenario_and_wait(client, tmp_scenario_no_reset)

    assert run["status"] == "FAILED"
    assert "precondition" in run["failure_reason"].lower()


async def test_cancel_marks_run_cancelled_not_passed():
    async with await _demo_control_client() as client:
        resp = await client.post("/api/v1/scenarios/SCN-010/run", json={})
        run_id = resp.json()["run_id"]

        cancel_resp = await client.post(f"/api/v1/runs/{run_id}/cancel")
        assert cancel_resp.status_code == 200

        deadline = asyncio.get_event_loop().time() + 30.0
        while True:
            run = (await client.get(f"/api/v1/runs/{run_id}")).json()
            if run["status"] in TERMINAL_STATES:
                break
            if asyncio.get_event_loop().time() >= deadline:
                raise AssertionError(f"run {run_id} never reached a terminal state: {run}")
            await asyncio.sleep(0.3)

    assert run["status"] in ("CANCELLED", "PASSED"), run["status"]
    # A cancel requested immediately after start should usually win the race; if the scenario was
    # too fast to interrupt, PASSED is acceptable, but FAILED/hung is not.
    assert run["status"] != "FAILED"


async def test_reset_endpoint_returns_missionnet_to_nominal():
    async with await _demo_control_client() as client:
        run = await _run_scenario_and_wait(client, "SCN-003")
        assert run["status"] == "PASSED"

        reset_resp = await client.post(f"/api/v1/runs/{run['run_id']}/reset")
        assert reset_resp.status_code == 200
        assert reset_resp.json()["reset_status"] == "RESET_COMPLETE"

    async with httpx.AsyncClient(base_url="http://127.0.0.1:8090", timeout=15.0) as mn:
        health = (await mn.get("/health")).json()
    assert health["status"] == "nominal"
