# Splunk integration (Phase 8) - read-only, first-class

**Sentinel is not replacing Splunk.** The product story: Sentinel can consume evidence from an
organization's existing Splunk environment and add vendor-neutral normalization, evidence-grounded
local AI, human-approved response, verification, and provenance on top of it. Splunk stays the
system of record for whatever it already indexes; Sentinel never writes to it.

No real Splunk instance exists in this Lite-profile lab (running one is far too heavy alongside
MissionNet/Suricata/Zeek/Postgres/MLX on a 16 GB machine, and is not required by this phase - see
DECISIONS.md). The client, adapter, and mapper are built and tested against Splunk's own real REST
shapes via `httpx.MockTransport` (`tests/unit/test_splunk_client.py`,
`tests/unit/test_splunk_adapter.py`), so pointing them at a genuine Splunk server later needs zero
code changes - only configuration.

## Read-only by construction

`integrations/splunk/client.py::SplunkClient` calls exactly two endpoints, both read-only:

- `GET /services/server/info` - health check only.
- `POST /services/search/jobs/export` - a one-shot, streaming, bounded search. No job is created
  and left running; no result set is unbounded (`count` is a hard cap Splunk itself enforces).

There is no code path anywhere in this integration that calls a Splunk endpoint capable of writing,
modifying, or deleting anything in the target deployment.

## Configuration

```bash
SENTINEL_SPLUNK_ENABLED=false        # stays NOT_CONFIGURED until explicitly true
SENTINEL_SPLUNK_BASE_URL=            # e.g. https://splunk.example.internal:8089
SENTINEL_SPLUNK_TOKEN=               # Bearer token - never logged, never sent to frontend JS
SENTINEL_SPLUNK_VERIFY_TLS=true      # on by default; only disable against a lab instance
SENTINEL_SPLUNK_INDEX=               # optional - prefixed onto the query as `index=<value>`
SENTINEL_SPLUNK_QUERY=               # a bounded SPL search, e.g. `search sourcetype=suricata`
```

The token is read once into `SplunkClient`, sent only as an `Authorization: Bearer` header, and
`SplunkClient.__repr__` is overridden to print `token=***redacted***` so a stray `repr()` in a log
line or traceback can never leak it (`tests/unit/test_splunk_client.py::
test_repr_never_leaks_the_token`).

## Field mapping is configurable, not universal

No two Splunk deployments necessarily use the same field names for the same concept - a
`SplunkFieldMapping` profile (`integrations/splunk/mappings/*.yaml`) declares which raw result
field holds each canonical concept (`time_field`, `src_ip_field`, `severity_field`, ...). Three
ship by default:

| Profile | For |
|---|---|
| `generic_security.yaml` | A Splunk deployment already using Splunk's own Common Information Model (CIM) field names (`src`, `dest`, `user`, `severity`, `signature`). |
| `suricata.yaml` | The Suricata Splunk Technology Add-on, which indexes `eve.json` fields close to their original names (`src_ip`, `dest_ip`, dotted `alert.severity`/`alert.signature` - Splunk flattens nested JSON into dotted field names, and the mapper reads that literally). |
| `windows_security.yaml` | Windows Security Event Log via the Windows TA (`ComputerName`, `Account_Name`, `EventCode`). |

A field a profile doesn't declare (`dst_ip_field: null` in `windows_security.yaml`) simply leaves
that `NormalizedEventRecord` column `None` - never guessed. This is deliberately not a full SPL
language layer (blueprint scope) - just a small, explicit field-name table per deployment shape.

## Live validation

If a real Splunk test instance is ever configured (`SENTINEL_SPLUNK_ENABLED=true` and a genuine
`SENTINEL_SPLUNK_BASE_URL`/`SENTINEL_SPLUNK_TOKEN`), `GET /api/v1/integrations` will report Splunk
`ACTIVE` the moment `SplunkClient.health()` succeeds against it, and the very next
`POST /api/v1/ingest/run` will run the configured bounded search, normalize real results, and
ingest them through the same pipeline every other source uses - no code path is mocked or
short-circuited for a "real" instance versus the test mock. No such instance exists in this
session, so Splunk is honestly reported `NOT_CONFIGURED` throughout - this phase does not claim
live Splunk validation, per its own scope (§14).
