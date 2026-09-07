"""FALCO ALERT -> NORMALIZER -> CANONICAL EVENT. Pure and deterministic - see
integrations/falco/__init__.py for why nothing live runs against this in the current lab.
"""

from datetime import datetime

from pydantic import ValidationError

from domain.models.events import EventCategory, Severity
from integrations.falco.schemas import FalcoAlert
from services.event_ingestor.ports import RawSourceEvent

EVENT_CATEGORY: EventCategory = "endpoint"

# Falco's own priority scale, highest to lowest - never re-judged by Sentinel.
_SEVERITY_BY_PRIORITY: dict[str, Severity] = {
    "emergency": "critical",
    "alert": "critical",
    "critical": "critical",
    "error": "high",
    "warning": "medium",
    "notice": "medium",
    "informational": "low",
    "debug": "info",
}


class UnmappedEventTypeError(ValueError):
    """Raised when a source event's shape has no known normalization."""


def normalize_falco_event(raw: RawSourceEvent) -> dict:
    if raw.stream != "alerts":
        raise UnmappedEventTypeError(f"unknown Falco stream: {raw.stream!r}")

    try:
        alert = FalcoAlert.model_validate(raw.payload)
    except ValidationError as exc:
        raise UnmappedEventTypeError(f"malformed Falco alert: {exc}") from exc

    container_id = alert.output_fields.get("container.id")
    process_name = alert.output_fields.get("proc.name")
    user = alert.output_fields.get("user.name")

    return {
        "event_id": f"falco-alert-{raw.source_event_id}",
        "timestamp": raw.occurred_at,
        "source": "falco",
        "source_event_id": raw.source_event_id,
        "asset_id": f"falco:{container_id}" if container_id else None,
        "user_id": user,
        "event_category": EVENT_CATEGORY,
        "event_type": "falco.alert",
        "severity": _SEVERITY_BY_PRIORITY.get(alert.priority.lower(), "medium"),
        "src_ip": None,
        "dst_ip": None,
        "process_name": process_name,
        "rule_id": alert.rule,
        "dns_query": None,
        "technique_ids": [],
        "summary": alert.output[:2000],
        "scenario_id": raw.payload.get("_sentinel_scenario_id"),
        "correlation_key": f"falco:{container_id}" if container_id else None,
    }


def parse_falco_timestamp(raw_timestamp: str) -> datetime:
    """Falco's `time` is RFC3339 with nanoseconds, e.g. `2024-01-01T19:41:23.652937000Z` - trim to
    microsecond precision (`datetime.fromisoformat` supports at most 6 fractional digits)."""
    value = raw_timestamp[:-1] if raw_timestamp.endswith("Z") else raw_timestamp
    if "." in value:
        head, fraction = value.split(".", 1)
        value = f"{head}.{fraction[:6]}"
    return datetime.fromisoformat(value + "+00:00")
