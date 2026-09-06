"""Unit tests for the verification engine using a mocked Sentinel HTTP client (httpx.MockTransport)
- no live Postgres/MissionNet/Sentinel required. Proves the pass/fail logic itself is correct,
independent of any real deployment.
"""

from datetime import UTC, datetime

import httpx

from apps.demo_control.scenarios import load_scenario
from apps.demo_control.verification import Baseline, capture_baseline, verify_scenario_result


def _sentinel_client(handler) -> httpx.AsyncClient:
    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(transport=transport, base_url="http://sentinel.test")


async def test_capture_baseline_reads_existing_ids():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/detections":
            return httpx.Response(200, json=[{"detection_id": "DET-old"}])
        if request.url.path == "/api/v1/incidents":
            return httpx.Response(200, json=[{"incident_id": "INC-old"}])
        raise AssertionError(f"unexpected request: {request.url}")

    async with _sentinel_client(handler) as client:
        baseline = await capture_baseline(client)
    assert baseline.detection_ids == {"DET-old"}
    assert baseline.incident_ids == {"INC-old"}


async def test_verify_fails_when_expected_detection_missing():
    scenario = load_scenario("SCN-003")  # expects DET-002
    baseline = Baseline(detection_ids=set(), incident_ids=set(), captured_at=datetime.now(UTC))

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/events":
            return httpx.Response(200, json=[{"event_id": "evt-1"}])
        if request.url.path == "/api/v1/detections":
            return httpx.Response(200, json=[{"detection_id": "DET-x", "rule_id": "DET-999"}])
        if request.url.path == "/api/v1/incidents":
            return httpx.Response(200, json=[])
        if request.url.path == "/api/v1/ingest/run":
            return httpx.Response(200, json={"detections_created": 0, "incidents_created": 0})
        raise AssertionError(f"unexpected request: {request.url}")

    async with _sentinel_client(handler) as client:
        result = await verify_scenario_result(client, scenario, baseline, datetime.now(UTC))

    assert result.checks["expected_detection_observed"] is False
    assert result.checks["incident_created"] is False
    assert not result.all_passed


async def test_verify_passes_when_everything_matches():
    scenario = load_scenario("SCN-003")
    baseline = Baseline(detection_ids=set(), incident_ids=set(), captured_at=datetime.now(UTC))

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/events":
            return httpx.Response(200, json=[{"event_id": "evt-1"}])
        if request.url.path == "/api/v1/detections":
            return httpx.Response(
                200, json=[{"detection_id": "DET-x", "rule_id": "DET-002"}]
            )
        if request.url.path == "/api/v1/incidents":
            return httpx.Response(
                200,
                json=[
                    {
                        "incident_id": "INC-x",
                        "primary_asset_id": "mission-data-api-01",
                    }
                ],
            )
        if request.url.path == "/api/v1/incidents/INC-x":
            return httpx.Response(200, json={"event_ids": ["evt-1"]})
        if request.url.path == "/api/v1/ingest/run":
            return httpx.Response(200, json={"detections_created": 0, "incidents_created": 0})
        raise AssertionError(f"unexpected request: {request.url}")

    async with _sentinel_client(handler) as client:
        result = await verify_scenario_result(client, scenario, baseline, datetime.now(UTC))

    result.checks["missionnet_event_observed"] = True  # set by the runner in real usage
    assert result.all_passed


async def test_verify_fails_incident_created_when_wrong_primary_asset():
    scenario = load_scenario("SCN-003")  # expects primary_asset_id=mission-data-api-01
    baseline = Baseline(detection_ids=set(), incident_ids=set(), captured_at=datetime.now(UTC))

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/events":
            return httpx.Response(200, json=[{"event_id": "evt-1"}])
        if request.url.path == "/api/v1/detections":
            return httpx.Response(200, json=[{"detection_id": "DET-x", "rule_id": "DET-002"}])
        if request.url.path == "/api/v1/incidents":
            return httpx.Response(
                200, json=[{"incident_id": "INC-x", "primary_asset_id": "some-other-asset"}]
            )
        if request.url.path == "/api/v1/incidents/INC-x":
            return httpx.Response(200, json={"event_ids": ["evt-1"]})
        if request.url.path == "/api/v1/ingest/run":
            return httpx.Response(200, json={"detections_created": 0, "incidents_created": 0})
        raise AssertionError(f"unexpected request: {request.url}")

    async with _sentinel_client(handler) as client:
        result = await verify_scenario_result(client, scenario, baseline, datetime.now(UTC))

    assert result.checks["incident_created"] is False


async def test_verify_fails_duplicate_check_when_replay_creates_new_records():
    scenario = load_scenario("SCN-003")
    baseline = Baseline(detection_ids=set(), incident_ids=set(), captured_at=datetime.now(UTC))

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/events":
            return httpx.Response(200, json=[{"event_id": "evt-1"}])
        if request.url.path == "/api/v1/detections":
            return httpx.Response(200, json=[{"detection_id": "DET-x", "rule_id": "DET-002"}])
        if request.url.path == "/api/v1/incidents":
            return httpx.Response(
                200, json=[{"incident_id": "INC-x", "primary_asset_id": "mission-data-api-01"}]
            )
        if request.url.path == "/api/v1/incidents/INC-x":
            return httpx.Response(200, json={"event_ids": ["evt-1"]})
        if request.url.path == "/api/v1/ingest/run":
            return httpx.Response(200, json={"detections_created": 1, "incidents_created": 0})
        raise AssertionError(f"unexpected request: {request.url}")

    async with _sentinel_client(handler) as client:
        result = await verify_scenario_result(client, scenario, baseline, datetime.now(UTC))

    assert result.checks["no_duplicate_on_replay"] is False


async def test_baseline_ids_are_excluded_from_new_detections_and_incidents():
    scenario = load_scenario("SCN-003")
    baseline = Baseline(
        detection_ids={"DET-old"}, incident_ids={"INC-old"}, captured_at=datetime.now(UTC)
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/events":
            return httpx.Response(200, json=[])
        if request.url.path == "/api/v1/detections":
            return httpx.Response(
                200,
                json=[
                    {"detection_id": "DET-old", "rule_id": "DET-002"},
                    {"detection_id": "DET-new", "rule_id": "DET-002"},
                ],
            )
        if request.url.path == "/api/v1/incidents":
            return httpx.Response(
                200,
                json=[
                    {"incident_id": "INC-old", "primary_asset_id": "mission-data-api-01"},
                    {"incident_id": "INC-new", "primary_asset_id": "mission-data-api-01"},
                ],
            )
        if request.url.path == "/api/v1/incidents/INC-new":
            return httpx.Response(200, json={"event_ids": ["evt-1"]})
        if request.url.path == "/api/v1/ingest/run":
            return httpx.Response(200, json={"detections_created": 0, "incidents_created": 0})
        raise AssertionError(f"unexpected request: {request.url}")

    async with _sentinel_client(handler) as client:
        result = await verify_scenario_result(client, scenario, baseline, datetime.now(UTC))

    assert result.detection_ids == ["DET-new"]
    assert result.incident_ids == ["INC-new"]
