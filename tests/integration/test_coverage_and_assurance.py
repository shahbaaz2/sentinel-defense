"""Phase 4: Detection Coverage (real rules + real validation status from Demo Control's run
history) and System Assurance (truthful online/offline reporting, no fabricated integrations).
"""

import asyncio

import httpx
import pytest

from apps.demo_control.reset import reset as reset_demo_control
from apps.missionnet.seed import reset_and_seed as reset_missionnet
from services.event_ingestor.reset import reset as reset_sentinel

pytestmark = pytest.mark.integration

SENTINEL_BASE_URL = "http://127.0.0.1:8080"
DEMO_CONTROL_BASE_URL = "http://127.0.0.1:8100"
TERMINAL_RUN_STATES = {"PASSED", "FAILED", "CANCELLED"}
ALL_RULE_IDS = {"DET-001", "DET-002", "DET-003", "DET-004", "DET-005", "DET-006"}


@pytest.fixture(autouse=True)
async def _reset_everything():
    # Detection Coverage's validation status is derived from Demo Control's *entire* run history
    # (see apps/api/coverage_routes.py), so these tests must also reset that history, not just
    # MissionNet/Sentinel - otherwise a PASSED run from an earlier test (or manual testing) leaks
    # into "has this rule ever been validated" for every test that runs afterward.
    await reset_missionnet()
    await reset_sentinel()
    await reset_demo_control()
    yield
    await reset_missionnet()
    await reset_sentinel()
    await reset_demo_control()


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


async def test_coverage_lists_all_six_rules_with_no_fabricated_percentages():
    async with await _sentinel_client() as sentinel:
        coverage = (await sentinel.get("/api/v1/detection-coverage")).json()

    assert {r["rule_id"] for r in coverage} == ALL_RULE_IDS
    for rule in coverage:
        assert rule["validation_status"] in ("VALIDATED", "FAILED", "NOT_TESTED")
        assert isinstance(rule["total_detections"], int)
        assert isinstance(rule["validating_scenarios"], list)


async def test_coverage_shows_not_tested_before_any_run():
    async with await _sentinel_client() as sentinel:
        coverage = (await sentinel.get("/api/v1/detection-coverage")).json()
    by_id = {r["rule_id"]: r for r in coverage}
    assert by_id["DET-002"]["validation_status"] == "NOT_TESTED"
    assert by_id["DET-002"]["total_detections"] == 0
    assert by_id["DET-002"]["last_triggered"] is None


async def test_coverage_shows_validated_after_a_passing_scenario_run():
    run = await _run_scenario("SCN-003")
    assert run["status"] == "PASSED"

    async with await _sentinel_client() as sentinel:
        coverage = (await sentinel.get("/api/v1/detection-coverage")).json()
    by_id = {r["rule_id"]: r for r in coverage}

    assert by_id["DET-002"]["validation_status"] == "VALIDATED"
    assert by_id["DET-002"]["total_detections"] == 1
    assert by_id["DET-002"]["last_triggered"] is not None
    # SCN-003 doesn't touch DET-001 - it must not be reported VALIDATED by association.
    assert by_id["DET-001"]["validation_status"] == "NOT_TESTED"


async def test_coverage_scenario_mapping_matches_shipped_scn_to_det_assignments():
    """Locks in the DECISIONS.md-documented mapping so a future rule rename doesn't silently
    desync the scenario YAMLs from the real catalog without a test noticing."""
    async with await _sentinel_client() as sentinel:
        coverage = (await sentinel.get("/api/v1/detection-coverage")).json()
    by_id = {r["rule_id"]: r for r in coverage}

    assert "SCN-001" in by_id["DET-001"]["validating_scenarios"]
    assert "SCN-002" in by_id["DET-006"]["validating_scenarios"]
    assert "SCN-003" in by_id["DET-002"]["validating_scenarios"]
    assert "SCN-004" in by_id["DET-003"]["validating_scenarios"]
    assert "SCN-010" in by_id["DET-005"]["validating_scenarios"]


async def test_assurance_reports_truthful_state_no_fake_certifications():
    async with await _sentinel_client() as sentinel:
        assurance = (await sentinel.get("/api/v1/system/assurance")).json()

    assert assurance["external_ai_api"] == "DISABLED"
    assert assurance["ai_analyst_status"] == "NOT ENABLED"
    assert assurance["local_llm_runtime"] == "NOT ENABLED"
    assert assurance["missionnet_adapter"] == "ONLINE"
    assert assurance["sentinel_api"] == "ONLINE"
    assert assurance["postgresql"] == "ONLINE"
    assert assurance["demo_control"] == "ONLINE"
    integrations = assurance["integrations"]
    assert integrations["missionnet"] == "ACTIVE"
    for name in ("wazuh", "splunk", "suricata", "zeek", "falco"):
        assert integrations[name] == "NOT_CONFIGURED"
    body_text = str(assurance).lower()
    for forbidden in ("dod approved", "cmmc certified", "fedramp", "classified-ready"):
        assert forbidden not in body_text
