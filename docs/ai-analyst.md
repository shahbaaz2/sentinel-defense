# AI Analyst (Phase 5)

A local, read-only, advisory second opinion on an already-existing Sentinel incident. It cannot
create, dismiss, or modify anything - deterministic detection and incident correlation
(`services/detection_engine/`, `services/incident_engine/`) still do 100% of that work, exactly as
in Phases 2-4. See `docs/ai-security-boundaries.md` for the trust model this doc assumes.

## Pipeline

```
Real MissionNet activity
  -> Sentinel ingestion (services/event_ingestor)
  -> normalized events (domain/models/orm.NormalizedEventRecord)
  -> deterministic detections (services/detection_engine)
  -> deterministic incident correlation (services/incident_engine)
  -> Evidence Pack (services/ai_analyst/evidence.py)
  -> local LLM (ai/providers/*)
  -> schema-validated + reference-validated assessment (ai/schemas.py, services/ai_analyst/validation.py)
  -> persisted AIAssessment row (domain/models/orm.py)
  -> Incident Detail UI (apps/dashboard/app/incidents/[id]/AIAnalystPanel.tsx)
```

Everything left of "Evidence Pack" is unchanged from Phase 4 and has no idea the AI Analyst exists.

## Evidence Pack

`services/ai_analyst/evidence.py::build_evidence_pack` reads exactly: the incident's own fields,
its linked detections (with their exact event IDs and MITRE techniques), its linked normalized
events (sorted by timestamp), the primary asset's context if one exists, and the union of every
ATT&CK technique ID already attached by deterministic code. No raw table access, no unbounded
query, no playbook catalog yet (`available_playbook_ids` is always `[]` in Phase 5 - see
DECISIONS.md). The pack is hashed (`evidence_pack_hash`, sha256) and that hash is recorded on every
assessment, so two assessments of the same incident can be checked for whether the underlying
evidence actually changed between them.

## Structured output and validation

The model must return a single JSON object matching `ai.schemas.AIIncidentAssessment` - the shape
the blueprint specified almost verbatim (`classification`, `confidence` bounded `[0.0, 1.0]`,
`summary`, `affected_assets`, `evidence_refs`, `detection_refs`, `hypotheses`,
`recommended_investigation_steps`, `attack_techniques`, `recommended_playbook_id`, `limitations`).
Pydantic rejects malformed shape (`extra="forbid"`, bounded confidence); `services/ai_analyst/
validation.py::validate_assessment` then rejects *content* that doesn't exist in the evidence pack
that was actually sent - every `event_id`, `detection_id`, and entry in `affected_assets` must be
copied verbatim from the pack, and `recommended_playbook_id` must be in the (currently always
empty) allowlist or null. A rejected assessment is persisted with `validation_status =
REJECTED_HALLUCINATION` (or `REJECTED_SCHEMA` / `TIMEOUT` / `PROVIDER_ERROR`) and a null
`assessment` body - the dashboard shows the rejection reason, never the fabricated content.

Measured on 14 hand-built evaluation cases (`evaluation/llm/cases.py`) plus the live SCN-010
incident: 100% schema validity, 0% accepted hallucinated references after the `affected_assets`
prompt clarification described in DECISIONS.md (an initial run found the model citing usernames as
"affected assets" on identity-only incidents with no asset context - correctly rejected by
validation, then fixed by tightening the prompt's field semantics rather than loosening
validation).

## API

- `POST /api/v1/incidents/{id}/ai/analyze` - runs one new analysis, persists it, returns it. 503 if
  `SENTINEL_AI_ENABLED=false`. 404 if the incident doesn't exist.
- `GET /api/v1/incidents/{id}/ai/assessment` - the most recent assessment, or `null`.
- `GET /api/v1/incidents/{id}/ai/assessments` - full history, newest first. Re-analysis never
  deletes or overwrites a prior row.
- `GET /api/v1/ai/status` - truthful runtime state (`READY`/`LOADING`/`DEGRADED`/`DISABLED`),
  provider, model, last latency.

No endpoint accepts an arbitrary prompt - every request analyzes one real incident through the one
controlled, versioned prompt (`ai/prompts/incident_analysis_v1.txt`, tracked as `prompt_version` on
every row).

## Dashboard

Incident Detail's section E ("AI Assessment - Model Interpretation") replaces the Phase 4 "NOT
ENABLED" placeholder. It never auto-runs on page load or refresh - only the analyst's own
`ANALYZE WITH LOCAL AI` click triggers inference, per the blueprint's "do not automatically rerun
inference on every refresh" requirement. The panel is visually distinct (indigo border/background,
explicit "Model Interpretation" label) from the black-and-white Observed Evidence and Deterministic
Detections sections above it, and from the human-driven Analyst Workflow panel below it - see
`docs/ai-security-boundaries.md` for why that visual separation is a hard requirement, not styling
taste.

## Failure isolation

`services/ai_analyst/service.py::run_analysis` never raises to its caller - provider load failure,
timeout, invalid JSON, and hallucinated references are all caught and persisted as a failed
`AIAssessment` row with a `validation_status` and `error` message. Verified in
`tests/integration/test_ai_analyst_api.py` (`test_provider_timeout_is_isolated_and_incident_state_
unaffected`, `test_provider_error_other_than_timeout_is_isolated`) that a failed analysis leaves
the incident's `status`/`severity` completely untouched, and in
`tests/adversarial/test_prompt_injection.py`/`test_prompt_injection_live.py` that this holds even
when the model's output actively tries to look compliant with an injected instruction.
