from datetime import UTC, datetime, timedelta

from services.detection_engine.rules import RULES, EventView

RULES_BY_ID = {r.rule_id: r for r in RULES}
T0 = datetime(2026, 9, 6, 18, 0, 0, tzinfo=UTC)


def ev(
    event_id, event_type, category="identity", severity="info", asset_id=None, user_id=None, dt=T0
):
    return EventView(
        event_id=event_id,
        timestamp=dt,
        event_type=event_type,
        event_category=category,
        severity=severity,
        asset_id=asset_id,
        user_id=user_id,
        scenario_id=None,
    )


def test_det001_fires_on_three_failures_same_user_within_window():
    events = [
        ev("e1", "auth.failure", user_id="u1", dt=T0),
        ev("e2", "auth.failure", user_id="u1", dt=T0 + timedelta(seconds=10)),
        ev("e3", "auth.failure", user_id="u1", dt=T0 + timedelta(seconds=20)),
    ]
    candidates = RULES_BY_ID["DET-001"].evaluate(events, {})
    assert len(candidates) == 1
    assert candidates[0].severity == "medium"
    assert set(candidates[0].event_ids) == {"e1", "e2", "e3"}


def test_det001_does_not_fire_below_threshold():
    events = [
        ev("e1", "auth.failure", user_id="u1", dt=T0),
        ev("e2", "auth.failure", user_id="u1", dt=T0 + timedelta(seconds=10)),
    ]
    assert RULES_BY_ID["DET-001"].evaluate(events, {}) == []


def test_det001_does_not_fire_outside_window():
    events = [
        ev("e1", "auth.failure", user_id="u1", dt=T0),
        ev("e2", "auth.failure", user_id="u1", dt=T0 + timedelta(minutes=10)),
        ev("e3", "auth.failure", user_id="u1", dt=T0 + timedelta(minutes=20)),
    ]
    assert RULES_BY_ID["DET-001"].evaluate(events, {}) == []


def test_det001_escalates_to_high_when_followed_by_success():
    events = [
        ev("e1", "auth.failure", user_id="u1", dt=T0),
        ev("e2", "auth.failure", user_id="u1", dt=T0 + timedelta(seconds=10)),
        ev("e3", "auth.failure", user_id="u1", dt=T0 + timedelta(seconds=20)),
        ev("e4", "auth.success", user_id="u1", dt=T0 + timedelta(seconds=30)),
    ]
    candidates = RULES_BY_ID["DET-001"].evaluate(events, {})
    assert len(candidates) == 1
    assert candidates[0].severity == "high"
    assert "e4" in candidates[0].event_ids


def test_det001_does_not_mix_users():
    events = [
        ev("e1", "auth.failure", user_id="u1", dt=T0),
        ev("e2", "auth.failure", user_id="u2", dt=T0 + timedelta(seconds=1)),
        ev("e3", "auth.failure", user_id="u1", dt=T0 + timedelta(seconds=2)),
    ]
    assert RULES_BY_ID["DET-001"].evaluate(events, {}) == []


def test_det002_fires_only_for_critical_asset():
    events = [ev("e1", "asset.degrade", category="application", asset_id="gw-01")]
    assert RULES_BY_ID["DET-002"].evaluate(events, {"gw-01": 5}) != []
    assert RULES_BY_ID["DET-002"].evaluate(events, {"gw-01": 2}) == []
    assert RULES_BY_ID["DET-002"].evaluate(events, {}) == []


def test_det003_fires_on_bulk_record_access():
    events = [
        ev(
            f"e{i}",
            "record.access",
            category="application",
            user_id="u1",
            dt=T0 + timedelta(seconds=i),
        )
        for i in range(5)
    ]
    candidates = RULES_BY_ID["DET-003"].evaluate(events, {})
    assert len(candidates) == 1
    assert len(candidates[0].event_ids) == 5


def test_det004_fires_only_on_medium_or_high_telemetry_severity():
    events = [
        ev("e1", "telemetry.sample", category="runtime", severity="info", asset_id="uav-1"),
        ev("e2", "telemetry.sample", category="runtime", severity="high", asset_id="uav-2"),
    ]
    candidates = RULES_BY_ID["DET-004"].evaluate(events, {})
    assert len(candidates) == 1
    assert candidates[0].asset_id == "uav-2"


def test_det005_correlates_degrade_and_telemetry_on_same_asset_within_window():
    events = [
        ev("e1", "asset.degrade", category="application", asset_id="gw-01", dt=T0),
        ev(
            "e2",
            "telemetry.sample",
            category="runtime",
            severity="high",
            asset_id="gw-01",
            dt=T0 + timedelta(seconds=60),
        ),
    ]
    candidates = RULES_BY_ID["DET-005"].evaluate(events, {})
    assert len(candidates) == 1
    assert set(candidates[0].event_ids) == {"e1", "e2"}


def test_det005_does_not_correlate_different_assets():
    events = [
        ev("e1", "asset.degrade", category="application", asset_id="gw-01", dt=T0),
        ev(
            "e2",
            "telemetry.sample",
            category="runtime",
            severity="high",
            asset_id="gw-02",
            dt=T0 + timedelta(seconds=10),
        ),
    ]
    assert RULES_BY_ID["DET-005"].evaluate(events, {}) == []


def test_det006_correlates_token_revoke_and_record_access_same_identity():
    events = [
        ev("e1", "token.revoke", category="identity", user_id="svc-1", dt=T0),
        ev(
            "e2",
            "record.access",
            category="application",
            user_id="svc-1",
            dt=T0 + timedelta(minutes=5),
        ),
    ]
    candidates = RULES_BY_ID["DET-006"].evaluate(events, {})
    assert len(candidates) == 1
    assert set(candidates[0].event_ids) == {"e1", "e2"}


def test_det006_does_not_correlate_different_identities():
    events = [
        ev("e1", "token.revoke", category="identity", user_id="svc-1", dt=T0),
        ev(
            "e2",
            "record.access",
            category="application",
            user_id="svc-2",
            dt=T0 + timedelta(minutes=1),
        ),
    ]
    assert RULES_BY_ID["DET-006"].evaluate(events, {}) == []


def test_all_rule_ids_are_unique():
    ids = [r.rule_id for r in RULES]
    assert len(ids) == len(set(ids))
