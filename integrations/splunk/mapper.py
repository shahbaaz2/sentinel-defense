"""SPLUNK SEARCH RESULT -> NORMALIZER -> CANONICAL EVENT, parameterized by a `SplunkFieldMapping`
profile (integrations/splunk/mappings/*.yaml) since no two Splunk deployments necessarily use the
same field names for the same concept. Pure and deterministic given a mapping - no SPL parsing, no
guessing at fields a profile doesn't declare.
"""

from datetime import UTC, datetime
from pathlib import Path

import yaml

from domain.models.events import EventCategory, Severity
from integrations.splunk.schemas import SplunkFieldMapping
from services.event_ingestor.ports import RawSourceEvent

EVENT_CATEGORY: EventCategory = "application"
MAPPINGS_DIR = Path(__file__).resolve().parent / "mappings"

_VALID_SEVERITIES: set[Severity] = {"info", "low", "medium", "high", "critical"}


class UnmappedEventTypeError(ValueError):
    """Raised when a Splunk result is missing the one field every mapping profile requires
    (a time field) - anything else missing just leaves that column `None`."""


def load_mapping_profile(name: str) -> SplunkFieldMapping:
    path = MAPPINGS_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"no Splunk mapping profile at {path}")
    with path.open() as f:
        raw = yaml.safe_load(f)
    return SplunkFieldMapping.model_validate(raw)


def list_mapping_profiles() -> list[str]:
    if not MAPPINGS_DIR.exists():
        return []
    return sorted(p.stem for p in MAPPINGS_DIR.glob("*.yaml"))


def _coerce_severity(raw_value: object, default: str) -> Severity:
    value = str(raw_value).lower() if raw_value is not None else default
    return value if value in _VALID_SEVERITIES else default  # type: ignore[return-value]


def parse_splunk_time(value: object) -> datetime:
    """Splunk's `_time` is a Unix epoch (string or number) in its raw search results."""
    return datetime.fromtimestamp(float(value), tz=UTC)  # type: ignore[arg-type]


def normalize_splunk_event(raw: RawSourceEvent, mapping: SplunkFieldMapping) -> dict:
    if raw.stream != "search_results":
        raise UnmappedEventTypeError(f"unknown Splunk stream: {raw.stream!r}")

    result = raw.payload
    if mapping.time_field not in result:
        raise UnmappedEventTypeError(
            f"Splunk result missing configured time field {mapping.time_field!r}"
        )

    src_ip = result.get(mapping.src_ip_field) if mapping.src_ip_field else None
    dst_ip = result.get(mapping.dst_ip_field) if mapping.dst_ip_field else None
    user = result.get(mapping.user_field) if mapping.user_field else None
    signature = result.get(mapping.signature_field) if mapping.signature_field else None
    rule_id = result.get(mapping.rule_id_field) if mapping.rule_id_field else None
    raw_severity = result.get(mapping.severity_field) if mapping.severity_field else None
    host = result.get(mapping.host_field)
    source = result.get(mapping.source_field)
    sourcetype = result.get(mapping.sourcetype_field)

    summary = f"Splunk [{sourcetype or source or 'unknown sourcetype'}]"
    if host:
        summary += f" on {host}"
    if signature:
        summary += f": {signature}"

    return {
        "event_id": f"splunk-{raw.source_event_id}",
        "timestamp": parse_splunk_time(result[mapping.time_field]),
        "source": "splunk",
        "source_event_id": raw.source_event_id,
        "asset_id": f"splunk:{host}" if host else None,
        "user_id": str(user) if user else None,
        "event_category": EVENT_CATEGORY,
        "event_type": f"splunk.{sourcetype or 'event'}",
        "severity": _coerce_severity(raw_severity, mapping.default_severity),
        "src_ip": str(src_ip) if src_ip else None,
        "dst_ip": str(dst_ip) if dst_ip else None,
        "process_name": None,
        "rule_id": str(rule_id) if rule_id else None,
        "dns_query": None,
        "technique_ids": [],
        "summary": summary,
        "scenario_id": result.get("_sentinel_scenario_id"),
        "correlation_key": (f"host:{src_ip}" if src_ip else None)
        or (f"splunk:{host}" if host else None),
    }
