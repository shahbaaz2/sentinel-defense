from datetime import UTC, datetime

import pytest

from integrations.suricata.mapper import UnmappedEventTypeError, normalize_suricata_event
from services.event_ingestor.ports import RawSourceEvent


def _alert_raw(**overrides) -> dict:
    payload = {
        "timestamp": "2026-09-07T02:52:36.517816+0000",
        "flow_id": 1377792597106738,
        "event_type": "alert",
        "src_ip": "172.28.0.3",
        "src_port": 47032,
        "dest_ip": "172.28.0.10",
        "dest_port": 80,
        "proto": "TCP",
        "alert": {
            "action": "allowed",
            "gid": 1,
            "signature_id": 1000001,
            "rev": 1,
            "signature": "SENTINEL LAB Suspicious Command-Injection-style URI",
            "category": "Web Application Attack",
            "severity": 1,
        },
        "http": {
            "hostname": "172.28.0.10",
            "url": "/index.html?cmd=cat%20/etc/passwd",
            "http_user_agent": "SentinelLabClient/1.0",
            "http_method": "GET",
            "status": 404,
        },
    }
    payload.update(overrides)
    return payload


def _raw_event(payload: dict) -> RawSourceEvent:
    return RawSourceEvent(
        source="suricata",
        source_event_id=f"{payload['flow_id']}:{payload['alert']['signature_id']}:{payload['timestamp']}",
        stream="alerts",
        occurred_at=datetime.fromisoformat(payload["timestamp"]),
        payload=payload,
    )


def test_normalizes_a_real_high_priority_alert_to_high_severity():
    normalized = normalize_suricata_event(_raw_event(_alert_raw()))
    assert normalized["source"] == "suricata"
    assert normalized["event_category"] == "network"
    assert normalized["event_type"] == "suricata.alert"
    assert normalized["severity"] == "high"  # Suricata priority 1
    assert normalized["src_ip"] == "172.28.0.3"
    assert normalized["dst_ip"] == "172.28.0.10"
    assert normalized["src_port"] == 47032
    assert normalized["dst_port"] == 80
    assert normalized["rule_id"] == "1000001"
    assert normalized["correlation_key"] == "host:172.28.0.3"
    assert "cmd=cat" in normalized["summary"]


def test_priority_2_and_3_map_to_medium_and_low():
    payload_2 = _alert_raw()
    payload_2["alert"]["severity"] = 2
    assert normalize_suricata_event(_raw_event(payload_2))["severity"] == "medium"

    payload_3 = _alert_raw()
    payload_3["alert"]["severity"] = 3
    assert normalize_suricata_event(_raw_event(payload_3))["severity"] == "low"


def test_unknown_stream_raises():
    raw = RawSourceEvent(
        source="suricata",
        source_event_id="x",
        stream="flow",
        occurred_at=datetime.now(UTC),
        payload={},
    )
    with pytest.raises(UnmappedEventTypeError):
        normalize_suricata_event(raw)


def test_malformed_alert_raises_not_silently_dropped():
    raw = RawSourceEvent(
        source="suricata",
        source_event_id="x",
        stream="alerts",
        occurred_at=datetime.now(UTC),
        payload={"event_type": "alert"},  # missing every required field
    )
    with pytest.raises(UnmappedEventTypeError):
        normalize_suricata_event(raw)


def test_scenario_id_is_read_from_injected_payload_key():
    payload = _alert_raw()
    payload["_sentinel_scenario_id"] = "SCN-NET-001"
    normalized = normalize_suricata_event(_raw_event(payload))
    assert normalized["scenario_id"] == "SCN-NET-001"
