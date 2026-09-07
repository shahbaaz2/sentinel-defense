# Response playbooks (Phase 6; execution is Phase 7 - see docs/response-executor.md)

Declarative response *plan definitions*, not executable scripts. Nothing in `playbooks/*.yaml`
contains a shell command, SQL statement, or network call - each playbook only references stable
`action_id`s from a closed registry (`services/policy_engine/actions.py`). See
`docs/human-approval.md` for a plan's approval lifecycle and `docs/response-executor.md` for what
happens when an approved plan is actually executed.

## The catalog

| ID | Name | Category | Min severity | Min detections | Assets |
|---|---|---|---|---|---|
| RP-001 | Authentication Abuse Investigation / Credential Protection | credential-abuse | medium | 1 | any (identity-focused) |
| RP-002 | Service Credential Protection | identity-compromise | high | 1 | any (identity-focused) |
| RP-003 | Critical Mission Asset Containment | asset-degradation | high | 1 | data / gateway / identity |
| RP-004 | Sensitive Record Access Protection | data-access-anomaly | medium | 1 | any (identity-focused) |
| RP-005 | Multi-Signal Incident Containment | asset-degradation / telemetry-anomaly / multi-signal-compromise / identity-compromise | high | **2** | any |

Each maps to one of the 6 Phase 2 detection rules (RP-005 to whichever combination produces a
multi-detection incident - see "Why `allowed_asset_types` uses `mission_role`" and "Why RP-005
checks detection count" below).

## Schema (`services/policy_engine/playbooks.py::PlaybookDefinition`)

```yaml
id: RP-003                                    # must equal the filename (RP-003.yaml)
version: "1.0"
name: Critical Mission Asset Containment
description: >
  ...
enabled: true
allowed_asset_types: [data, gateway, identity]  # MissionNet mission_role values, or [] = any asset
allowed_incident_categories: [asset-degradation]
minimum_incident_severity: [high]               # floor - "high" means high or critical qualify
minimum_detection_count: 1                      # default 1; RP-005 sets 2
requires_human_approval: true
reversible: true
actions:
  - action_id: quarantine_workload              # must exist in the action registry
    target_source: incident_asset               # incident | incident_asset | incident_identity
    required: true                              # default true; false only for RP-005's revoke_test_token
verification: [workload_isolated, ...]          # re-checked for real by services/response_executor/verifier.py
rollback: [restore_workload_network]            # free-text steps, not necessarily registry action IDs
risk:
  mission_impact: high
  reversibility: medium
```

Validated at load time (`services/policy_engine/playbooks.py`, tests in
`tests/unit/test_playbook_schema.py`): every `action_id` must be registered, a playbook marked
`reversible: true` must declare at least one rollback step (and vice versa), `allowed_incident_
categories`/`minimum_incident_severity`/`actions`/`verification` must be non-empty, and the
filename must equal the declared `id` - which also makes duplicate IDs structurally impossible
(two files can't share a name on one filesystem). An invalid playbook raises at load time, not at
first use.

## Why `allowed_asset_types` matches MissionNet's `mission_role`, not Sentinel's `asset_type`

Every MissionNet asset's `asset_type` column is literally `"service"` - see `apps/missionnet/
seed.py`. That column can never discriminate between playbooks in this deployment. The field that
actually varies is MissionNet's own `mission_role` (`identity`, `gateway`, `data`, `edge`), carried
through to Sentinel as `SentinelAsset.extra["mission_role"]` and exposed on the AI Analyst's
`EvidenceAsset.mission_role` (`services/ai_analyst/evidence.py`). `allowed_asset_types` in the YAML
keeps its blueprint name for fidelity to the spec, but its values are real mission roles, not the
always-constant `asset_type` string.

## Why RP-005 checks detection count, not a single category

A multi-signal incident's `category` column is set once, from whichever detection happened to
create it first (`services/incident_engine/engine.py` never updates `category` on merge) - so the
SCN-010 flagship incident (DET-002 + DET-004 + DET-005, all on one asset) ends up with `category =
"asset-degradation"` even though it's genuinely a multi-signal case. RP-005 therefore lists every
category a multi-signal incident could plausibly land on *and* requires `minimum_detection_count:
2`, so it becomes eligible exactly when an incident actually has multiple correlated detections -
independent of which one happened to arrive first. Verified live: SCN-010's asset-degradation
incident shows both RP-003 and RP-005 as eligible (`GET .../eligible-playbooks`), and the real
local AI model recommended RP-005 for it unprompted (see PROGRESS.md).

## Why RP-005's `revoke_test_token` step is `required: false`

RP-005 is eligible across four different incident categories with structurally different evidence -
some are purely asset-based (no identity/token in evidence at all), some are identity-based (no
degraded asset). Its `revoke_test_token` step can't always resolve a target, even for a genuinely
eligible incident. Marking it `required: false` (`services/policy_engine/playbooks.py::
PlaybookAction.required`, default `true` for every other step in every other playbook) means the
executor `SKIP`s it when unresolvable instead of blocking or failing the whole plan - verified live:
the SCN-010 flagship incident (asset-only) executes RP-005 to `SUCCEEDED` with this one step
`SKIPPED`. See `docs/response-executor.md`.

## Adding a playbook

1. Add a new `action_id` to `services/policy_engine/actions.py` first if the playbook needs a
   capability that doesn't exist yet - playbooks can only reference what's already registered.
2. Write `playbooks/RP-00N.yaml` with a unique ID matching the filename.
3. Add tests in `tests/unit/test_playbook_schema.py` (loads without error) and
   `tests/unit/test_policy_engine.py` (fires on the intended incident shape, doesn't fire on
   adjacent ones).

No code outside the YAML file and the action registry needs to change -
`services/policy_engine/playbooks.py::list_playbooks()` picks up every `RP-*.yaml` file
automatically.
