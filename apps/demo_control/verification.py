"""Derive scenario PASS/FAIL from Sentinel's real read APIs.

Every check here is backed by observed Sentinel evidence. Upstream HTTP handling is centralized so
an empty/non-JSON cloud response becomes a classified integration failure rather than a raw JSON
decoder exception shown to the operator.
"""

from dataclasses import dataclass, field
from datetime import datetime

import httpx

from apps.demo_control.http_client import request_json
from apps.demo_control.scenarios import ScenarioDefinition


@dataclass
class Baseline:
    detection_ids: set[str]
    incident_ids: set[str]
    captured_at: datetime


@dataclass
class VerificationResult:
    checks: dict[str, bool] = field(default_factory=dict)
    sentinel_event_ids: list[str] = field(default_factory=list)
    detection_ids: list[str] = field(default_factory=list)
    incident_ids: list[str] = field(default_factory=list)
    detail: dict = field(default_factory=dict)

    @property
    def all_passed(self) -> bool:
        return bool(self.checks) and all(self.checks.values())


async def capture_baseline(sentinel: httpx.AsyncClient) -> Baseline:
    detections = await request_json(
        sentinel,
        "GET",
        "/api/v1/detections",
        component="Sentinel API",
        retry_safe=True,
        expected_type=list,
        params={"limit": 500},
    )
    incidents = await request_json(
        sentinel,
        "GET",
        "/api/v1/incidents",
        component="Sentinel API",
        retry_safe=True,
        expected_type=list,
        params={"limit": 500},
    )
    return Baseline(
        detection_ids={d["detection_id"] for d in detections},
        incident_ids={i["incident_id"] for i in incidents},
        captured_at=datetime.now().astimezone(),
    )


async def verify_scenario_result(
    sentinel: httpx.AsyncClient,
    scenario: ScenarioDefinition,
    baseline: Baseline,
    run_started_at: datetime,
) -> VerificationResult:
    result = VerificationResult()

    events = await request_json(
        sentinel,
        "GET",
        "/api/v1/events",
        component="Sentinel API",
        retry_safe=True,
        expected_type=list,
        params={"since": run_started_at.isoformat(), "limit": 500},
    )
    result.sentinel_event_ids = [e["event_id"] for e in events]
    result.checks["normalized_event_observed"] = len(result.sentinel_event_ids) > 0

    all_detections = await request_json(
        sentinel,
        "GET",
        "/api/v1/detections",
        component="Sentinel API",
        retry_safe=True,
        expected_type=list,
        params={"limit": 500},
    )
    new_detections = [d for d in all_detections if d["detection_id"] not in baseline.detection_ids]
    result.detection_ids = [d["detection_id"] for d in new_detections]
    observed_rule_ids = {d["rule_id"] for d in new_detections}
    expected_rule_ids = {d.rule_id for d in scenario.expected_observations.sentinel.detections}
    missing_rules = expected_rule_ids - observed_rule_ids
    result.checks["expected_detection_observed"] = not missing_rules
    result.detail["missing_detection_rules"] = sorted(missing_rules)
    result.detail["observed_detection_rules"] = sorted(observed_rule_ids)

    all_incidents = await request_json(
        sentinel,
        "GET",
        "/api/v1/incidents",
        component="Sentinel API",
        retry_safe=True,
        expected_type=list,
        params={"limit": 500},
    )
    new_incidents = [i for i in all_incidents if i["incident_id"] not in baseline.incident_ids]
    result.incident_ids = [i["incident_id"] for i in new_incidents]
    expected_incidents = scenario.expected_observations.sentinel.incidents
    incident_count_ok = len(new_incidents) >= expected_incidents.min_count
    incident_asset_ok = True
    if expected_incidents.primary_asset_id:
        incident_asset_ok = any(
            i["primary_asset_id"] == expected_incidents.primary_asset_id for i in new_incidents
        )
    result.checks["incident_created"] = incident_count_ok and incident_asset_ok
    result.detail["new_incident_count"] = len(new_incidents)

    evidence_ok = len(new_incidents) > 0
    for incident in new_incidents:
        detail = await request_json(
            sentinel,
            "GET",
            f"/api/v1/incidents/{incident['incident_id']}",
            component="Sentinel API",
            retry_safe=True,
            expected_type=dict,
        )
        if not detail.get("event_ids"):
            evidence_ok = False
    result.checks["evidence_link_verified"] = evidence_ok

    # Sentinel ingestion is designed to be idempotent; a bounded retry is safe here and the result
    # itself proves whether replay created any duplicate detections/incidents.
    replay = await request_json(
        sentinel,
        "POST",
        "/api/v1/ingest/run",
        component="Sentinel API",
        retry_safe=True,
        expected_type=dict,
    )
    result.checks["no_duplicate_on_replay"] = (
        replay["detections_created"] == 0 and replay["incidents_created"] == 0
    )
    result.detail["replay_result"] = replay

    result.checks.setdefault("missionnet_event_observed", False)
    return result
