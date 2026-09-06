# Scenario / Demo Control Plane

The third deliverable (blueprint §17). Orchestrates demonstrations by driving MissionNet through its
own approved APIs and observing whatever Sentinel independently produces - it never writes to
Sentinel directly. See `DECISIONS.md` ("Proof the Scenario Controller cannot create Sentinel
incidents/detections directly") for the safety-boundary argument in full.

## Architecture

```
apps/demo_control/
    config.py       settings: MissionNet/Sentinel base URLs, lab secret, poll interval/timeout
    db.py           Demo Control's own Postgres database ("democontrol")
    models.py       ScenarioRun (one row per run, JSON columns for step results/observed IDs)
    scenarios.py    Pydantic ScenarioDefinition schema + YAML loader (cyber-range/scenarios/*.yaml)
    actions.py      one function per scenario step action - each makes exactly one MissionNet HTTP call
    verification.py derives PASS/FAIL from Sentinel's real read APIs (never hard-coded)
    runner.py       the execution state machine tying the above together
    routes.py       FastAPI endpoints
    main.py         app + CORS (the console, :3200, calls this API from browser JS)
```

## Execution flow

```
PENDING -> PREPARING -> RUNNING -> WAITING_FOR_TELEMETRY -> WAITING_FOR_SENTINEL -> VERIFYING
    -> PASSED | FAILED
    (CANCELLED reachable from any non-terminal state)
```

1. **PREPARING**: check MissionNet and Sentinel are reachable; reset the lab if the scenario says to
   (`reset.strategy: lab_reset`, which every shipped scenario uses); verify preconditions
   (`missionnet_status`); capture a baseline of existing Sentinel detection/incident IDs.
2. **RUNNING**: execute each scenario step in order via `actions.py` - real HTTP calls to MissionNet's
   public or `/lab/*` API, never anything else.
3. **WAITING_FOR_TELEMETRY**: poll MissionNet's `/audit` and `/telemetry` (`?since=<run start>`) until
   every `expected_observations.missionnet` entry is satisfied, bounded by
   `DEMOCONTROL_POLL_TIMEOUT_SECONDS` (default 30s).
4. **WAITING_FOR_SENTINEL**: call `POST /api/v1/ingest/run` on Sentinel (the exact Phase 2 pipeline -
   see DECISIONS.md) and check the result against `expected_observations.sentinel`; repeat on the
   same poll interval/timeout if not yet satisfied.
5. **VERIFYING**: run every check in `verification.py` (see below) and mark PASSED only if all pass.

## Verification checks

| Check | What it means |
|---|---|
| `missionnet_event_observed` | MissionNet produced the expected audit/telemetry record(s). |
| `normalized_event_observed` | Sentinel's ingest produced at least one new `NormalizedEventRecord`. |
| `expected_detection_observed` | Every rule ID the scenario expects appears among newly created detections. |
| `incident_created` | At least `min_count` new incidents exist, matching `primary_asset_id` if specified. |
| `evidence_link_verified` | Every new incident's detail exposes non-empty `event_ids`. |
| `no_duplicate_on_replay` | Running the pipeline again creates zero new detections/incidents. |

All six are derived from real HTTP responses at verification time - see
`apps/demo_control/verification.py`. There is no code path that sets a check to `true` without a
matching API response.

## Scenario format

See `cyber-range/scenarios/SCN-003.yaml` for a minimal example and `SCN-010.yaml` for the flagship
multi-step one. Fields:

- `steps[].action`: one of `auth_failure`, `auth_success`, `degrade_asset`, `quarantine_asset`,
  `restore_asset`, `revoke_token`, `inject_telemetry`, `access_record`, `snapshot_evidence`
  (`apps/demo_control/actions.py` is the authoritative list).
- `steps[].target` + `repeat`: call the same target N times (e.g. an auth-failure burst).
- `steps[].targets`: call once per item in the list (e.g. spreading record access across five records).
- `expected_observations.missionnet`: what MissionNet should show (`event_type`, optional `asset_id`,
  `count`).
- `expected_observations.sentinel.detections[].rule_id`: which DET-* rules must fire. **Note:** these
  reference the real shipped catalog (`docs/detection-engine.md`), not the original blueprint's
  suggested numbering - see DECISIONS.md if a scenario's rule ID looks surprising relative to its name.
- `expected_observations.sentinel.incidents`: `min_count` and optional `primary_asset_id`.
- `reset.strategy`: `lab_reset` (default, used by every shipped scenario) or `none`.

## Adding a scenario

1. Write `cyber-range/scenarios/SCN-0XX.yaml`.
2. If it needs a MissionNet action not in `actions.py`, add one function there - it must be a single
   real HTTP call to MissionNet's public or lab-control API, nothing else.
3. Add it to the parametrized list in `tests/unit/test_demo_control_scenarios.py`.
4. Run it (`POST /api/v1/scenarios/SCN-0XX/run`, poll `GET /api/v1/runs/{id}`) and confirm PASSED with
   real IDs before considering it done.
