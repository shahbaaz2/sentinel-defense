"""SURICATA EVE ALERT -> NORMALIZER -> CANONICAL EVENT, mirroring
`integrations/missionnet/mapper.py`'s shape: a pure, deterministic function, unit-testable without
a running Suricata process or database.

Only `event_type: "alert"` lines are mapped (see schemas.py) - Suricata's `flow`/`fileinfo`/`stats`/
built-in `dns` events are real but not evidence Sentinel currently normalizes; Zeek is the
authoritative source for DNS/conn/HTTP evidence (see integrations/zeek/mapper.py and
docs/sensor-pipeline.md for why the two tools' roles don't overlap).
"""

from pydantic import ValidationError

from domain.models.events import EventCategory, Severity
from integrations.suricata.schemas import SuricataEveAlert
from services.event_ingestor.ports import RawSourceEvent

EVENT_CATEGORY: EventCategory = "network"

# Suricata's own convention: 1 = highest priority/most severe, 3 = lowest. Never invented by
# Sentinel - this table only translates the source's own severity into Sentinel's vocabulary.
_SEVERITY_BY_PRIORITY: dict[int, Severity] = {1: "high", 2: "medium", 3: "low"}


class UnmappedEventTypeError(ValueError):
    """Raised when a source event's shape has no known normalization - fail loudly rather than
    silently dropping or guessing at an unrecognized event type."""


def normalize_suricata_event(raw: RawSourceEvent) -> dict:
    """Returns a dict shaped for `NormalizedEventRecord`. `raw.stream` is always `"alerts"` for
    this adapter (see adapter.py) - the branch exists only so this function has the same shape as
    every other source's normalizer."""
    if raw.stream != "alerts":
        raise UnmappedEventTypeError(f"unknown Suricata stream: {raw.stream!r}")

    try:
        alert = SuricataEveAlert.model_validate(raw.payload)
    except ValidationError as exc:
        raise UnmappedEventTypeError(f"malformed Suricata eve.json alert: {exc}") from exc

    severity = _SEVERITY_BY_PRIORITY.get(alert.alert.severity, "low")
    url = alert.http.url if alert.http else None
    method = alert.http.http_method if alert.http else None
    summary = (
        f"Suricata alert: {alert.alert.signature} "
        f"({alert.src_ip}:{alert.src_port} -> {alert.dest_ip}:{alert.dest_port}/{alert.proto})"
    )
    if method and url:
        summary += f" [{method} {url}]"

    return {
        "event_id": f"suricata-alert-{raw.source_event_id}",
        "timestamp": raw.occurred_at,
        "source": "suricata",
        "source_event_id": raw.source_event_id,
        "asset_id": None,
        "user_id": None,
        "event_category": EVENT_CATEGORY,
        "event_type": "suricata.alert",
        "severity": severity,
        "src_ip": alert.src_ip,
        "dst_ip": alert.dest_ip,
        "src_port": alert.src_port,
        "dst_port": alert.dest_port,
        "process_name": None,
        "rule_id": str(alert.alert.signature_id),
        "dns_query": None,
        "technique_ids": [],
        "summary": summary,
        "scenario_id": raw.payload.get("_sentinel_scenario_id"),
        "correlation_key": f"host:{alert.src_ip}",
    }
