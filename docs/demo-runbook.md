# Live demo runbook

Repeatable steps for running the SCN-010 flagship demo live, per blueprint §30 and the Phase 3
end-to-end validation requirement.

## Start the full stack

```bash
make dev-up                # Postgres in Colima
make api                   # Sentinel API :8080          (separate terminal)
make missionnet             # MissionNet API :8090         (separate terminal)
make demo-control            # Demo Control API :8100       (separate terminal)
make dashboard              # Sentinel dashboard :3000     (separate terminal)
make missionnet-console     # MissionNet console :3100     (separate terminal)
make demo-control-console   # Demo Control console :3200   (separate terminal)
make health                 # confirm everything is up
```

## Open three browser tabs

1. **Demo Control** — http://127.0.0.1:3200 (the one you drive from)
2. **MissionNet Operations Console** — http://127.0.0.1:3100
3. **Sentinel SOC Dashboard** — http://127.0.0.1:3000

## Run a simple scenario first (SCN-001 or SCN-003)

1. In Demo Control, click **Run Scenario** on SCN-003 ("Mission-Critical Asset Degradation").
2. You land on the run page; the live timeline updates every 1.5s with real execution events.
3. Within a few seconds it should read **PASSED**, all 6 verification checks green.
4. Switch to the MissionNet tab and refresh — `mission-data-api-01` shows degraded, overall status
   DEGRADED.
5. Switch to the Sentinel tab, click **Live Incidents** — the new incident is there with severity
   `high`, category `asset-degradation`. Open it to see Observed Evidence / Deterministic Detections
   / Incident Correlation, and the honest **"AI Analyst: NOT ENABLED"** label.

## Run the flagship (SCN-010)

1. Back in Demo Control, click **Run Scenario** on SCN-010 (marked "Flagship").
2. Watch the timeline: 3 auth failures, a token revoke, a record access, an asset degrade, a
   telemetry injection — each a real MissionNet call, each logged the moment it happens.
3. It should reach PASSED with **5 detections** and **at least 3 incidents** (the tool does not force
   everything into one incident — DET-001 and DET-006 land in their own incidents because they're
   keyed by identity, not the shared asset that DET-002/DET-004/DET-005 correlate on).
4. Click through to any resulting incident from the run page's "Resulting Incidents" section.

## Verify reproducibility

1. From the run page, click **Reset Lab**.
2. Confirm MissionNet's console shows NOMINAL again.
3. Run SCN-010 again from Demo Control's home page.
4. It should PASS again with the same shape (5 detections, ≥3 incidents) but **different IDs** — the
   reset genuinely cleared prior state rather than reusing it.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Scenario stuck in WAITING_FOR_TELEMETRY | MissionNet unreachable or a lab-control call failed | Check `make health`; check the run's `step_results` for the failing step's HTTP response |
| Scenario stuck in WAITING_FOR_SENTINEL | Sentinel API down, or the expected rule genuinely didn't fire | Check `curl http://127.0.0.1:8080/api/v1/health`; manually call `POST /api/v1/ingest/run` and inspect the response |
| Run FAILED on precondition | MissionNet wasn't nominal and the scenario didn't reset first | Only relevant for `reset.strategy: none` scenarios (none of the shipped ones use this in normal operation) |
| Buttons on the Demo Control page do nothing | Hydration or CORS issue (see DECISIONS.md) | Confirm `apps/demo-control-console/next.config.ts` has `allowedDevOrigins`, and Demo Control's API has CORS enabled for :3200 |
| `Failed to fetch` shown under a Run button | CORS blocked, or Demo Control API is down | `curl http://127.0.0.1:8100/health` |

## Stop the demo stack

```bash
# Ctrl-C each `make api` / `make missionnet` / `make demo-control` / `make dashboard` /
# `make missionnet-console` / `make demo-control-console` terminal, then:
make dev-down
```
