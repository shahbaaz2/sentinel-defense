from datetime import UTC, datetime, timedelta

from services.detection_engine.rules import RULES, EventView

RULES_BY_ID = {r.rule_id: r for r in RULES}
T0 = datetime(2026, 9, 6, 18, 0, 0, tzinfo=UTC)


def net_ev(
    event_id,
    event_type,
    source,
    severity="info",
    src_ip=None,
    dst_ip=None,
    rule_id=None,
    dns_query=None,
    dt=T0,
):
    return EventView(
        event_id=event_id,
        timestamp=dt,
        event_type=event_type,
        event_category="network",
        severity=severity,
        asset_id=None,
        user_id=None,
        scenario_id=None,
        source=source,
        src_ip=src_ip,
        dst_ip=dst_ip,
        rule_id=rule_id,
        dns_query=dns_query,
    )


# ---------------------------------------------------------------------------------------------
# NET-001: Suricata High-Severity Lab Alert
# ---------------------------------------------------------------------------------------------


def test_net001_fires_on_high_severity_suricata_alert():
    events = [
        net_ev(
            "e1", "suricata.alert", "suricata", severity="high", src_ip="172.28.0.3",
            rule_id="1000001",
        )
    ]
    candidates = RULES_BY_ID["NET-001"].evaluate(events, {})
    assert len(candidates) == 1
    assert candidates[0].correlation_key == "host:172.28.0.3"


def test_net001_does_not_fire_on_medium_severity_alert():
    events = [
        net_ev("e1", "suricata.alert", "suricata", severity="medium", src_ip="172.28.0.3")
    ]
    assert RULES_BY_ID["NET-001"].evaluate(events, {}) == []


def test_net001_ignores_non_suricata_sources():
    events = [net_ev("e1", "suricata.alert", "zeek", severity="high", src_ip="172.28.0.3")]
    assert RULES_BY_ID["NET-001"].evaluate(events, {}) == []


# ---------------------------------------------------------------------------------------------
# NET-002: Suspicious DNS Pattern from Zeek
# ---------------------------------------------------------------------------------------------


def test_net002_fires_on_dga_like_query_name():
    events = [
        net_ev(
            "e1", "zeek.dns", "zeek", src_ip="172.28.0.3",
            dns_query="a8f3k2m9x7q1z5.sentinel-lab-dga-test.example",
        )
    ]
    candidates = RULES_BY_ID["NET-002"].evaluate(events, {})
    assert len(candidates) == 1
    assert candidates[0].correlation_key == "host:172.28.0.3"


def test_net002_does_not_fire_on_a_normal_looking_hostname():
    events = [net_ev("e1", "zeek.dns", "zeek", src_ip="172.28.0.3", dns_query="www.example.com")]
    assert RULES_BY_ID["NET-002"].evaluate(events, {}) == []


def test_net002_ignores_events_with_no_dns_query():
    events = [net_ev("e1", "zeek.conn", "zeek", src_ip="172.28.0.3")]
    assert RULES_BY_ID["NET-002"].evaluate(events, {}) == []


# ---------------------------------------------------------------------------------------------
# NET-003: Suricata + Zeek Cross-Sensor Correlation
# ---------------------------------------------------------------------------------------------


def test_net003_fires_when_suricata_alert_and_zeek_evidence_share_host_within_window():
    events = [
        net_ev("e1", "suricata.alert", "suricata", severity="high", src_ip="172.28.0.3", dt=T0),
        net_ev(
            "e2", "zeek.conn", "zeek", src_ip="172.28.0.3", dt=T0 + timedelta(seconds=5)
        ),
    ]
    candidates = RULES_BY_ID["NET-003"].evaluate(events, {})
    assert len(candidates) == 1
    assert set(candidates[0].event_ids) == {"e1", "e2"}
    assert candidates[0].correlation_key == "host:172.28.0.3"


def test_net003_does_not_fire_outside_the_correlation_window():
    events = [
        net_ev("e1", "suricata.alert", "suricata", severity="high", src_ip="172.28.0.3", dt=T0),
        net_ev(
            "e2", "zeek.conn", "zeek", src_ip="172.28.0.3", dt=T0 + timedelta(seconds=120)
        ),
    ]
    assert RULES_BY_ID["NET-003"].evaluate(events, {}) == []


def test_net003_does_not_fire_for_a_different_host():
    events = [
        net_ev("e1", "suricata.alert", "suricata", severity="high", src_ip="172.28.0.3", dt=T0),
        net_ev("e2", "zeek.conn", "zeek", src_ip="10.0.0.9", dt=T0 + timedelta(seconds=5)),
    ]
    assert RULES_BY_ID["NET-003"].evaluate(events, {}) == []


def test_net003_requires_a_suricata_alert_not_just_zeek_evidence_alone():
    events = [
        net_ev("e1", "zeek.conn", "zeek", src_ip="172.28.0.3", dt=T0),
        net_ev("e2", "zeek.dns", "zeek", src_ip="172.28.0.3", dt=T0 + timedelta(seconds=5)),
    ]
    assert RULES_BY_ID["NET-003"].evaluate(events, {}) == []
