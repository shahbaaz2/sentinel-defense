from datetime import UTC, datetime

import pytest

from integrations.zeek.mapper import UnmappedEventTypeError, normalize_zeek_event
from services.event_ingestor.ports import RawSourceEvent


def _raw(stream: str, payload: dict) -> RawSourceEvent:
    return RawSourceEvent(
        source="zeek",
        source_event_id=f"{stream}:{payload['uid']}",
        stream=stream,
        occurred_at=datetime.fromtimestamp(payload["ts"], tz=UTC),
        payload=payload,
    )


def test_normalizes_conn_log_as_evidence_with_info_severity():
    payload = {
        "ts": 1788749556.524556,
        "uid": "CS5n9k4pHwVBrvgRIf",
        "id.orig_h": "172.28.0.3",
        "id.orig_p": 56490,
        "id.resp_h": "172.28.0.11",
        "id.resp_p": 53,
        "proto": "udp",
        "service": "dns",
        "conn_state": "SF",
    }
    normalized = normalize_zeek_event(_raw("conn", payload))
    assert normalized["source"] == "zeek"
    assert normalized["event_type"] == "zeek.conn"
    assert normalized["severity"] == "info"  # Zeek is evidence, never itself a detection
    assert normalized["src_ip"] == "172.28.0.3"
    assert normalized["dst_ip"] == "172.28.0.11"
    assert normalized["correlation_key"] == "host:172.28.0.3"


def test_normalizes_dns_log_and_preserves_the_query_name():
    payload = {
        "ts": 1788749556.524556,
        "uid": "CS5n9k4pHwVBrvgRIf",
        "id.orig_h": "172.28.0.3",
        "id.orig_p": 56490,
        "id.resp_h": "172.28.0.11",
        "id.resp_p": 53,
        "query": "a8f3k2m9x7q1z5.sentinel-lab-dga-test.example",
        "qtype_name": "A",
        "rcode_name": "NOERROR",
        "answers": ["172.28.0.10"],
    }
    normalized = normalize_zeek_event(_raw("dns", payload))
    assert normalized["event_type"] == "zeek.dns"
    assert normalized["dns_query"] == "a8f3k2m9x7q1z5.sentinel-lab-dga-test.example"
    assert normalized["severity"] == "info"


def test_normalizes_http_log():
    payload = {
        "ts": 1788749556.514459,
        "uid": "C5qX274aqsvKxZU4d",
        "id.orig_h": "172.28.0.3",
        "id.orig_p": 47030,
        "id.resp_h": "172.28.0.10",
        "id.resp_p": 80,
        "method": "GET",
        "host": "172.28.0.10",
        "uri": "/index.html",
        "status_code": 404,
    }
    normalized = normalize_zeek_event(_raw("http", payload))
    assert normalized["event_type"] == "zeek.http"
    assert "GET" in normalized["summary"]


def test_unknown_stream_raises():
    with pytest.raises(UnmappedEventTypeError):
        normalize_zeek_event(_raw("files", {"ts": 0.0, "uid": "x"}))


def test_malformed_record_raises():
    raw = RawSourceEvent(
        source="zeek",
        source_event_id="conn:x",
        stream="conn",
        occurred_at=datetime.now(UTC),
        payload={"ts": 0.0},  # missing uid/id.orig_h/...
    )
    with pytest.raises(UnmappedEventTypeError):
        normalize_zeek_event(raw)
