# PROGRESS

Current phase, what is actually verified working (not just present), and the next task. Update this
at every phase checkpoint — never claim something works without having run the check.

## Current phase: Phase 2 — COMPLETE (all 15 Definition-of-Done items verified)

### Phase 0 + 1 recap (see git history / earlier sections for full detail)
Repo scaffold, Sentinel/MissionNet API shells, both dashboards, PostgreSQL in Colima, MissionNet's
full synthetic data model + lab-control API + Operations Console — all verified end-to-end and
committed (`0fa4286`, `3e7618e`).

### Phase 2 — verified working

**MissionNet extensions** (genuine signals, not fabricated - see DECISIONS.md):
- `POST /identity/login` — real auth against seeded synthetic identities, writes
  `auth.success`/`auth.failure` audit events. `IdentityUser.synthetic_password` added via migration
  `ae25b1ea2ef9`.
- `GET /mission-data/records/{id}?actor_user_id=...` — writes `record.access` audit events.
- `GET /audit` and `GET /telemetry` now support `?since=<ISO8601>&limit=<n>` ascending polling.
- `POST /lab/telemetry/{asset_id}/inject` — controlled synthetic telemetry for testing anomaly
  detection, lab-secret gated like every other `/lab/*` endpoint.
- 6 new integration tests in `tests/integration/test_missionnet_auth_and_access.py`, all passing
  against the real Postgres `missionnet` database.

**Sentinel's own persistence** (`domain/models/orm.py`, migrated via
`infrastructure/migrations/sentinel`, applied to the real `sentinel` database — verified with
`\dt` showing all 9 tables + `alembic_version`):
`raw_events`, `assets`, `normalized_events`, `detections`, `detection_event_links`, `incidents`,
`incident_detection_links`, `incident_event_links`, `ingestion_cursors`.

**Event source adapter boundary** (`services/event_ingestor/ports.py` — vendor-neutral
`EventSourceAdapter` Protocol) with `integrations/missionnet/adapter.py` (real HTTP polling, two
stream instances) and `integrations/missionnet/mapper.py` (SOURCE → NORMALIZER → CANONICAL,
13 passing unit tests in `tests/unit/test_missionnet_mapper.py` covering every audit action,
telemetry severity thresholds, and rejection of unknown event types).

**Ingestion service** (`services/event_ingestor/service.py`): idempotent (verified — a second
`make ingest-once` against unchanged MissionNet data ingests 0 new events), cursor-tracked per
`(source, stream)`, preserves raw payload + SHA-256 hash before any normalization. Fixed a real
SQLAlchemy flush-ordering bug along the way (recorded in DECISIONS.md so it isn't rediscovered).
`sync_missionnet_assets` upserts Sentinel's own `assets` table from MissionNet's `/assets`.

**Deterministic detection engine** (`services/detection_engine/`): 6 rules (DET-001 through
DET-006, see `docs/detection-engine.md`) as pure, DB-free functions — 13 passing unit tests
(`tests/unit/test_detection_rules.py`) covering fire/no-fire/window-boundary/no-cross-contamination
for every rule. Idempotent via a `dedupe_key` on each `Detection` row.

**Incident correlation engine** (`services/incident_engine/`): merges related open detections by
`correlation_key` (asset or identity) within a 10-minute window into `Incident` rows with real
relational evidence links (`docs/incident-correlation.md`). No AI anywhere in this decision.

**Sentinel API** (`apps/api/routes.py`): `/api/v1/assets[/{id}]`, `/api/v1/events[/{id}]`
(filterable by severity/source/asset_id/since/until), `/api/v1/detections[/{id}]`,
`/api/v1/incidents[/{id}]` (detail includes full evidence — linked detections and their exact
source events), `/api/v1/metrics/summary`. All curl-verified against real ingested data.

**Sentinel dashboard**: Mission Cyber Posture overview (protected assets, event/detection/incident
counts, severity distribution, MissionNet connectivity, last ingestion time, explicit
`External AI API: disabled`), Live Incidents table, Incident Detail page with separate
**Observed Evidence** / **Deterministic Detections** / **Incident Correlation** sections and an
explicit **"AI Analyst: NOT ENABLED — scheduled for a later phase"** placeholder. Verified via
`tsc --noEmit`, `eslint`, and a live browser walkthrough (screenshotted) showing a real 3-detection,
1-incident correlation produced by genuine MissionNet activity.

**One real end-to-end run, exactly as specified in the Phase 2 end-state:**
1. `make reset-lab` → MissionNet nominal, Sentinel has no data.
2. `POST /lab/state/mission-data-api-01/degrade` + `POST /lab/telemetry/.../inject` (both real
   MissionNet lab-control calls, not Sentinel-internal).
3. `make ingest-once` → MissionNet's genuine audit+telemetry rows ingested, normalized, 3 detections
   created (DET-002, DET-004, DET-005), correlated into **1** incident (1 created, 2 merged-in).
4. `GET /api/v1/incidents` and the dashboard both show it with severity `high`, category
   `asset-degradation`, and evidence tracing back to the exact 2 source events.
5. Re-running `make ingest-once` created 0 new events/detections/incidents (idempotency proven).
6. `make reset-lab` again + repeating step 2-3 reproduced the identical result
   (`test_reset_lab_and_sentinel_reset_reproduce_identical_result`).

**Tests**: 58 passing total (`'.venv/bin/pytest -q'`) — 26 unit (13 mapper + 13 rules, both DB-free)
+ 32 integration (24 pre-existing MissionNet/Phase-0-1 + 5 new full-pipeline end-to-end tests in
`tests/integration/test_sentinel_ingestion_pipeline.py`, covering: full pipeline detection, ingestion
idempotency, benign-activity-creates-nothing, multi-signal correlation-into-one-incident, and
reset-then-reproduce). `ruff check .` and `mypy apps domain services integrations` both clean.
`tsc --noEmit` and `eslint` clean on both frontend apps. Full `scripts/healthcheck.sh` passes,
including new "Sentinel DB migration applied" and existing checks.

### Phase 2 Definition of Done (continuation prompt §16) — all 15 items verified
- [x] Sentinel observes real MissionNet-produced events (real HTTP polling, not DB access).
- [x] MissionNet source events convert into canonical `NormalizedEvent`/`NormalizedEventRecord`.
- [x] Ingestion is idempotent (proven by test and by manual re-run).
- [x] Source provenance retained (`raw_events` with SHA-256, referenced by every normalized event).
- [x] Deterministic rules create detections (6 rules, all rule tests pass).
- [x] Rule tests pass (13/13).
- [x] Related detections/events become an incident (correlation engine, tested).
- [x] Incident contains real evidence links (relational link tables, not JSON blobs).
- [x] Sentinel API exposes events, detections, incidents, and assets.
- [x] Sentinel dashboard renders actual backend information (verified live in-browser).
- [x] One controlled MissionNet state/action produces a visible Sentinel incident end-to-end.
- [x] No AI is involved in deciding whether the detection or incident exists.
- [x] The complete prior test suite still passes (58/58, including all Phase 0/1 tests).
- [x] Ruff/mypy/TypeScript checks pass.
- [x] Documentation updated (this file, DECISIONS.md, RUNBOOK.md, docs/data-contracts.md, plus new
      docs/detection-engine.md and docs/incident-correlation.md).

### Next task
Phase 3 — Demo & Scenario Control Plane. Build `services/scenario_controller`: a scenario
catalog/API that starts named scenarios (SCN-001, and a first version of SCN-010) by calling
MissionNet's real lab-control endpoints and emitting/replaying timed events — never by directly
creating a Sentinel incident/detection/event. Acceptance target: starting a scenario changes
MissionNet state and emits events; Sentinel independently detects/correlates them through the exact
pipeline built in Phase 2; the Demo Control Plane discovers the resulting incident only through
Sentinel's own API.

## Phase acceptance status

| Phase | Acceptance criteria met? |
|---|---|
| 0 — Repo/bootstrap/contracts | **Yes — verified** |
| 1 — MissionNet real app | **Yes — verified** |
| 2 — Sentinel event/detection/incident | **Yes — verified** |
| 3 — Demo Control + SCN-010 causality | Not started |
| 4 — Sentinel dashboard | Partially done ahead of schedule (Overview + Incidents + Incident Detail landed in Phase 2 to prove the causal chain visually; posture polish/SSE still open) |
| 5 — Local AI analyst + RAG | Not started |
| 6 — Playbooks/policy/approval | Not started |
| 7 — Deterministic response + verification (MVP stopping point) | Not started |
| 8 — Real sensors + SIEM portability | Not started |
| 9 — Validation/coverage/offline hardening | Not started |
| 10 — Model benchmarking | Not started |
