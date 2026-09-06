# RUNBOOK

## Start

```bash
make bootstrap    # first time only, or after switching machines
make dev-up       # starts Colima, PostgreSQL, MissionNet
make api          # foreground: FastAPI on :8080
make dashboard    # foreground, separate terminal: Sentinel dashboard on :3000
```

MissionNet's own dashboard runs on :3100 (`make missionnet-console`). Demo Control's API runs on
:8100 (`make demo-control`) and its console on :3200 (`make demo-control-console`). Full walkthrough
of a live demo, including SCN-010, is in `docs/demo-runbook.md`.

## Run the Sentinel ingestion pipeline

Sentinel does not ingest automatically yet - run it manually or watch continuously:

```bash
make ingest-once     # sync assets, ingest audit+telemetry, run detection + correlation, then exit
make ingest-watch     # same, every 5s (Ctrl-C to stop)
```

Both require the Sentinel API's database to be migrated (`make migrate-sentinel`, done automatically
by `make bootstrap`) and MissionNet's API reachable at `MISSIONNET_BASE_URL`
(default `http://127.0.0.1:8090`).

## Create a Phase 2 test event and verify detection/incident

```bash
# 1. Baseline
make reset-lab

# 2. Cause a genuine MissionNet signal (pick any lab-control call, e.g.):
curl -s -X POST -H "X-Lab-Secret: dev-only-lab-secret-change-me" \
  -H "Content-Type: application/json" -d '{"reason":"manual test"}' \
  http://127.0.0.1:8090/lab/state/mission-data-api-01/degrade

# 3. Run the pipeline
make ingest-once

# 4. Verify
curl -s http://127.0.0.1:8080/api/v1/incidents | python3 -m json.tool
```

Expect one `high`-severity incident with `category: asset-degradation`, whose
`/api/v1/incidents/{id}` detail lists the exact detection(s) and source event(s) that caused it.
Re-running `make ingest-once` immediately afterward must create zero new detections/incidents
(idempotency) - see `docs/detection-engine.md` and `docs/incident-correlation.md`.

`make sentinel-reset` clears only Sentinel's ingested/derived state (events, detections, incidents,
cursors, synced assets) without touching MissionNet - useful when iterating on rules without
wanting to reseed MissionNet each time. `make reset-lab` now runs both resets together.

## Run a scenario through Demo Control

With MissionNet, Sentinel, and Demo Control all up (`make missionnet`, `make api`,
`make demo-control`):

```bash
curl -s -X POST -H "Content-Type: application/json" -d '{}' \
  http://127.0.0.1:8100/api/v1/scenarios/SCN-001/run
# -> {"run_id": "RUN-...", "status": "PENDING", ...}

curl -s http://127.0.0.1:8100/api/v1/runs/RUN-<id> | python3 -m json.tool
# poll until "status" is PASSED or FAILED (2-5 seconds for any shipped scenario)
```

Or drive it visually from http://127.0.0.1:3200 (`make demo-control-console`) - see
`docs/demo-runbook.md` for the full live-demo walkthrough including the SCN-010 flagship.

`make reset-demo` runs `make reset-lab` (MissionNet + Sentinel) and additionally clears Demo
Control's own scenario-run history.

## SOC operator walkthrough (Phase 4)

With MissionNet, Sentinel API, Demo Control, and the Sentinel dashboard all up
(`make missionnet`, `make api`, `make demo-control`, `make dashboard`):

1. **Run a scenario and watch it land live.** Trigger any scenario (see "Run a scenario through
   Demo Control" above) and open http://127.0.0.1:3000 — the Overview page updates within a couple
   of seconds via its SSE connection, with no manual refresh. Open the Live Incidents page
   (http://127.0.0.1:3000/incidents) to see the resulting incident(s).

2. **Investigate an incident.** Click into an incident from either the Overview's Recent Incidents
   table or the Incidents list. The detail page shows, in order: the summary cards, the raw
   observed evidence (with links to each event's full raw payload), the deterministic detections
   that fired, a plain-language explanation of why they were correlated together, the (currently
   disabled) AI Analyst placeholder, the analyst workflow panel, and a provenance section linking to
   the audit trail.

3. **Update incident status/assignment/disposition.** In the Analyst Workflow panel (section F):
   change the Status dropdown to progress OPEN → INVESTIGATING → MONITORING → RESOLVED/DISMISSED;
   type an analyst name into the Assigned Analyst field and click Save; add free-text notes; set a
   Disposition once you've determined the truth of the incident. Each change is a direct
   PATCH/POST to Sentinel's API and takes effect immediately (confirmed by the Summary card updating
   after each save).

4. **Verify provenance.** Every workflow change above writes a row to `audit_log`. Open
   http://127.0.0.1:3000/audit and filter by `entity_id=<incident_id>` (or follow the "Full audit
   trail" link from the incident's Provenance section) to see the complete history — status changes,
   assignment, notes, disposition, and the original `incident.created`/`incident.detection_merged`
   entries from when Sentinel's detection engine correlated it, each with the real `scenario_id` and
   before/after values in `detail`.

5. **Check detection coverage honestly.** http://127.0.0.1:3000/detection-coverage shows all 6
   shipped rules; a rule only shows VALIDATED once a real Demo Control scenario run has actually
   triggered it — run more scenarios (or `SCN-004` specifically, which is the only one currently
   mapped to DET-003) to move rules out of NOT_TESTED.

6. **Check deployment truthfulness.** http://127.0.0.1:3000/assurance reports real reachability
   checks for every component and integration — anything not yet built (Wazuh, Splunk, an AI
   analyst) reads `NOT_CONFIGURED`/`NOT ENABLED` rather than being hidden or faked.

7. **Reset for the next walkthrough.** `make reset-demo` (see below) returns MissionNet, Sentinel,
   and Demo Control's run history to a clean seeded baseline.

## Stop

```bash
make dev-down     # stops containers, leaves Colima running
colima stop       # stops the Colima VM entirely
```

## Reset the lab

```bash
make reset-lab
```

Restores MissionNet to its seeded baseline, clears incidents/executions/scenario runs, and preserves
knowledge/rule/policy bundles and the cached model. Never hand-edit the database to "reset" it — always
go through migrations + the seed script so the state is reproducible.

## Health check

```bash
make health
```

Runs `scripts/healthcheck.sh`, which checks PostgreSQL connectivity, API `/health`, dashboard HTTP
response, MissionNet health, the local model endpoint (once Phase 5 is enabled), migration version, and
that a knowledge/policy bundle is present. Exits non-zero on any critical failure.

## Offline check

```bash
make offline-check
```

Disables external AI base URLs, confirms the local model endpoint responds, confirms Postgres/containers
are local, confirms knowledge/rules are present, and runs one scenario end to end with no external
network dependency required.

## Troubleshooting

### Colima will not start
```bash
colima status
```
Check available disk/memory (`df -h ~`). Reduce the allocation in `scripts/dev-up.sh` for this machine's
Lite profile if needed, then `colima stop && colima start`. Do not delete the Colima VM while debugging —
capture logs first (`colima ssh -- dmesg` or `~/.colima/_lima/colima/*.log`).

### Docker CLI cannot reach Colima
Confirm Colima is running and the active Docker context is `colima` (`docker context ls`). Colima
normally activates its own context automatically on `colima start`.

### MLX model is slow or runs out of memory
Confirm the 4-bit quantized model is selected (`SENTINEL_LLM_MODEL` in `.env`). Shorten the evidence pack
or reduce max tokens before reaching for a larger model. Stop any heavy sensor profile that's running
concurrently. Do not swap to an 8B model on this 16 GB machine merely for cybersecurity specialization —
benchmark it first (Phase 10).

### Wazuh (or any Phase 8 sensor) consumes too much memory
Stop that sensor's optional Compose profile. The system must remain functional with sensors marked
`unavailable` — detection and incident handling continue on synthetic/fixture adapters alone.

### Database schema drift
Never hand-edit tables. Use Alembic migrations only (`infrastructure/migrations`). For a broken dev DB,
`make reset-lab` recreates the seeded state from scratch.

Apply migrations: `make migrate-missionnet` / `make migrate-sentinel` / `make migrate-democontrol`
(each equivalent to `alembic -c infrastructure/migrations/<app>/alembic.ini upgrade head`). To
create a new one after changing `apps/missionnet/models.py`, `domain/models/orm.py`, or
`apps/demo_control/models.py`:
```bash
.venv/bin/alembic -c infrastructure/migrations/missionnet/alembic.ini revision --autogenerate -m "..."
.venv/bin/alembic -c infrastructure/migrations/sentinel/alembic.ini revision --autogenerate -m "..."
.venv/bin/alembic -c infrastructure/migrations/demo_control/alembic.ini revision --autogenerate -m "..."
```
Always review the autogenerated file before applying it — Alembic's diff is a starting point, not a
guarantee. In particular, check whether a new non-nullable column needs a `server_default` for
existing rows (autogenerate never adds one automatically).

### Demo won't reset cleanly
`make reset-lab` should fully restore MissionNet's seed state and clear scenario/incident/execution
records for the next run. If it doesn't, that's a bug — fix the reset path rather than manually patching
the database before a demo.
