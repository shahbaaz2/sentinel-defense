"""ZEEK LOG LINE -> NORMALIZER -> CANONICAL EVENT. Every Zeek record normalizes to `severity:
"info"` - Zeek is evidence, never itself a detection (blueprint intent, Phase 8 prompt); the one
rule that treats Zeek DNS evidence as detection-worthy (NET-002) does its own pattern match over
`dns_query` at detection time, not at normalization time - see services/detection_engine/rules.py.
"""

from pydantic import ValidationError

from domain.models.events import EventCategory, Severity
from integrations.zeek.schemas import ZeekConnRecord, ZeekDnsRecord, ZeekHttpRecord
from services.event_ingestor.ports import RawSourceEvent

EVENT_CATEGORY: EventCategory = "network"
_SEVERITY: Severity = "info"


class UnmappedEventTypeError(ValueError):
    """Raised when a source event's stream/shape has no known normalization."""


def normalize_zeek_event(raw: RawSourceEvent) -> dict:
    if raw.stream == "conn":
        return _normalize_conn(raw)
    if raw.stream == "dns":
        return _normalize_dns(raw)
    if raw.stream == "http":
        return _normalize_http(raw)
    raise UnmappedEventTypeError(f"unknown Zeek stream: {raw.stream!r}")


def _base_fields(raw: RawSourceEvent, event_type: str, src_ip: str, dst_ip: str) -> dict:
    return {
        "event_id": f"zeek-{raw.stream}-{raw.source_event_id}",
        "timestamp": raw.occurred_at,
        "source": "zeek",
        "source_event_id": raw.source_event_id,
        "asset_id": None,
        "user_id": None,
        "event_category": EVENT_CATEGORY,
        "event_type": event_type,
        "severity": _SEVERITY,
        "src_ip": src_ip,
        "dst_ip": dst_ip,
        "process_name": None,
        "rule_id": None,
        "dns_query": None,
        "technique_ids": [],
        "scenario_id": raw.payload.get("_sentinel_scenario_id"),
        "correlation_key": f"host:{src_ip}",
    }


def _normalize_conn(raw: RawSourceEvent) -> dict:
    try:
        rec = ZeekConnRecord.model_validate(raw.payload)
    except ValidationError as exc:
        raise UnmappedEventTypeError(f"malformed Zeek conn.log record: {exc}") from exc

    fields = _base_fields(raw, "zeek.conn", rec.id_orig_h, rec.id_resp_h)
    fields["src_port"] = rec.id_orig_p
    fields["dst_port"] = rec.id_resp_p
    fields["summary"] = (
        f"Zeek connection {rec.id_orig_h}:{rec.id_orig_p} -> {rec.id_resp_h}:{rec.id_resp_p} "
        f"({rec.proto}{f'/{rec.service}' if rec.service else ''}, state={rec.conn_state or 'n/a'})"
    )
    return fields


def _normalize_dns(raw: RawSourceEvent) -> dict:
    try:
        rec = ZeekDnsRecord.model_validate(raw.payload)
    except ValidationError as exc:
        raise UnmappedEventTypeError(f"malformed Zeek dns.log record: {exc}") from exc

    fields = _base_fields(raw, "zeek.dns", rec.id_orig_h, rec.id_resp_h)
    fields["src_port"] = rec.id_orig_p
    fields["dst_port"] = rec.id_resp_p
    fields["dns_query"] = rec.query
    fields["summary"] = (
        f"Zeek DNS query {rec.query!r} ({rec.qtype_name or '?'}) from {rec.id_orig_h} "
        f"- {rec.rcode_name or 'NO_RESPONSE'}"
    )
    return fields


def _normalize_http(raw: RawSourceEvent) -> dict:
    try:
        rec = ZeekHttpRecord.model_validate(raw.payload)
    except ValidationError as exc:
        raise UnmappedEventTypeError(f"malformed Zeek http.log record: {exc}") from exc

    fields = _base_fields(raw, "zeek.http", rec.id_orig_h, rec.id_resp_h)
    fields["src_port"] = rec.id_orig_p
    fields["dst_port"] = rec.id_resp_p
    fields["summary"] = (
        f"Zeek HTTP {rec.method or '?'} {rec.host or ''}{rec.uri or ''} "
        f"-> {rec.status_code if rec.status_code is not None else '?'}"
    )
    return fields
