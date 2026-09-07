from datetime import UTC, datetime

import pytest

from integrations.splunk.mapper import (
    UnmappedEventTypeError,
    list_mapping_profiles,
    load_mapping_profile,
    normalize_splunk_event,
)
from services.event_ingestor.ports import RawSourceEvent


def _raw(payload: dict, stream: str = "search_results") -> RawSourceEvent:
    return RawSourceEvent(
        source="splunk",
        source_event_id="evt-1",
        stream=stream,
        occurred_at=datetime.now(UTC),
        payload=payload,
    )


def test_all_three_shipped_mapping_profiles_load():
    profiles = list_mapping_profiles()
    assert set(profiles) == {"generic_security", "suricata", "windows_security"}
    for name in profiles:
        profile = load_mapping_profile(name)
        assert profile.name == name


def test_generic_security_profile_maps_cim_fields():
    mapping = load_mapping_profile("generic_security")
    result = {
        "_time": "1700000000",
        "host": "web-01",
        "source": "/var/log/auth.log",
        "sourcetype": "linux_secure",
        "src": "203.0.113.9",
        "dest": "10.0.0.5",
        "user": "root",
        "severity": "high",
        "signature": "SSH brute force",
        "rule_id": "R-100",
    }
    normalized = normalize_splunk_event(_raw(result), mapping)
    assert normalized["source"] == "splunk"
    assert normalized["src_ip"] == "203.0.113.9"
    assert normalized["dst_ip"] == "10.0.0.5"
    assert normalized["user_id"] == "root"
    assert normalized["severity"] == "high"
    assert normalized["rule_id"] == "R-100"
    assert normalized["correlation_key"] == "host:203.0.113.9"


def test_suricata_profile_reads_dotted_flattened_field_names():
    mapping = load_mapping_profile("suricata")
    result = {
        "_time": "1700000000",
        "host": "sensor-01",
        "source": "eve.json",
        "sourcetype": "suricata",
        "src_ip": "172.28.0.3",
        "dest_ip": "172.28.0.10",
        "alert.severity": "1",
        "alert.signature": "SENTINEL LAB alert",
        "alert.signature_id": "1000001",
    }
    normalized = normalize_splunk_event(_raw(result), mapping)
    assert normalized["src_ip"] == "172.28.0.3"
    assert normalized["rule_id"] == "1000001"


def test_invalid_severity_falls_back_to_profile_default():
    mapping = load_mapping_profile("generic_security")
    result = {"_time": "1700000000", "severity": "not-a-real-severity"}
    normalized = normalize_splunk_event(_raw(result), mapping)
    assert normalized["severity"] == mapping.default_severity


def test_missing_time_field_raises():
    mapping = load_mapping_profile("generic_security")
    with pytest.raises(UnmappedEventTypeError):
        normalize_splunk_event(_raw({"host": "x"}), mapping)


def test_unknown_stream_raises():
    mapping = load_mapping_profile("generic_security")
    with pytest.raises(UnmappedEventTypeError):
        normalize_splunk_event(_raw({"_time": "1700000000"}, stream="jobs"), mapping)


def test_missing_field_in_result_leaves_column_none_not_a_crash():
    mapping = load_mapping_profile("windows_security")  # dst_ip_field/severity_field are null
    result = {"_time": "1700000000", "ComputerName": "WIN-01", "EventCode": "4625"}
    normalized = normalize_splunk_event(_raw(result), mapping)
    assert normalized["dst_ip"] is None
    assert normalized["severity"] == mapping.default_severity
