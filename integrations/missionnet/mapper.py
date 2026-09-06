"""SOURCE EVENT -> NORMALIZER -> CANONICAL EVENT (blueprint §8), kept as a pure, deterministic
function so it's trivially unit-testable without a running MissionNet or database.

Every MissionNet audit `action` and the `telemetry` stream map to one explicit
(event_category, event_type) pair here - never inferred ad hoc downstream, and never treated as
natural-language instructions even though `detail`/`reason` fields are free text.
"""

from domain.models.events import EventCategory, Severity
from services.event_ingestor.ports import RawSourceEvent

# action -> (event_category, default_severity_if_source_omits_one)
_AUDIT_ACTION_CATEGORY: dict[str, EventCategory] = {
    "seed.reset": "control",
    "asset.degrade": "application",
    "asset.quarantine": "control",
    "asset.restore": "control",
    "token.revoke": "identity",
    "evidence.snapshot": "control",
    "telemetry.inject": "control",
    "auth.success": "identity",
    "auth.failure": "identity",
    "record.access": "application",
}

_VALID_SEVERITIES: set[Severity] = {"info", "low", "medium", "high", "critical"}


def _audit_severity(raw_severity: str) -> Severity:
    return raw_severity if raw_severity in _VALID_SEVERITIES else "info"  # type: ignore[return-value]


def _telemetry_severity(battery: int, link_quality: int) -> Severity:
    """Deterministic sensor-style thresholding, not a judgment call - documented here as the one
    place MissionNet telemetry severity is decided."""
    if battery < 15 or link_quality < 20:
        return "high"
    if battery < 30 or link_quality < 40:
        return "medium"
    return "info"


class UnmappedEventTypeError(ValueError):
    """Raised when a source event's action/stream has no known normalization - fail loudly rather
    than silently dropping or guessing at an unrecognized event type."""


def normalize_missionnet_event(raw: RawSourceEvent) -> dict:
    """Returns a dict shaped for `NormalizedEventRecord` (adds `event_type`/`correlation_key` on
    top of the canonical `NormalizedEvent` fields - see domain/models/orm.py for why)."""
    if raw.stream == "audit":
        return _normalize_audit(raw)
    if raw.stream == "telemetry":
        return _normalize_telemetry(raw)
    raise UnmappedEventTypeError(f"unknown MissionNet stream: {raw.stream!r}")


def _normalize_audit(raw: RawSourceEvent) -> dict:
    action = raw.payload["action"]
    if action not in _AUDIT_ACTION_CATEGORY:
        raise UnmappedEventTypeError(f"unmapped MissionNet audit action: {action!r}")

    object_type = raw.payload["object_type"]
    object_id = raw.payload["object_id"]
    detail = raw.payload.get("detail") or {}

    asset_id = object_id if object_type == "asset" else None
    if action == "token.revoke":
        user_id = detail.get("owner_user_id")
    elif action in ("auth.success", "auth.failure") and object_type == "identity_user":
        user_id = object_id
    elif action == "record.access":
        user_id = raw.payload.get("actor_id")
    else:
        user_id = None

    return {
        "event_id": f"missionnet-audit-{raw.source_event_id}",
        "timestamp": raw.occurred_at,
        "source": "missionnet",
        "source_event_id": raw.source_event_id,
        "asset_id": asset_id,
        "user_id": user_id,
        "event_category": _AUDIT_ACTION_CATEGORY[action],
        "event_type": action,
        "severity": _audit_severity(raw.payload.get("severity", "info")),
        "src_ip": None,
        "dst_ip": None,
        "process_name": None,
        "rule_id": None,
        "technique_ids": [],
        "summary": f"MissionNet {action} on {object_type}:{object_id}",
        "scenario_id": raw.payload.get("scenario_id"),
        "correlation_key": asset_id or user_id,
    }


def _normalize_telemetry(raw: RawSourceEvent) -> dict:
    asset_id = raw.payload["asset_id"]
    battery = raw.payload["battery"]
    link_quality = raw.payload["link_quality"]

    return {
        "event_id": f"missionnet-telemetry-{raw.source_event_id}",
        "timestamp": raw.occurred_at,
        "source": "missionnet",
        "source_event_id": raw.source_event_id,
        "asset_id": asset_id,
        "user_id": None,
        "event_category": "runtime",
        "event_type": "telemetry.sample",
        "severity": _telemetry_severity(battery, link_quality),
        "src_ip": None,
        "dst_ip": None,
        "process_name": None,
        "rule_id": None,
        "technique_ids": [],
        "summary": (
            f"Telemetry sample for {asset_id}: battery={battery}%, link_quality={link_quality}%"
        ),
        "scenario_id": None,
        "correlation_key": asset_id,
    }
