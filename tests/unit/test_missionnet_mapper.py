from datetime import UTC, datetime

import pytest

from integrations.missionnet.mapper import UnmappedEventTypeError, normalize_missionnet_event
from services.event_ingestor.ports import RawSourceEvent


def _audit_raw(**overrides) -> RawSourceEvent:
    payload = {
        "audit_id": "aud-1",
        "timestamp": "2026-09-06T18:00:00+00:00",
        "actor_type": "scenario_controller",
        "actor_id": "SCN-TEST",
        "action": "asset.degrade",
        "object_type": "asset",
        "object_id": "telemetry-gateway-02",
        "detail": {"reason": "test"},
        "severity": "medium",
        "scenario_id": "SCN-TEST",
        "classification": "SYNTHETIC",
    }
    payload.update(overrides)
    return RawSourceEvent(
        source="missionnet",
        source_event_id=payload["audit_id"],
        stream="audit",
        occurred_at=datetime.fromisoformat(payload["timestamp"]),
        payload=payload,
    )


def _telemetry_raw(**overrides) -> RawSourceEvent:
    payload = {
        "sample_id": "sample-1",
        "asset_id": "sim-uav-017",
        "battery": 90,
        "link_quality": 95,
        "latitude": None,
        "longitude": None,
        "generated_at": "2026-09-06T18:00:00+00:00",
        "classification": "SYNTHETIC",
    }
    payload.update(overrides)
    return RawSourceEvent(
        source="missionnet",
        source_event_id=payload["sample_id"],
        stream="telemetry",
        occurred_at=datetime.fromisoformat(payload["generated_at"]),
        payload=payload,
    )


def test_asset_degrade_maps_to_application_category_with_asset_id():
    event = normalize_missionnet_event(_audit_raw())
    assert event["event_id"] == "missionnet-audit-aud-1"
    assert event["event_category"] == "application"
    assert event["event_type"] == "asset.degrade"
    assert event["asset_id"] == "telemetry-gateway-02"
    assert event["user_id"] is None
    assert event["severity"] == "medium"
    assert event["scenario_id"] == "SCN-TEST"
    assert event["correlation_key"] == "telemetry-gateway-02"


def test_token_revoke_extracts_owner_user_id_from_detail_not_actor():
    event = normalize_missionnet_event(
        _audit_raw(
            action="token.revoke",
            object_type="service_token",
            object_id="tok-svc-telemetry-01",
            actor_id="lab_control",
            detail={"reason": "compromise suspected", "owner_user_id": "svc-telemetry-01"},
            severity="high",
        )
    )
    assert event["event_category"] == "identity"
    assert event["asset_id"] is None
    assert event["user_id"] == "svc-telemetry-01"
    assert event["severity"] == "high"


def test_auth_failure_maps_identity_category_with_low_severity():
    event = normalize_missionnet_event(
        _audit_raw(
            action="auth.failure",
            object_type="identity_user",
            object_id="u-operator-01",
            actor_id="u-operator-01",
            actor_type="human",
            detail={},
            severity="low",
        )
    )
    assert event["event_category"] == "identity"
    assert event["event_type"] == "auth.failure"
    assert event["user_id"] == "u-operator-01"
    assert event["severity"] == "low"


def test_record_access_uses_actor_id_as_user_id():
    event = normalize_missionnet_event(
        _audit_raw(
            action="record.access",
            object_type="mission_record",
            object_id="rec-000",
            actor_id="u-analyst-01",
            actor_type="human",
            detail={},
            severity="info",
        )
    )
    assert event["event_category"] == "application"
    assert event["user_id"] == "u-analyst-01"
    assert event["asset_id"] is None


def test_unknown_audit_action_raises():
    with pytest.raises(UnmappedEventTypeError):
        normalize_missionnet_event(_audit_raw(action="something.new"))


def test_invalid_source_severity_falls_back_to_info():
    event = normalize_missionnet_event(_audit_raw(severity="not-a-real-severity"))
    assert event["severity"] == "info"


def test_telemetry_normal_reading_is_info_severity():
    event = normalize_missionnet_event(_telemetry_raw())
    assert event["event_id"] == "missionnet-telemetry-sample-1"
    assert event["event_category"] == "runtime"
    assert event["asset_id"] == "sim-uav-017"
    assert event["severity"] == "info"


@pytest.mark.parametrize(
    "battery,link_quality,expected",
    [
        (10, 95, "high"),
        (90, 15, "high"),
        (25, 95, "medium"),
        (90, 35, "medium"),
        (90, 95, "info"),
    ],
)
def test_telemetry_severity_thresholds(battery, link_quality, expected):
    event = normalize_missionnet_event(_telemetry_raw(battery=battery, link_quality=link_quality))
    assert event["severity"] == expected


def test_unknown_stream_raises():
    raw = RawSourceEvent(
        source="missionnet",
        source_event_id="x",
        stream="not-a-real-stream",
        occurred_at=datetime.now(UTC),
        payload={},
    )
    with pytest.raises(UnmappedEventTypeError):
        normalize_missionnet_event(raw)
