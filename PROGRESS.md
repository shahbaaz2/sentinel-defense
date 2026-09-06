# PROGRESS

Current phase, what is actually verified working (not just present), and the next task. Update this at
every phase checkpoint — never claim something works without having run the check.

## Current phase: Phase 1 — COMPLETE (all acceptance criteria verified)

### Phase 0 recap (see git history for full detail)
Repo scaffold, Sentinel API shell, MissionNet API shell, Sentinel dashboard shell, PostgreSQL in
Colima — all verified end-to-end. `make dev-up` / `make health` / `make test` pass.

### Phase 1 — verified working
- **Data layer**: `apps/missionnet/models.py` — `Asset`, `IdentityUser`, `ServiceToken`,
  `MissionRecord`, `TelemetrySample`, `AuditEvent`. Migrated via Alembic
  (`infrastructure/migrations/missionnet`), applied to the real `missionnet` Postgres database —
  verified with `\dt` showing all 6 tables + `alembic_version`.
- **Seed/reset**: `apps/missionnet/seed.py` (`python -m apps.missionnet.seed --reset`) creates the
  deterministic baseline: 10 assets, 8 users, 3 service tokens, 15 mission records, 2 telemetry
  samples, one `seed.reset` audit event. Counts verified in range per blueprint §7.6
  (8-15 / 6-10 / 3-5 / 10-30). `scripts/reset-lab.sh` calls this and was run directly — confirmed it
  restores the exact baseline after a mutation.
- **Public read API** (`apps/missionnet/routes.py`): `/assets`, `/assets/{id}`, `/identity/users`,
  `/identity/tokens`, `/mission-data/records`, `/telemetry`, `/audit`, `/state` — all curl-verified.
- **Lab-control API** (`apps/missionnet/lab.py`), header-secret gated:
  `/lab/reset`, `/lab/state/{id}/degrade`, `/lab/tokens/{id}/revoke`,
  `/lab/assets/{id}/quarantine`, `/lab/assets/{id}/restore`, `/lab/evidence/snapshot`,
  `GET /lab/state`. Verified: missing/wrong secret → 403; unknown asset → 404; a degrade call
  changes `/health` status to `degraded` **and** appears in `/audit` with correct
  `actor_type`/`actor_id`/`scenario_id` attribution; quarantine → restore round-trips cleanly;
  `/lab/reset` clears a mutation back to the nominal baseline.
- **Computed system state** (`apps/missionnet/state.py`): `nominal -> degraded ->
  containment_in_progress -> recovering` derived live from asset rows, never hard-coded. Verified via
  the degrade/quarantine/restore tests above.
- **Operations Console UI** (`apps/missionnet-console`): renders live Mission System Status badge,
  per-role service cards (Identity/Gateway/Mission Data/Comms/Operator Console/Telemetry), a full
  asset table, and the 10 most recent audit events — all server-fetched from the real API, no mock
  data. Verified two ways: (1) curl showing the live values embedded in the rendered HTML, (2)
  browser screenshot before and after triggering a real `/lab/state/.../degrade` call, showing the
  status badge and service dot flip from green/NOMINAL to amber/DEGRADED live.
- **Tests**: 21 passing (`'.venv/bin/pytest -q'`) — 13 unit (unchanged from Phase 0) + 8 new
  integration tests in `tests/integration/test_missionnet_lab_api.py` running against the real
  Postgres `missionnet` database (marked `@pytest.mark.integration`, requires `make dev-up`).
- `ruff check .` and `mypy apps/missionnet domain` both clean. `tsc --noEmit` clean on both frontend
  apps. Full `scripts/healthcheck.sh` passes, including a new "MissionNet DB migration applied" check.

### Known fix applied during Phase 1 (recorded so it isn't rediscovered)
- SQLAlchemy's default pooled `create_async_engine` breaks under pytest-asyncio's per-test event
  loops (`RuntimeError: ... attached to a different loop`) because pooled asyncpg connections stay
  bound to whichever loop first created them. Fixed by using `NullPool` for the MissionNet engine
  (`apps/missionnet/db.py`) — a fresh connection per checkout. Fine at this prototype's scale; revisit
  if connection-churn overhead ever matters.

### Phase 1 acceptance criteria (blueprint §26) — all met
- [x] MissionNet runs independently from Sentinel (no Sentinel API involved anywhere above).
- [x] Console shows seeded synthetic assets/services with real backend health state.
- [x] `make reset-lab` returns MissionNet to the exact seed baseline.
- [x] At least one state change (asset degrade) is visibly reflected in both the MissionNet UI and
      its audit stream.

### Next task
Begin **Phase 2 — Sentinel event/detection/incident foundation**: `NormalizedEvent` ingest from
MissionNet's `audit_events`/`telemetry_samples` (already curl-verified as a live source), raw-event
storage with SHA-256 hash, Sentinel's own Postgres schema (events/detections/incidents per blueprint
§10), the first deterministic correlation rules (§9.3), and the incident state machine (§9.4).
Acceptance target: a real MissionNet audit event reaches Sentinel through normal ingestion with no AI
involved, synthetic anomaly fixtures create the expected incident/evidence IDs, and benign activity
does **not** create a high-severity incident.

## Phase acceptance status

| Phase | Acceptance criteria met? |
|---|---|
| 0 — Repo/bootstrap/contracts | **Yes — verified** |
| 1 — MissionNet real app | **Yes — verified** |
| 2 — Sentinel event/detection/incident | Not started |
| 3 — Demo Control + SCN-010 causality | Not started |
| 4 — Sentinel dashboard | Not started |
| 5 — Local AI analyst + RAG | Not started |
| 6 — Playbooks/policy/approval | Not started |
| 7 — Deterministic response + verification (MVP stopping point) | Not started |
| 8 — Real sensors + SIEM portability | Not started |
| 9 — Validation/coverage/offline hardening | Not started |
| 10 — Model benchmarking | Not started |
