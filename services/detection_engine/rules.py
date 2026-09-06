"""Deterministic lab detection rules. No AI anywhere in this file - every rule is a pure function
over a window of normalized events, independently unit-testable without a database.

Rules are intentionally plain Python rather than Sigma so the engine, storage, and API can be
proven first; `detections/sigma/` (blueprint §18.7) is a Phase 8 addition behind the same `Rule`
shape, not a rewrite.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

AUTH_FAILURE_THRESHOLD = 3
AUTH_FAILURE_WINDOW = timedelta(minutes=5)
RECORD_ACCESS_THRESHOLD = 5
RECORD_ACCESS_WINDOW = timedelta(minutes=2)
MULTI_SIGNAL_WINDOW = timedelta(seconds=120)
TOKEN_RECORD_ACCESS_WINDOW = timedelta(minutes=10)
CRITICAL_ASSET_THRESHOLD = 4


@dataclass(frozen=True)
class EventView:
    """Rule-facing projection of a `NormalizedEventRecord` row - decouples rule logic from the ORM
    so rules can be tested with plain data and no database."""

    event_id: str
    timestamp: datetime
    event_type: str
    event_category: str
    severity: str
    asset_id: str | None
    user_id: str | None
    scenario_id: str | None


@dataclass(frozen=True)
class RuleCandidate:
    event_ids: list[str]
    asset_id: str | None
    user_id: str | None
    severity: str
    evidence_summary: str


@dataclass(frozen=True)
class Rule:
    rule_id: str
    name: str
    version: str
    default_severity: str
    category: str
    description: str
    event_categories: list[str]
    mitre_techniques: list[str]
    evaluate: Callable[[list[EventView], dict[str, int]], list[RuleCandidate]]


def _windowed_groups(
    events: list[EventView], window: timedelta
) -> list[list[EventView]]:
    """Greedily partitions a time-sorted list into non-overlapping groups where each group's span
    is <= window. Deliberately non-overlapping (rather than every sliding window) so a burst of N
    matching events produces one detection, not N-2 overlapping ones."""
    groups: list[list[EventView]] = []
    current: list[EventView] = []
    for event in sorted(events, key=lambda e: e.timestamp):
        if current and event.timestamp - current[0].timestamp > window:
            groups.append(current)
            current = [event]
        else:
            current.append(event)
    if current:
        groups.append(current)
    return groups


def _rule_repeated_auth_failures(
    events: list[EventView], _criticality: dict[str, int]
) -> list[RuleCandidate]:
    failures = [e for e in events if e.event_type == "auth.failure"]
    successes = [e for e in events if e.event_type == "auth.success"]
    candidates = []

    by_user: dict[str, list[EventView]] = {}
    for e in failures:
        if e.user_id:
            by_user.setdefault(e.user_id, []).append(e)

    for user_id, user_failures in by_user.items():
        for group in _windowed_groups(user_failures, AUTH_FAILURE_WINDOW):
            if len(group) < AUTH_FAILURE_THRESHOLD:
                continue
            group_end = max(e.timestamp for e in group)
            follow_up_success = next(
                (
                    s
                    for s in successes
                    if s.user_id == user_id
                    and group_end <= s.timestamp <= group_end + AUTH_FAILURE_WINDOW
                ),
                None,
            )
            event_ids = [e.event_id for e in group]
            if follow_up_success:
                event_ids.append(follow_up_success.event_id)
                candidates.append(
                    RuleCandidate(
                        event_ids=event_ids,
                        asset_id=None,
                        user_id=user_id,
                        severity="high",
                        evidence_summary=(
                            f"{len(group)} authentication failures for {user_id} followed by a "
                            "successful login - possible compromised credential"
                        ),
                    )
                )
            else:
                candidates.append(
                    RuleCandidate(
                        event_ids=event_ids,
                        asset_id=None,
                        user_id=user_id,
                        severity="medium",
                        evidence_summary=f"{len(group)} authentication failures for {user_id}",
                    )
                )
    return candidates


def _rule_critical_asset_degraded(
    events: list[EventView], criticality: dict[str, int]
) -> list[RuleCandidate]:
    candidates = []
    for e in events:
        if e.event_type != "asset.degrade" or not e.asset_id:
            continue
        if criticality.get(e.asset_id, 0) >= CRITICAL_ASSET_THRESHOLD:
            candidates.append(
                RuleCandidate(
                    event_ids=[e.event_id],
                    asset_id=e.asset_id,
                    user_id=None,
                    severity="high",
                    evidence_summary=(
                        f"Mission-critical asset {e.asset_id} degraded unexpectedly "
                        f"(criticality {criticality.get(e.asset_id)})"
                    ),
                )
            )
    return candidates


def _rule_record_access_anomaly(
    events: list[EventView], _criticality: dict[str, int]
) -> list[RuleCandidate]:
    accesses = [e for e in events if e.event_type == "record.access"]
    by_user: dict[str, list[EventView]] = {}
    for e in accesses:
        if e.user_id:
            by_user.setdefault(e.user_id, []).append(e)

    candidates = []
    for user_id, user_accesses in by_user.items():
        for group in _windowed_groups(user_accesses, RECORD_ACCESS_WINDOW):
            if len(group) < RECORD_ACCESS_THRESHOLD:
                continue
            candidates.append(
                RuleCandidate(
                    event_ids=[e.event_id for e in group],
                    asset_id=None,
                    user_id=user_id,
                    severity="medium",
                    evidence_summary=(
                        f"{len(group)} mission-record accesses by {user_id} in under "
                        f"{int(RECORD_ACCESS_WINDOW.total_seconds())}s"
                    ),
                )
            )
    return candidates


def _rule_telemetry_anomaly(
    events: list[EventView], _criticality: dict[str, int]
) -> list[RuleCandidate]:
    return [
        RuleCandidate(
            event_ids=[e.event_id],
            asset_id=e.asset_id,
            user_id=None,
            severity=e.severity,
            evidence_summary=f"Anomalous telemetry reading on {e.asset_id}",
        )
        for e in events
        if e.event_type == "telemetry.sample" and e.severity in ("medium", "high", "critical")
    ]


def _rule_multi_signal_asset_compromise(
    events: list[EventView], _criticality: dict[str, int]
) -> list[RuleCandidate]:
    degrades = [e for e in events if e.event_type == "asset.degrade" and e.asset_id]
    telemetry_anomalies = [
        e
        for e in events
        if e.event_type == "telemetry.sample" and e.severity in ("medium", "high", "critical")
    ]

    candidates = []
    for degrade in degrades:
        matches = [
            t
            for t in telemetry_anomalies
            if t.asset_id == degrade.asset_id
            and abs((t.timestamp - degrade.timestamp).total_seconds())
            <= MULTI_SIGNAL_WINDOW.total_seconds()
        ]
        if matches:
            event_ids = [degrade.event_id] + [m.event_id for m in matches]
            candidates.append(
                RuleCandidate(
                    event_ids=sorted(set(event_ids)),
                    asset_id=degrade.asset_id,
                    user_id=None,
                    severity="high",
                    evidence_summary=(
                        f"Asset {degrade.asset_id} degraded with a correlated telemetry anomaly "
                        f"within {int(MULTI_SIGNAL_WINDOW.total_seconds())}s"
                    ),
                )
            )
    return candidates


def _rule_identity_compromise_token_and_access(
    events: list[EventView], _criticality: dict[str, int]
) -> list[RuleCandidate]:
    revokes = [e for e in events if e.event_type == "token.revoke" and e.user_id]
    accesses = [e for e in events if e.event_type == "record.access" and e.user_id]

    candidates = []
    for revoke in revokes:
        matches = [
            a
            for a in accesses
            if a.user_id == revoke.user_id
            and abs((a.timestamp - revoke.timestamp).total_seconds())
            <= TOKEN_RECORD_ACCESS_WINDOW.total_seconds()
        ]
        if matches:
            event_ids = [revoke.event_id] + [m.event_id for m in matches]
            candidates.append(
                RuleCandidate(
                    event_ids=sorted(set(event_ids)),
                    asset_id=None,
                    user_id=revoke.user_id,
                    severity="high",
                    evidence_summary=(
                        f"Service credential for {revoke.user_id} revoked with correlated "
                        "mission-record access by the same identity"
                    ),
                )
            )
    return candidates


RULES: list[Rule] = [
    Rule(
        rule_id="DET-001",
        name="Repeated Authentication Failures",
        version="1.0.0",
        default_severity="medium",
        category="credential-abuse",
        description=(
            f"Fires when the same identity produces {AUTH_FAILURE_THRESHOLD}+ auth.failure "
            f"events within {int(AUTH_FAILURE_WINDOW.total_seconds() // 60)} minutes; escalates "
            "to high if a successful login follows within the same window."
        ),
        event_categories=["identity"],
        mitre_techniques=["T1110"],  # Brute Force
        evaluate=_rule_repeated_auth_failures,
    ),
    Rule(
        rule_id="DET-002",
        name="Mission-Critical Asset Degraded Unexpectedly",
        version="1.0.0",
        default_severity="high",
        category="asset-degradation",
        description=(
            f"Fires on a single asset.degrade event where the target asset's criticality is "
            f">= {CRITICAL_ASSET_THRESHOLD}."
        ),
        event_categories=["application"],
        mitre_techniques=["T1489"],  # Service Stop
        evaluate=_rule_critical_asset_degraded,
    ),
    Rule(
        rule_id="DET-003",
        name="Sensitive Mission Record Access Anomaly",
        version="1.0.0",
        default_severity="medium",
        category="data-access-anomaly",
        description=(
            f"Fires when the same identity produces {RECORD_ACCESS_THRESHOLD}+ record.access "
            f"events within {int(RECORD_ACCESS_WINDOW.total_seconds() // 60)} minutes."
        ),
        event_categories=["application"],
        mitre_techniques=["T1213"],  # Data from Information Repositories
        evaluate=_rule_record_access_anomaly,
    ),
    Rule(
        rule_id="DET-004",
        name="Suspicious Telemetry Anomaly",
        version="1.0.0",
        default_severity="medium",
        category="telemetry-anomaly",
        description=(
            "Fires on a single telemetry sample with medium/high/critical severity (low "
            "battery or poor link quality, per the mapper's documented thresholds)."
        ),
        event_categories=["runtime"],
        mitre_techniques=[],
        evaluate=_rule_telemetry_anomaly,
    ),
    Rule(
        rule_id="DET-005",
        name="Multi-Signal Asset Compromise Indicator",
        version="1.0.0",
        default_severity="high",
        category="multi-signal-compromise",
        description=(
            f"Fires when an asset.degrade event and an anomalous telemetry sample land on the "
            f"same asset within {int(MULTI_SIGNAL_WINDOW.total_seconds())} seconds."
        ),
        event_categories=["application", "runtime"],
        mitre_techniques=["T1489"],
        evaluate=_rule_multi_signal_asset_compromise,
    ),
    Rule(
        rule_id="DET-006",
        name="Identity Compromise Indicator: Token Revoke + Record Access",
        version="1.0.0",
        default_severity="high",
        category="identity-compromise",
        description=(
            f"Fires when a token.revoke and a record.access event share the same identity "
            f"within {int(TOKEN_RECORD_ACCESS_WINDOW.total_seconds() // 60)} minutes."
        ),
        event_categories=["identity", "application"],
        mitre_techniques=["T1078"],  # Valid Accounts
        evaluate=_rule_identity_compromise_token_and_access,
    ),
]
