from datetime import UTC, datetime

import pytest

from integrations.falco.mapper import (
    UnmappedEventTypeError,
    normalize_falco_event,
    parse_falco_timestamp,
)
from services.event_ingestor.ports import RawSourceEvent


def _alert_raw(**overrides) -> dict:
    payload = {
        "output": "19:41:23.652937000: Notice A shell was spawned in a container",
        "priority": "Notice",
        "rule": "Terminal shell in container",
        "time": "2024-01-01T19:41:23.652937000Z",
        "output_fields": {
            "container.id": "abc123",
            "proc.name": "bash",
            "user.name": "root",
        },
    }
    payload.update(overrides)
    return payload


def _raw_event(payload: dict) -> RawSourceEvent:
    return RawSourceEvent(
        source="falco",
        source_event_id="x",
        stream="alerts",
        occurred_at=parse_falco_timestamp(payload["time"]),
        payload=payload,
    )


def test_normalizes_a_real_falco_default_alert():
    normalized = normalize_falco_event(_raw_event(_alert_raw()))
    assert normalized["source"] == "falco"
    assert normalized["event_category"] == "endpoint"
    assert normalized["event_type"] == "falco.alert"
    assert normalized["severity"] == "medium"  # Notice
    assert normalized["asset_id"] == "falco:abc123"
    assert normalized["process_name"] == "bash"
    assert normalized["user_id"] == "root"
    assert normalized["rule_id"] == "Terminal shell in container"


@pytest.mark.parametrize(
    "priority,expected",
    [("Emergency", "critical"), ("Error", "high"), ("Warning", "medium"), ("Debug", "info")],
)
def test_priority_translation(priority, expected):
    payload = _alert_raw(priority=priority)
    assert normalize_falco_event(_raw_event(payload))["severity"] == expected


def test_timestamp_parsing_handles_nanosecond_precision():
    parsed = parse_falco_timestamp("2024-01-01T19:41:23.652937000Z")
    assert parsed.year == 2024
    assert parsed.microsecond == 652937


def test_timestamp_parsing_handles_no_fractional_seconds():
    parsed = parse_falco_timestamp("2024-01-01T19:41:23Z")
    assert parsed.second == 23


def test_unknown_stream_raises():
    raw = RawSourceEvent(
        source="falco", source_event_id="x", stream="events", occurred_at=datetime.now(UTC),
        payload={},
    )
    with pytest.raises(UnmappedEventTypeError):
        normalize_falco_event(raw)


def test_malformed_alert_raises():
    raw = RawSourceEvent(
        source="falco", source_event_id="x", stream="alerts", occurred_at=datetime.now(UTC),
        payload={"output": "x"},  # missing priority/rule/time
    )
    with pytest.raises(UnmappedEventTypeError):
        normalize_falco_event(raw)
