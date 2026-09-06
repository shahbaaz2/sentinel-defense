# Data contracts

Current schema definitions. Update this file whenever a model changes — it's the fast reference so
another engineer (or Claude, in a future session) doesn't have to read every model file to know what
exists.

## Sentinel domain (`domain/models/`)

### `NormalizedEvent` (blueprint §8)

Every sensor/adapter maps into this one schema before Sentinel's detection engine sees it. Immutable
(`frozen`). See `domain/models/events.py` for exact field bounds.

| Field | Type | Notes |
|---|---|---|
| `event_id` | str | Immutable, unique. |
| `timestamp` / `received_at` | datetime | Source time vs. ingest time. |
| `source` | enum | `missionnet, suricata, zeek, wazuh, falco, osquery, synthetic` |
| `event_category` | enum | `network, endpoint, identity, application, runtime, vulnerability, control` |
| `severity` | enum | `info, low, medium, high, critical` |
| `asset_id`, `user_id`, `rule_id` | str? | Max 256 chars. |
| `src_ip`/`dst_ip`/`src_port`/`dst_port` | | Ports validated 1-65535. |
| `technique_ids`, `tags` | list[str] | Max 50 items each. |
| `summary` | str | Max 2000 chars. |
| `raw_event_ref` | str | Pointer to the raw event row; raw data is never discarded. |
| `scenario_id` | str? | Set when a Demo Control scenario caused this event. |

## MissionNet (`apps/missionnet/models.py`)

Own Postgres database (`missionnet`), migrated via `infrastructure/migrations/missionnet` (Alembic).
Every table carries a `classification` column defaulting to `"SYNTHETIC"`.

| Table | Purpose | Key fields |
|---|---|---|
| `assets` | Protected synthetic inventory | `asset_id`, `mission_role`, `criticality`, `dependencies` (JSON list), `status` (nominal/degraded/quarantined/contained/recovering), `network_state` |
| `identity_users` | Fictional operators/analysts/admins/service accounts | `user_id`, `role`, `user_type`, `status` |
| `service_tokens` | Fictional service credentials | `token_id`, `owner_user_id` (FK), `valid`, `revoked_at` |
| `mission_records` | Fictional mission data | `record_id`, `owner_user_id` (FK) |
| `telemetry_samples` | Fictional sensor/platform telemetry | `asset_id` (FK), `battery`, `link_quality`, `latitude`/`longitude` |
| `audit_events` | MissionNet's own audit/event stream | `actor_type`, `actor_id`, `action`, `object_type`, `object_id`, `detail` (JSON), `scenario_id` |

`assets.status` drives the computed overall system state (`apps/missionnet/state.py`):
`nominal -> degraded -> containment_in_progress -> recovering -> nominal` (blueprint §7.4). This is
always derived from live rows, never hard-coded.

### MissionNet API surface

Public (read-only, blueprint §7.1):
`GET /health`, `/assets`, `/assets/{id}`, `/identity/users`, `/identity/tokens`,
`/mission-data/records`, `/telemetry`, `/audit`, `/state`.

Lab-control (blueprint §7.5) — requires `X-Lab-Secret` header, reserved for Sentinel's response
executor (Phase 7) and the Demo Control Plane (Phase 3), never exposed to the LLM:
`POST /lab/reset`, `/lab/state/{asset_id}/degrade`, `/lab/tokens/{token_id}/revoke`,
`/lab/assets/{asset_id}/quarantine`, `/lab/assets/{asset_id}/restore`, `/lab/evidence/snapshot`,
`GET /lab/state`. Every mutation writes an `audit_events` row attributing actor type/id and, when
applicable, a `scenario_id` — this is what lets Sentinel later distinguish "the scenario caused this"
from "our own response caused this."

## Sentinel API (`apps/api/main.py`)

`GET /api/v1/health`, `/api/v1/system/profile`, `/api/v1/system/assurance` (Deployment Assurance
panel data - inference location, external AI status, model, knowledge/policy bundle). Sentinel's own
database schema (assets/events/detections/incidents/ai_assessments/playbooks/approvals/executions/
audit_log per blueprint §10) is built starting Phase 2.
