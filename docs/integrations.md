# Integrations / vendor-neutral adapters (Phase 8)

Sentinel is SIEM-agnostic. Every source it can ingest from - MissionNet (the synthetic lab) and
every real sensor - implements the exact same `EventSourceAdapter` boundary
(`services/event_ingestor/ports.py`), so the domain layer (normalization, detection, correlation,
incidents, AI, response) never knows or cares whether a `NormalizedEventRecord` came from a
synthetic mission-information app or a real copy of Suricata. Wazuh is useful for free/local
experimentation; Splunk is a first-class enterprise integration target (see
`docs/splunk-integration.md`); Sentinel replaces neither - it adds normalization, evidence-grounded
local AI, policy-controlled human-approved response, verification, and provenance on top of
whatever an organization already runs.

## The adapter contract

```python
class EventSourceAdapter(Protocol):
    async def fetch_events(
        self, *, since: datetime | None = None, cursor: str | None = None,
        limit: int | None = None,
    ) -> EventBatch: ...

    async def health(self) -> bool: ...
```

Every adapter, regardless of source, guarantees:

- **Stable source event IDs** - the idempotency key `services/event_ingestor/service.py` checks
  before ever inserting a `NormalizedEventRecord`.
- **Per-source, per-stream cursor/checkpoint** - `IngestionCursor(source, stream)`, so a MissionNet
  outage never re-processes Zeek's already-ingested `dns.log`, and vice versa.
- **Source provenance** - `RawEvent.source` + a SHA-256 of the untouched payload, always
  preserved regardless of what the normalizer keeps (see "Raw provenance" below).
- **Explicit timeouts** - every HTTP-based adapter (MissionNet, Wazuh, Splunk) sets an explicit
  `httpx` timeout; a file-based adapter (Suricata, Zeek, Falco) simply returns no events for a
  missing file rather than blocking.
- **`health()` never raises** - it returns `False` for anything from "not configured" to "server
  unreachable" to "malformed output file" - the Data Sources UI and System Assurance page call it
  directly, with no try/except of their own.

## The registry

`services/event_ingestor/registry.py::build_adapter_registry(settings)` returns one
`AdapterDescriptor` per source, built fresh from live settings on every call (never cached at
import time, so toggling `.env` and restarting is always enough):

| Field | Meaning |
|---|---|
| `adapter_id` / `name` / `version` | e.g. `"suricata"` / `"Suricata"` / `"SUR-001"` - versioned the same way the response executor (`EX-001`) and policy bundle (`PB-001`) are. |
| `capabilities` | e.g. `["alert-ingestion"]`, `["evidence-ingestion"]`, `["read-only-search"]`. |
| `configuration_requirements` | the exact `SENTINEL_*` env vars an operator must set. |
| `supported_event_categories` | which `EventCategory` values this source can produce. |
| `enabled` | whether the operator turned this adapter on - independent of `status()`. |
| `streams` | `{stream_name: adapter_instance}` - empty exactly when disabled or missing required config. |

`AdapterDescriptor.status()` is the one place ACTIVE/DEGRADED/NOT_CONFIGURED is decided:

- **NOT_CONFIGURED** - `enabled` is False, or required config (a Splunk base URL, a Wazuh token)
  is missing, so `streams` is empty.
- **DEGRADED** - `enabled` and configured, but at least one stream's `health()` returned False
  (Suricata/Zeek before their first run - no `eve.json`/log yet - genuinely is DEGRADED by this
  definition, not a bug; it becomes ACTIVE the moment real output exists).
- **ACTIVE** - `enabled`, configured, and every stream's `health()` returned True.

This is exposed two ways: `GET /api/v1/integrations` (the Data Sources page - full detail per
adapter, including `last_successful_ingest_at`/`event_count`/`last_error`, all read from real
persisted state - `IngestionAdapterStatus` and `NormalizedEventRecord`, never a hardcoded string)
and `GET /api/v1/system/assurance`'s `integrations` field (the same six statuses, folded into the
existing System Assurance page).

## The adapters

| Adapter | Status by default | What it is |
|---|---|---|
| MissionNet | Always ACTIVE (core, not optional) | The synthetic lab's own audit/telemetry streams - unchanged since Phase 2. |
| Suricata | NOT_CONFIGURED until enabled | Real Suricata, run in Docker in batch mode against a safe synthetic pcap - see `docs/sensor-pipeline.md`. Genuinely live. |
| Zeek | NOT_CONFIGURED until enabled | Real Zeek, same pcap, same batch-mode pattern. Genuinely live. Evidence only - never itself a detection. |
| Wazuh | NOT_CONFIGURED | Adapter/mapper built and tested against real, representative Wazuh alert JSON via `httpx.MockTransport` - no live Wazuh manager runs in this Lite-profile lab (see `integrations/wazuh/__init__.py`). |
| Splunk | NOT_CONFIGURED | Read-only REST client built and tested against Splunk's real endpoint shapes via mock - see `docs/splunk-integration.md`. No live Splunk instance exists in this lab. |
| Falco | NOT_CONFIGURED | Contract + fixtures only, per this phase's explicit scope - not run live anywhere. |

Suricata and Zeek default to `false` in `.env`/`.env.example` even though they work, matching every
other optional capability in this project (the AI Analyst, response execution, RAG): a fresh
checkout behaves exactly like Phase 0-7 until an operator opts in. Set
`SENTINEL_SURICATA_ENABLED=true` and `SENTINEL_ZEEK_ENABLED=true` to turn them on - see
`RUNBOOK.md`.

## Multi-source ingestion and error isolation

`services/event_ingestor/service.py::ingest_all` iterates every enabled adapter's every stream and
wraps each one individually: a failing adapter (MissionNet unreachable, a malformed Wazuh response,
a Splunk auth error) is caught, logged, recorded to `IngestionAdapterStatus`, and reported as an
`IngestionResult` with `error` set - the cycle continues with every other adapter regardless. This
extends to MissionNet's own asset sync, which used to run outside this isolation and could abort
the whole cycle on a MissionNet outage - a real bug this phase found and fixed (see DECISIONS.md).

## Event Explorer and raw provenance

`GET /api/v1/events` filters by `source`, `event_category`, `event_type`, `rule_id`, `src_ip`, and
`dst_ip` in addition to the fields Phase 2-7 already supported. Every event - MissionNet or sensor -
still traces back to its original raw record: `RawEvent.payload` (the untouched source JSON),
`RawEvent.sha256`, `NormalizedEventRecord.raw_event_ref`, and (for network events) `rule_id`/
`src_ip`/`dst_ip`/`dns_query` as their own queryable columns, not buried in free text.
