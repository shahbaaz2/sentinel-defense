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

## Contain it (Phase 7 - the full recommend -> approve -> execute -> verify chain)

Full design: `docs/response-executor.md`, `docs/verification-and-rollback.md`.

1. On the asset-degradation incident (DET-002+DET-004+DET-005 on `mission-data-api-01`), click
   **ANALYZE WITH LOCAL AI** - it recommends **RP-005**. The Response Planning section shows it
   pre-selected as `ELIGIBLE — HUMAN APPROVAL REQUIRED`.
2. Click **CREATE RESPONSE PLAN**, then open the plan's own page. Review all 7 sections (Incident
   Context, Recommended Playbook, Why This Playbook, Planned Actions, Policy Checks, Mission Impact,
   Approval) - nothing has happened to MissionNet yet.
3. Click **APPROVE**. The banner changes to **APPROVED — READY TO EXECUTE (SYNTHETIC MISSIONNET LAB
   ONLY)** and an **EXECUTE APPROVED PLAN** button appears - execution is still a separate action,
   not automatic.
4. Click **EXECUTE APPROVED PLAN** and confirm the dialog. The banner flips to **RESPONSE SUCCEEDED
   — all mandatory actions completed and verified**, and the new **Response Execution** section shows
   the real timeline: `quarantine_workload` SUCCEEDED/VERIFIED, `revoke_test_token` SKIPPED (this
   incident has no identity/token signal), `preserve_evidence` SUCCEEDED/VERIFIED,
   `request_replacement_instance` SUCCEEDED/VERIFIED.
5. Cross-check the containment is real, not just claimed:
   - MissionNet Operations Console (:3100): system status **CONTAINMENT_IN_PROGRESS**,
     `mission-data-api-01` shown `quarantined`, a new `mission-data-api-01-replacement` asset shown
     `nominal`.
   - Incident Detail: `Containment: VERIFIED`, and the incident's own status is still whatever it was
     before (execution never auto-resolves an incident).
   - Response Center (`?view=COMPLETED`): the plan is bucketed there with a **ROLLBACK** action
     available (the plan is `reversible`).
   - Audit / Provenance: the full `response_plan.execution_started` -> `action_started`/
     `action_result`/`action_verified` (×4) -> `execution_succeeded` chain.
6. Optionally, click **ROLLBACK** on the Response Center or Plan Detail page to restore
   `mission-data-api-01` to `nominal`/`normal` and confirm the console reflects it - rollback for
   actions with no handler (`preserve_evidence`, `request_replacement_instance`) correctly shows
   `NOT_APPLICABLE`, not a false claim of reversal.

## Verify reproducibility

1. From the run page, click **Reset Lab**.
2. Confirm MissionNet's console shows NOMINAL again.
3. Run SCN-010 again from Demo Control's home page.
4. It should PASS again with the same shape (5 detections, ≥3 incidents) but **different IDs** — the
   reset genuinely cleared prior state rather than reusing it.

## Real network sensors: SCN-NET-001 (Phase 8)

Full design: `docs/sensor-pipeline.md`, `docs/integrations.md`. Requires Docker (via Colima) and
`SENTINEL_SURICATA_ENABLED=true` / `SENTINEL_ZEEK_ENABLED=true` in `.env` (both default `false` -
see `RUNBOOK.md`'s "Network sensor pipeline" section for enabling them). This scenario touches no
MissionNet state at all - it proves Sentinel's real-sensor path independently of the MissionNet lab.

1. From Demo Control's home page, click **Run Scenario** on **SCN-NET-001** ("Network Sensor
   Detection"). It takes roughly 10-15 seconds - real Docker containers actually run: an isolated
   bridge network with a server/DNS-stub/client, a captured pcap, then real Suricata and real Zeek
   analyzing it in batch mode.
2. It should reach **PASSED** with 3+ detections (`NET-001`, `NET-002`, `NET-003`) and exactly one
   incident, category `network-intrusion`.
3. Open the resulting incident - `NET-003`'s presence proves genuine Suricata+Zeek cross-sensor
   correlation, not just two sensors ingested side by side.
4. Open http://127.0.0.1:3000/data-sources - Suricata and Zeek should read `ACTIVE` with a nonzero
   event count and a recent "Last Successful Ingest" timestamp.
5. Open http://127.0.0.1:3000/events?source=suricata (or `?source=zeek`) - Event Explorer's Rule
   and Src → Dst columns show the real signature ID and IP pair from the actual pcap capture.
6. **Reproducibility**: run SCN-NET-001 again - it resets first (clearing both the DB and the
   generated `eve.json`/Zeek logs - see DECISIONS.md), then PASSes again with disjoint IDs.
7. **Regression check**: run SCN-010 again afterward - it should show exactly its own 5 detections,
   with no stray `NET-*` detections left over from the sensor run (the same reset guarantee).

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Scenario stuck in WAITING_FOR_TELEMETRY | MissionNet unreachable or a lab-control call failed | Check `make health`; check the run's `step_results` for the failing step's HTTP response |
| Scenario stuck in WAITING_FOR_SENTINEL | Sentinel API down, or the expected rule genuinely didn't fire | Check `curl http://127.0.0.1:8080/api/v1/health`; manually call `POST /api/v1/ingest/run` and inspect the response |
| Run FAILED on precondition | MissionNet wasn't nominal and the scenario didn't reset first | Only relevant for `reset.strategy: none` scenarios (none of the shipped ones use this in normal operation) |
| Buttons on the Demo Control page do nothing | Hydration or CORS issue (see DECISIONS.md) | Confirm `apps/demo-control-console/next.config.ts` has `allowedDevOrigins`, and Demo Control's API has CORS enabled for :3200 |
| `Failed to fetch` shown under a Run button | CORS blocked, or Demo Control API is down | `curl http://127.0.0.1:8100/health` |
| Execution ends `FAILED`/`ROLLED_BACK` with a 404-shaped error in an action's `error_message` | MissionNet's `uvicorn` process predates a new `/lab/*` endpoint (no `--reload`) | Restart it: `lsof -ti :8090 \| xargs kill -9`, then `make missionnet` |
| EXECUTE button returns 503 | `SENTINEL_RESPONSE_EXECUTION_ENABLED=false` (kill switch) | Set it `true` in `.env` and restart `make api` |
| SCN-NET-001 fails with a `SensorLabError` | Docker/Colima not running, or a leftover container from a killed prior run | `docker info`; `docker rm -f sentinel-lab-server sentinel-lab-dns sentinel-lab-client; docker network rm sentinel-sensor-lab` |
| SCN-NET-001 step succeeds but no detections appear | `SENTINEL_SURICATA_ENABLED`/`SENTINEL_ZEEK_ENABLED` still `false` | Set both `true` in `.env` and restart `make api` before running the scenario |

## Stop the demo stack

```bash
# Ctrl-C each `make api` / `make missionnet` / `make demo-control` / `make dashboard` /
# `make missionnet-console` / `make demo-control-console` terminal, then:
make dev-down
```
