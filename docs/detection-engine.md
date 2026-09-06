# Detection engine

Deterministic only - no LLM is consulted to decide whether a detection fires (Phase 2 hard
requirement). Rules live in `services/detection_engine/rules.py` as plain Python functions over a
list of `EventView` (a pure, ORM-free projection of `NormalizedEventRecord`), which is what makes
every rule unit-testable without a database (`tests/unit/test_detection_rules.py`).

## Why plain Python, not Sigma, for now

Sigma (blueprint §18.7) is the eventual detection-content format, but standing up the full Sigma
pipeline before the ingest/correlation/incident/API/dashboard vertical slice was proven would have
been solving the wrong problem first. The `Rule` dataclass shape (`rule_id`, `name`, `version`,
`severity`, `category`, `mitre_techniques`, `evaluate`) is deliberately close to what a Sigma-backed
rule would need to provide, so migrating specific rules to Sigma later (Phase 8) means writing a
Sigma-to-`Rule` adapter, not redesigning the engine.

## The six lab rules

| Rule | Trigger | Window | Default severity |
|---|---|---|---|
| DET-001 Repeated Authentication Failures | ≥3 `auth.failure` for the same user | 5 min | medium (high if followed by `auth.success`) |
| DET-002 Mission-Critical Asset Degraded Unexpectedly | one `asset.degrade` where asset criticality ≥ 4 | none | high |
| DET-003 Sensitive Mission Record Access Anomaly | ≥5 `record.access` by the same user | 2 min | medium |
| DET-004 Suspicious Telemetry Anomaly | one `telemetry.sample` with medium/high/critical severity | none | matches event severity |
| DET-005 Multi-Signal Asset Compromise Indicator | `asset.degrade` + anomalous `telemetry.sample` on the same asset | 120 s | high |
| DET-006 Identity Compromise Indicator | `token.revoke` + `record.access` by the same identity | 10 min | high |

Every rule's ATT&CK mapping is either a well-established technique for that behavior (T1110 Brute
Force, T1489 Service Stop, T1213 Data from Information Repositories, T1078 Valid Accounts) or
omitted entirely (DET-004) rather than guessed - per the explicit instruction not to invent
mappings for dashboard appeal.

## Genuine signals only

Every one of these rules depends on a MissionNet action that didn't exist before Phase 2:
`auth.success`/`auth.failure` (a real, if minimal, login endpoint - `POST /identity/login`) and
`record.access` (`GET /mission-data/records/{id}?actor_user_id=...`). These were added to
MissionNet itself, not synthesized inside Sentinel - see DECISIONS.md for why, and
`tests/integration/test_missionnet_auth_and_access.py` for proof they produce real audit rows.

## Idempotency

Each rule candidate gets a `dedupe_key = sha256(rule_id + sorted(event_ids))`. Re-running the
engine against unchanged data produces the exact same dedupe keys, so nothing new is created -
verified in `tests/integration/test_sentinel_ingestion_pipeline.py::test_repeated_ingestion_is_idempotent_no_duplicate_events_or_detections`.

## Adding a rule

1. Write a pure function `(events: list[EventView], criticality: dict[str, int]) ->
   list[RuleCandidate]` in `rules.py`.
2. Add it to the `RULES` list with a unique `rule_id`, real ATT&CK mapping or none, and a
   `category` (used by the incident engine's default title/category when it starts a new incident).
3. Add unit tests in `tests/unit/test_detection_rules.py` - fires on the positive case, does not
   fire just below threshold, does not fire outside the window, does not cross-contaminate
   different assets/identities.

No code outside `rules.py` needs to change - `services/detection_engine/engine.py` iterates
`RULES` generically.
