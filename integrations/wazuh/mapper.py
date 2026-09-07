"""WAZUH ALERT -> NORMALIZER -> CANONICAL EVENT. Pure, deterministic, unit-testable without a
live Wazuh manager - see integrations/wazuh/__init__.py for why no live Wazuh runs in this lab.
"""

from datetime import datetime

from pydantic import ValidationError

from domain.models.events import EventCategory, Severity
from integrations.wazuh.schemas import WazuhAlert
from services.event_ingestor.ports import RawSourceEvent

EVENT_CATEGORY: EventCategory = "endpoint"


class UnmappedEventTypeError(ValueError):
    """Raised when a source event's shape has no known normalization."""


def _severity_from_level(level: int) -> Severity:
    """Wazuh's own rule level is 0-16 (higher = more severe) - this table only translates that
    source-assigned scale into Sentinel's vocabulary, never re-judges the alert."""
    if level >= 12:
        return "critical"
    if level >= 9:
        return "high"
    if level >= 6:
        return "medium"
    if level >= 3:
        return "low"
    return "info"


def normalize_wazuh_event(raw: RawSourceEvent) -> dict:
    if raw.stream != "alerts":
        raise UnmappedEventTypeError(f"unknown Wazuh stream: {raw.stream!r}")

    try:
        alert = WazuhAlert.model_validate(raw.payload)
    except ValidationError as exc:
        raise UnmappedEventTypeError(f"malformed Wazuh alert: {exc}") from exc

    technique_ids = list(alert.rule.mitre.id) if alert.rule.mitre else []
    src_ip = alert.data.get("srcip")
    summary = f"Wazuh [{alert.agent.name}] {alert.rule.description} (level {alert.rule.level})"

    return {
        "event_id": f"wazuh-alert-{raw.source_event_id}",
        "timestamp": raw.occurred_at,
        "source": "wazuh",
        "source_event_id": raw.source_event_id,
        "asset_id": f"wazuh:{alert.agent.id}",
        "user_id": alert.data.get("srcuser"),
        "event_category": EVENT_CATEGORY,
        "event_type": "wazuh.alert",
        "severity": _severity_from_level(alert.rule.level),
        "src_ip": src_ip,
        "dst_ip": None,
        "process_name": alert.data.get("process") if isinstance(alert.data, dict) else None,
        "rule_id": alert.rule.id,
        "dns_query": None,
        "technique_ids": technique_ids,
        "summary": summary,
        "scenario_id": raw.payload.get("_sentinel_scenario_id"),
        "correlation_key": f"host:{src_ip}" if src_ip else f"wazuh:{alert.agent.id}",
    }


def parse_wazuh_timestamp(raw_timestamp: str) -> datetime:
    """Wazuh timestamps are ISO 8601 with milliseconds, e.g. `2024-01-01T00:00:00.000+0000` -
    the same shape Suricata's eve.json uses, which `datetime.fromisoformat` already parses."""
    return datetime.fromisoformat(raw_timestamp)
