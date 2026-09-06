# PROGRESS

Current phase, what is actually verified working (not just present), and the next task. Update this
at every phase checkpoint — never claim something works without having run the check.

## Current phase: Phase 3 — COMPLETE (all 19 Definition-of-Done items verified)

### Phase 0-2 recap (see git history for full detail)
Repo scaffold, MissionNet's full synthetic data model + lab-control API + Operations Console,
Sentinel's real ingestion/normalization/deterministic-detection/correlation pipeline with 6 rules
(DET-001..006), Sentinel API + dashboard — all verified end-to-end and committed
(`0fa4286`, `3e7618e`, `43525c8`).

### Phase 3 — verified working

**Demo Control as a fourth, independent product** (`apps/demo_control` backend +
`apps/demo-control-console` frontend, own `democontrol` Postgres database migrated via
`infrastructure/migrations/demo_control` — verified with `\dt` showing `scenario_runs` +
`alembic_version`). Visually distinct dark "mission control" theme from Sentinel's and MissionNet's
light zinc dashboards.

**Five scenario definitions** (`cyber-range/scenarios/SCN-{001,002,003,004,010}.yaml`), declarative
YAML validated by a Pydantic schema (`apps/demo_control/scenarios.py`) at load time. Each targets a
real rule from Phase 2's *actual shipped* DET catalog rather than the original blueprint's numbering
(documented explicitly in DECISIONS.md and in each scenario's own description, since they differ):
SCN-001→DET-001, SCN-002→DET-006, SCN-003→DET-002, SCN-004→DET-003, SCN-010→all five plus the
cross-signal DET-005.

**Action registry** (`apps/demo_control/actions.py`): 9 functions, each exactly one real HTTP call to
MissionNet's public or `/lab/*` API — `auth_failure`, `auth_success`, `degrade_asset`,
`quarantine_asset`, `restore_asset`, `revoke_token`, `inject_telemetry`, `access_record`,
`snapshot_evidence`. No function anywhere in this package writes to Sentinel's tables or fabricates a
MissionNet event.

**Execution engine** (`apps/demo_control/runner.py`): the full state machine (PENDING → PREPARING →
RUNNING → WAITING_FOR_TELEMETRY → WAITING_FOR_SENTINEL → VERIFYING → PASSED/FAILED, CANCELLED
reachable throughout), with every transition persisted immediately so `GET /api/v1/runs/{id}` always
reflects genuine progress. Bounded polling (configurable interval/timeout, no bare `sleep()`) for
both the MissionNet-observation and Sentinel-observation waits.

**Verification engine** (`apps/demo_control/verification.py`): derives all 6 PASS/FAIL checks
(`missionnet_event_observed`, `normalized_event_observed`, `expected_detection_observed`,
`incident_created`, `evidence_link_verified`, `no_duplicate_on_replay`) from Sentinel's real read
APIs, baseline-diffed so it works correctly whether or not the scenario reset first. 21 unit tests
(schema, step-expansion, verification logic against a mocked Sentinel client via
`httpx.MockTransport`) pass with zero live services required.

**Two new Sentinel endpoints** (`apps/api/admin_routes.py`, Phase 3 addition to Sentinel, not Demo
Control): `POST /api/v1/ingest/run` (the exact Phase 2 pipeline, refactored into
`services/event_ingestor/pipeline.py` so `make ingest-once` and this endpoint share one code path)
and `POST /api/v1/admin/reset`. These are the *only* two non-GET calls Demo Control ever makes to
Sentinel, and neither writes an event/detection/incident directly — each invokes Sentinel's own
pre-existing, already-tested logic wholesale.

**Demo Control API** (`apps/demo_control/routes.py`): `GET /api/v1/status`,
`GET /api/v1/scenarios[/{id}]`, `POST /api/v1/scenarios/{id}/run`, `GET /api/v1/runs[/{id}]`,
`GET /api/v1/runs/{id}/timeline`, `GET /api/v1/runs/{id}/verification`,
`POST /api/v1/runs/{id}/cancel`, `POST /api/v1/runs/{id}/reset` — all exercised by curl and by the
integration test suite.

**Demo Control Console** (`apps/demo-control-console`): main screen with live MissionNet/Sentinel/
AI-analyst status, all 5 scenarios with a working **Run Scenario** button; run page with a real live
timeline (polled every 1.5s, entries are exactly what the runner wrote, never client-side
animation), a 6-check verification panel, resulting-incident link-outs to Sentinel's own incident
detail page, and Cancel/Reset Lab controls. Verified with a full browser walkthrough, not just API
calls: clicked **Run Scenario** on SCN-001 and SCN-010, watched both reach PASSED with the exact
timeline shown below, followed a resulting-incident link into Sentinel's dashboard, confirmed
MissionNet's console showed DEGRADED, clicked **Reset Lab** and confirmed MissionNet returned to
NOMINAL via a direct API check.

**Two real bugs found and fixed while building the first interactive frontend in this repo**
(documented in DECISIONS.md so they aren't rediscovered):
1. Next.js 16's `allowedDevOrigins` silently blocked hydration when loaded via `127.0.0.1` instead
   of `localhost` — every button was visually present but inert, no console error. Fixed in all
   three Next.js apps' `next.config.ts`.
2. CORS blocked the console's browser-side fetch to the Demo Control API (different port = different
   origin). Fixed by adding `CORSMiddleware` to `apps/demo_control/main.py`.

### One real, observed SCN-010 flagship run (via the actual browser UI, not just the API)

```
2:31:27 PM  Scenario preparing
2:31:27 PM  Resetting lab to deterministic baseline
2:31:27 PM  MissionNet baseline verified
2:31:27 PM  auth_failure -> j.rivera            (x3)
2:31:28 PM  revoke_token -> tok-svc-mission-data-01
2:31:28 PM  access_record -> rec-000
2:31:28 PM  degrade_asset -> mission-data-api-01
2:31:28 PM  inject_telemetry -> mission-data-api-01
2:31:28 PM  MissionNet actions complete - waiting for audit/telemetry
2:31:29 PM  MissionNet event(s) observed (8)
2:31:29 PM  Triggering Sentinel ingestion
2:31:30 PM  Sentinel normalized event(s) observed
2:31:30 PM  Detection(s) triggered: 5
2:31:30 PM  Incident(s) created: INC-58562424-..., INC-e6317ef4-..., INC-3dad4fc3-...
2:31:30 PM  Evidence links verified
2:31:30 PM  Scenario PASSED
```

All 6 verification checks green. MissionNet's console then showed **DEGRADED** with the Mission Data
service card amber; Sentinel's Live Incidents page showed exactly these 3 incidents — one
`medium`/credential-abuse (DET-001 alone), one `high`/asset-degradation (DET-002+DET-004+DET-005
correlated together, 3 detections on one incident), one `high`/identity-compromise (DET-006 alone).
This is exactly what the deterministic correlation engine should produce given different
correlation keys — the scenario's own YAML documents this expectation and the run reproduced it
exactly, without any hard-coded success. Re-ran SCN-010 after a reset: PASSED again with the same
shape (5 detections, 3 incidents) and entirely new, disjoint IDs — reproducibility confirmed.

### Tests and checks actually run
- **85 tests passing** (`.venv/bin/pytest -q`): 60 unit (39 pre-existing Phase 0-2 + 21 new: 11
  scenario-schema/loader, 4 runner step-expansion, 6 verification-engine-against-mocked-Sentinel,
  the latter using `httpx.MockTransport` so they need zero live services) + 25 integration (19
  pre-existing + 6 new Demo Control end-to-end tests against the real live stack: SCN-003
  full-chain with a cross-check against Sentinel's own API, SCN-010 flagship 5-detection/
  ≥3-incident, SCN-010 reproducibility-after-reset, precondition-failure-reported-as-FAILED,
  cancel-does-not-report-FAILED, reset-endpoint-returns-MissionNet-to-nominal).
- `ruff check .` and `mypy apps domain services integrations` (51 files) both clean.
- `tsc --noEmit` and `eslint` clean on all three Next.js apps (dashboard, missionnet-console,
  demo-control-console).
- Full `scripts/healthcheck.sh` passes, including three new Demo Control checks.

### Phase 3 Definition of Done (continuation prompt §20) — all 19 items verified
- [x] Demo Control exists as a distinct runnable product (own backend, frontend, database, visually
      distinct theme).
- [x] Scenario definitions are declarative (YAML) and versionable (`version` field, `docs/scenario-controller.md`).
- [x] SCN-001, SCN-002, SCN-003, SCN-004, and SCN-010 all exist and pass.
- [x] Scenario actions only go through approved MissionNet public/lab interfaces (`actions.py`).
- [x] Controller cannot directly create Sentinel events/detections/incidents (see DECISIONS.md's
      dedicated proof entry — no import of Sentinel's domain/services modules anywhere in
      `apps/demo_control`).
- [x] Scenario execution state is persisted (`scenario_runs` table, real Postgres).
- [x] Real MissionNet event IDs are captured (`missionnet_event_ids`, from polling `/audit`/`/telemetry`).
- [x] Real Sentinel normalized event IDs are captured (`sentinel_event_ids`, from `/api/v1/events`).
- [x] Real detection IDs are captured (`detection_ids`, baseline-diffed from `/api/v1/detections`).
- [x] Real incident IDs are captured (`incident_ids`, baseline-diffed from `/api/v1/incidents`).
- [x] PASS/FAIL is based on real verification (all 6 checks derived from live API responses).
- [x] Demo Control UI shows live progress (1.5s polling, real timeline entries).
- [x] MissionNet UI reflects scenario state (verified: DEGRADED after SCN-010).
- [x] Sentinel dashboard reflects genuine resulting incident state (verified: 3 real incidents shown).
- [x] SCN-010 passes end to end (verified via browser UI, timeline above).
- [x] Reset restores reproducible baseline (`Reset Lab` button verified via API + MissionNet health).
- [x] SCN-010 passes again after reset (verified, disjoint IDs).
- [x] Existing Phase 0-2 behavior remains intact (85 tests including all prior ones pass).
- [x] All tests/lint/type/health checks pass; documentation updated; clean commit created (below).

### Next task
Phase 4 (already substantially ahead of schedule from Phase 2's dashboard work) or Phase 5 — local
AI analyst + RAG. Whichever is chosen, the same safety boundary applies: the LLM will receive a
curated evidence packet built from exactly the `NormalizedEventRecord`/`Detection`/`Incident` rows
already in Sentinel's database, and will return a schema-validated *assessment*, never a decision
about whether a detection or incident exists — that remains Phase 2's deterministic code, untouched.

## Phase acceptance status

| Phase | Acceptance criteria met? |
|---|---|
| 0 — Repo/bootstrap/contracts | **Yes — verified** |
| 1 — MissionNet real app | **Yes — verified** |
| 2 — Sentinel event/detection/incident | **Yes — verified** |
| 3 — Demo Control + SCN-010 causality | **Yes — verified** |
| 4 — Sentinel dashboard | Overview + Incidents + Incident Detail done (Phase 2); posture polish/SSE pending |
| 5 — Local AI analyst + RAG | Not started |
| 6 — Playbooks/policy/approval | Not started |
| 7 — Deterministic response + verification (MVP stopping point) | Not started |
| 8 — Real sensors + SIEM portability | Not started |
| 9 — Validation/coverage/offline hardening | Not started |
| 10 — Model benchmarking | Not started |
