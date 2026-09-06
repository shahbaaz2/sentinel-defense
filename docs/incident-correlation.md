# Incident correlation

"Detections are not incidents" (blueprint §9). `services/incident_engine/engine.py` merges related,
still-open, not-yet-linked `Detection` rows into `Incident` rows using only deterministic
attributes - never an LLM judgment call.

## Algorithm

1. Load every `Detection` with `status == "open"` that has no row in `incident_detection_links` yet
   (`_unlinked_open_detections`).
2. Process them oldest-first, so an incident's timeline reads in the order things actually
   happened.
3. For each detection, compute its `correlation_key` (set by the detection engine as
   `asset_id or user_id` - whichever the triggering rule populated). This is what lets
   identity-centric rules like DET-001/DET-003/DET-006 correlate by identity, and asset-centric
   rules like DET-002/DET-004/DET-005 correlate by asset, without conflating the two.
4. Look for an existing, still-open `Incident` with the same `correlation_key` whose `last_seen` is
   within `CORRELATION_WINDOW` (10 minutes) of this detection's timestamp.
   - **Found:** attach (`IncidentDetectionLink`), bump `last_seen`/severity (max, not overwrite)/
     union the ATT&CK techniques, and copy the detection's evidence events into
     `IncidentEventLink` so the API can expose exact source evidence without a two-hop join.
   - **Not found:** create a new `Incident` seeded from this detection's rule
     (`title`/`category`/`severity`/`summary` all come from the triggering rule and detection, not
     invented).

## Why this, and not the full blueprint §9.4 state machine yet

Phase 2 incidents only ever land in `status = "new"` - there's no human triage, AI assessment, or
response yet to move them further, so implementing `triage -> investigating -> awaiting_approval ->
...` now would be dead code. The `status` column and the values are already blueprint-compliant;
later phases add the transitions, not a new column.

## What this proves, concretely

In the Phase 2 end-to-end test (`test_multi_signal_correlation_merges_into_one_incident` and the
manual verification run recorded in PROGRESS.md), degrading `mission-data-api-01` and then
injecting anomalous telemetry on the same asset within the correlation window produces **three**
detections (DET-002, DET-004, DET-005) that the engine merges into **one** incident - not three
separate alerts an analyst would have to manually connect.

## Known limitation

Merge decisions only look at the single most-recently-updated open incident per correlation key via
a `.order_by(last_seen.desc())` scan, not a full window-aware graph merge. For Phase 2's event
volumes (hundreds, not millions, per blueprint §28.1) this is correct and fast enough; if two
disjoint "bursts" for the same asset happen far enough apart that a third burst's window bridges
both, only the most recent one is considered for merging. Revisit if that scenario becomes a real
demo requirement.
