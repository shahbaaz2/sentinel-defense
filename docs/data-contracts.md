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

## Sentinel's own persistence (`domain/models/orm.py`, Phase 2)

Own Postgres database (`sentinel`), migrated via `infrastructure/migrations/sentinel` (Alembic).
Distinct from both the canonical `NormalizedEvent` Pydantic contract and MissionNet's schema.

| Table | Purpose | Key fields |
|---|---|---|
| `raw_events` | Untouched source payload | `raw_event_id`, `source`, `payload` (JSON), `sha256` |
| `assets` | Sentinel's own synced view of protected assets | `id` (`source:external_id`), `external_asset_id`, `source`, `criticality`, `status` |
| `normalized_events` | Persisted `NormalizedEvent` + ingestion-only fields | `event_id`, `event_type`, `correlation_key`, `raw_event_ref` (FK → `raw_events`) |
| `detections` | One deterministic rule firing | `detection_id`, `rule_id`/`rule_version`, `severity`, `correlation_key`, `dedupe_key` (idempotency) |
| `detection_event_links` | Detection → evidence events (relational, not JSON) | `detection_id`, `event_id` |
| `incidents` | Correlated case | `incident_id`, `status` (blueprint §9.4 values; Phase 2 only produces `new`), `correlation_key`, `category` |
| `incident_detection_links` / `incident_event_links` | Incident → evidence (relational) | composite PKs |
| `ingestion_cursors` | Per-`(source, stream)` polling watermark | `source`, `stream`, `last_timestamp` |

`correlation_key` on both `detections` and `incidents` is `asset_id` when the triggering rule is
asset-centric, else `user_id` - see `docs/incident-correlation.md`.

## Event source adapter boundary (`services/event_ingestor/ports.py`)

```python
class EventSourceAdapter(Protocol):
    async def fetch_events(self, *, since: datetime | None = None, cursor: str | None = None) -> EventBatch: ...
```

`integrations/missionnet/adapter.py` is the first (and so far only) implementation, as two adapter
instances - one per MissionNet stream (`audit`, `telemetry`) - each with its own cursor row. Future
sources (Wazuh, Splunk, Suricata, Zeek, Falco - Phase 8) implement the same Protocol; nothing in
`services/event_ingestor`, `services/detection_engine`, or `services/incident_engine` is MissionNet-
specific.

`integrations/missionnet/mapper.py` does SOURCE EVENT → NORMALIZER → CANONICAL EVENT: every
MissionNet audit `action` and the telemetry stream map to one explicit, tested
`(event_category, event_type, severity)`. See `docs/detection-engine.md` for the rules that consume
these events, and `docs/incident-correlation.md` for how detections become incidents.

## Sentinel API (`apps/api/main.py`, `apps/api/routes.py`)

`GET /api/v1/health`, `/api/v1/system/profile`, `/api/v1/system/assurance` (Deployment Assurance
panel data). Phase 2 adds: `/api/v1/assets`, `/api/v1/assets/{id}`, `/api/v1/events` (filterable by
`severity`/`source`/`asset_id`/`since`/`until`), `/api/v1/events/{id}`, `/api/v1/detections`
(filterable by `severity`/`status`/`asset_id`), `/api/v1/detections/{id}`, `/api/v1/incidents`
(filterable by `severity`/`status`/`asset_id`), `/api/v1/incidents/{id}` (includes full evidence:
linked detections and their event IDs), `/api/v1/metrics/summary` (dashboard overview data).
`ai_assessments`/`playbooks`/`approvals`/`executions`/`audit_log` (blueprint §10) are built starting
Phase 5/6/7.
