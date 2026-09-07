from datetime import UTC, datetime

import pytest

from integrations.wazuh.mapper import UnmappedEventTypeError, normalize_wazuh_event
from services.event_ingestor.ports import RawSourceEvent


def _alert_raw(**overrides) -> dict:
    payload = {
        "id": "1690000000.123456",
        "timestamp": "2024-01-01T00:00:00.000+0000",
        "rule": {
            "id": "5720",
            "level": 10,
            "description": "Multiple authentication failures.",
            "groups": ["authentication_failures"],
            "mitre": {
                "id": ["T1110"], "tactic": ["Credential Access"], "technique": ["Brute Force"]
            },
        },
        "agent": {"id": "001", "name": "web-server-01", "ip": "10.0.0.5"},
        "decoder": {"name": "sshd"},
        "data": {"srcip": "203.0.113.5", "srcuser": "root"},
        "location": "/var/log/auth.log",
        "full_log": "Failed password for root from 203.0.113.5 port 4444 ssh2",
    }
    payload.update(overrides)
    return payload


def _raw_event(payload: dict) -> RawSourceEvent:
    return RawSourceEvent(
        source="wazuh",
        source_event_id=str(payload["id"]),
        stream="alerts",
        occurred_at=datetime.fromisoformat(payload["timestamp"]),
        payload=payload,
    )


def test_normalizes_a_real_representative_wazuh_alert():
    normalized = normalize_wazuh_event(_raw_event(_alert_raw()))
    assert normalized["source"] == "wazuh"
    assert normalized["event_category"] == "endpoint"
    assert normalized["event_type"] == "wazuh.alert"
    assert normalized["severity"] == "high"  # level 10
    assert normalized["asset_id"] == "wazuh:001"
    assert normalized["user_id"] == "root"
    assert normalized["src_ip"] == "203.0.113.5"
    assert normalized["rule_id"] == "5720"
    assert normalized["technique_ids"] == ["T1110"]
    assert normalized["correlation_key"] == "host:203.0.113.5"


@pytest.mark.parametrize(
    "level,expected",
    [(15, "critical"), (12, "critical"), (10, "high"), (7, "medium"), (4, "low"), (1, "info")],
)
def test_severity_translation_matches_wazuhs_own_level_scale(level, expected):
    payload = _alert_raw()
    payload["rule"]["level"] = level
    assert normalize_wazuh_event(_raw_event(payload))["severity"] == expected


def test_alert_with_no_srcip_falls_back_to_agent_correlation():
    payload = _alert_raw()
    payload["data"] = {}
    normalized = normalize_wazuh_event(_raw_event(payload))
    assert normalized["src_ip"] is None
    assert normalized["correlation_key"] == "wazuh:001"


def test_unknown_stream_raises():
    raw = RawSourceEvent(
        source="wazuh", source_event_id="x", stream="events", occurred_at=datetime.now(UTC),
        payload={},
    )
    with pytest.raises(UnmappedEventTypeError):
        normalize_wazuh_event(raw)


def test_malformed_alert_raises():
    raw = RawSourceEvent(
        source="wazuh", source_event_id="x", stream="alerts", occurred_at=datetime.now(UTC),
        payload={"id": "1"},  # missing rule/agent/timestamp
    )
    with pytest.raises(UnmappedEventTypeError):
        normalize_wazuh_event(raw)
