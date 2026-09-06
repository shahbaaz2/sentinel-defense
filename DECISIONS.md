# DECISIONS

ADR-style log of durable engineering decisions. Newest first. Each entry: date, decision, rationale.

---

## 2026-09-06 — Project decomposition (mandatory, do not lose this)

The prototype is **three connected deliverables**, all required. None may be skipped or faked:

1. **Sentinel** (`apps/api`, `services/*`, `ai/*`, `domain/*`, `apps/dashboard`) — the AI-augmented
   defensive cyber platform. Ingests normalized telemetry, runs deterministic detection/correlation,
   packages evidence for a local LLM, gets a schema-validated assessment, recommends an allow-listed
   playbook, requires human approval, executes narrow deterministic containment against MissionNet,
   verifies, and records a full audit trail.
2. **MissionNet** (`apps/missionnet`) — an independently runnable, synthetic fictional mission-information
   application that Sentinel protects. Not static JSON: it has its own Operations Console UI, Identity
   Service, Mission Data API, Telemetry Gateway, Asset Registry, audit events, a real health/state
   machine (`NOMINAL -> DEGRADED -> CONTAINMENT_IN_PROGRESS -> RECOVERING -> NOMINAL`), and an internal
   lab-control API (`/lab/*`) that only Sentinel's executor and the Demo Control Plane may call.
3. **Demo Control / Scenario Engine** (`services/scenario_controller`) — a safe local harness that starts
   named scenarios, changes only MissionNet state, injects/replays synthetic telemetry, and observes
   Sentinel's reaction through Sentinel's normal APIs. It must never directly create a Sentinel incident,
   AI assessment, approval, or response-success record — Sentinel must discover everything independently.

**Hard rule:** the project is not complete if only Sentinel exists, if MissionNet is reduced to a mock
JSON fixture, or if the Demo Control Plane fakes a successful detection/response instead of causing one.

The causal path that must work end to end (first proven at Phase 7 via SCN-010):

```
Demo Control -> MissionNet state/behavior -> telemetry -> Sentinel ingest ->
deterministic detection/correlation -> incident -> local LLM evidence assessment ->
allow-listed response recommendation -> human approval -> deterministic MissionNet
containment -> verification -> MissionNet recovery -> audit trail
```

Source of truth: `SENTINEL_Complete_Prototype_Plan_v1.1.md` (blueprint) and
`SENTINEL_Claude_Master_Build_Prompt_v1.1.txt` (build order), both under project root's parent Downloads.
This repo's `docs/blueprint.md` mirrors the blueprint for in-repo reference.

---

## 2026-09-06 — Machine profile: Lite

Detected: Apple Silicon (arm64), macOS 15.3.1, 16 GB unified RAM, 8 cores, ~115 GB free disk after
cleanup. Per blueprint §4.2, 16 GB RAM selects the **Lite profile**:
- Native Qwen3-4B-Instruct-2507 4-bit MLX for inference (Phase 5+).
- FastAPI + Next.js run natively on macOS (not in containers).
- Colima allocated conservatively (4 CPU / 6 GB RAM / 60 GB disk) for PostgreSQL + MissionNet containers only.
- Synthetic/fixture sensor adapters first; heavy sensors (Wazuh, Suricata, Zeek, Falco) deferred to Phase 8
  and enabled one at a time, never all simultaneously on this machine.
- OpenSearch, full Wazuh stack, and Security Onion explicitly out of scope for MVP.

**Why:** the blueprint warns that Wazuh's own quickstart resource guidance exceeds what a 16 GB Lite
profile can run alongside everything else. Disk was also a hard constraint (started at 17 GB free due to
~275 GB of old VM images/ISOs in Downloads/Virtual Machines.localized/Parallels); user freed space before
build started.

---

## 2026-09-06 — Stack choices (per blueprint §5, not re-litigated)

- Dashboard: Next.js + React + TypeScript.
- API/control plane: FastAPI + Python 3.12 (not 3.14, which shipped as the system default — pinned to
  3.12 for library compatibility with the Python security/ML ecosystem, per blueprint §24.4).
- Validation: Pydantic v2 for every event/incident/AI-output/API contract.
- System of record: PostgreSQL, with pgvector for local RAG — no separate vector DB service.
- Container runtime: Colima (MIT-licensed, free) instead of Docker Desktop, whose license is not free for
  all use cases — Docker CLI talks to the Colima VM.
- No Redis/queue until a measured need exists.
- AI runtime: MLX-LM native on macOS, Qwen3-4B-Instruct-2507 4-bit as the default model, behind an
  `LLMProvider` protocol so the model/runtime can be swapped without touching application code.

---

## 2026-09-06 — Use standalone `docker-compose`, not the `docker compose` v2 plugin

On this machine, `brew install docker docker-compose` does not wire up `docker compose` as a CLI
subcommand (the plugin isn't symlinked into `~/.docker/cli-plugins/`). Rather than fight Homebrew's
packaging, all scripts invoke the standalone `docker-compose` binary directly, which works out of the
box. Also removed `"credsStore": "desktop"` from `~/.docker/config.json` (backed up to
`config.json.bak`) — it pointed at a Docker-Desktop-only credential helper that doesn't exist under
Colima and broke anonymous image pulls. This project never needs private-registry auth, so no
credential helper is required at all.

## 2026-09-06 — Phase 2: MissionNet adapter polls its public API over real HTTP, not the database

`integrations/missionnet/adapter.py` calls MissionNet's own `GET /audit` and `GET /telemetry`
(extended with `?since=<ISO8601>&limit=<n>` ascending-order polling specifically for this) rather
than querying MissionNet's Postgres tables directly. This is deliberate, not just convenient:
Sentinel must observe MissionNet the same way a real external SIEM/XDR would observe a monitored
system - through its API - so the two systems stay genuinely decoupled and the causal chain (Demo
Control → MissionNet → telemetry → Sentinel ingest) is real, not a database-level shortcut.
`EventSourceAdapter` (`services/event_ingestor/ports.py`) is the vendor-neutral Protocol; Wazuh/
Splunk/Suricata/Zeek/Falco adapters (Phase 8) implement the same interface with zero changes to
ingestion, detection, or correlation code.

## 2026-09-06 — Ingestion cursor and idempotency design

One `ingestion_cursors` row per `(source, stream)` stores a `last_timestamp` watermark. Each poll
passes it as `since`; MissionNet returns only newer rows, ascending. Idempotency is enforced twice,
independently: (1) `normalized_events` has a unique constraint on `(source, source_event_id)` and
the ingestion service checks-then-skips before inserting, and (2) `raw_events` primary key is
`f"{source}-{stream}-{source_event_id}"`, so re-ingesting the same MissionNet row is a no-op even if
the cursor were somehow rewound. Verified in
`tests/integration/test_sentinel_ingestion_pipeline.py::test_repeated_ingestion_is_idempotent_...`.

**Gotcha worth recording so it isn't rediscovered:** `RawEvent` and `NormalizedEventRecord` have a
plain FK column (`normalized_events.raw_event_ref -> raw_events.raw_event_id`) but no declared ORM
`relationship()` between them. SQLAlchemy's unit-of-work does **not** infer insert ordering across
mappers from a bare FK column - only from `relationship()`-derived dependency edges - so a single
flush containing both new `RawEvent` and new `NormalizedEventRecord` objects can (and, empirically,
did) attempt the child insert before the parent, tripping the FK constraint. Fixed by ingesting in
two explicit passes: add and flush every needed `RawEvent` first, then add every
`NormalizedEventRecord`. If a future change reintroduces "add both, then flush once," this bug comes
back - either keep the two-pass structure or add a real `relationship()`.

## 2026-09-06 — Detection rules are plain Python, not Sigma, for Phase 2

See `docs/detection-engine.md` for full rationale. Summary: the `Rule` dataclass shape mirrors what
a Sigma-backed rule would need (id/name/version/severity/category/mitre_techniques/evaluate), so
adopting Sigma in Phase 8 is an adapter, not a redesign. Every rule is a pure function over
`EventView` objects with no DB access, which is what makes 13 rule-engine unit tests possible with
zero database fixtures.

## 2026-09-06 — Incident correlation groups by `correlation_key` (asset OR identity), not asset alone

Blueprint §9 groups by "same asset" and "same identity" as separate correlation rules. Rather than
two parallel grouping mechanisms, both `Detection` and `Incident` carry one `correlation_key` column
that the triggering rule populates as `asset_id or user_id`. This lets identity-centric rules
(DET-001, DET-003, DET-006) and asset-centric rules (DET-002, DET-004, DET-005) share one merge
algorithm (`services/incident_engine/engine.py`) instead of needing two. Full detail and known
limitations in `docs/incident-correlation.md`.

## 2026-09-06 — Why no AI anywhere in Phase 2

Every decision in this phase - whether an event matches a rule, whether two detections correlate
into one incident - is made by plain, tested, deterministic code with no model in the loop. This
isn't a temporary simplification to revisit later; it's the architectural point of separating the
DETECTION PLANE from the AI PLANE (blueprint §2). Phase 5 adds a local LLM that receives an evidence
packet built from exactly the data this phase produces (`normalized_events`, `detections`,
`incidents`) and returns a schema-validated *assessment* - it will never decide whether a detection
or incident *exists*. The dashboard's "AI Analyst: NOT ENABLED — scheduled for a later phase" label
on every incident page is intentionally visible now so the architecture reads as honest at every
phase, not just at the end.

## 2026-09-06 — Extended MissionNet with genuine `auth.*` and `record.access` signals for Phase 2

Four of the six lab detection rules need signals MissionNet didn't produce after Phase 1
(authentication events, mission-record access events). Rather than fabricate these inside Sentinel
(explicitly prohibited - Sentinel must only detect what actually happened), added a real, minimal
`POST /identity/login` and `GET /mission-data/records/{id}?actor_user_id=...` to MissionNet's own
public API, each writing a genuine `audit_events` row. This closes a Phase 1 gap against the
blueprint's own spec (§7.1: Identity Service should have "login/logout/token events") rather than
inventing new scope. `IdentityUser.synthetic_password` is plaintext by design - a fictional
credential in a synthetic lab, not a real secret, so normal password-handling practices don't apply.

## 2026-09-06 — MissionNet DB engine uses NullPool

`create_async_engine`'s default pooled connections stay bound to whichever asyncio event loop first
checked them out. pytest-asyncio creates a fresh event loop per test by default, so the second
integration test to touch the shared module-level `engine` singleton crashed with
`RuntimeError: ... attached to a different loop`. Switched `apps/missionnet/db.py` to `NullPool`
(fresh connection per checkout) rather than fighting pytest-asyncio's loop scoping. Acceptable at this
prototype's connection volume; revisit if per-request connection overhead ever shows up in latency
measurements.

## 2026-09-06 — Lab-control API design (blueprint §7.5)

Every `/lab/*` mutation takes an optional `ScenarioContext` body (`actor_type`, `actor_id`,
`scenario_id`, `reason`) and writes exactly one `audit_events` row per call, before committing the
state change in the same transaction. This is deliberate: Phase 3's Demo Control Plane and Phase 7's
Sentinel response executor are the only two callers, and both need their actions to be
distinguishable from each other and from ordinary application activity in MissionNet's own audit
trail. The header-secret check (`X-Lab-Secret`) is a single dependency (`require_lab_secret`) applied
per-router, not per-route, so a new lab endpoint can't accidentally ship without it.

## 2026-09-06 — Dependency rule

Business logic (`services/*`, `domain/*`) imports `domain/repositories` **protocols**, never vendor SDKs
directly. `ai/providers` implements `LLMProvider` for `MockLLMProvider` (tests) and
`MLXOpenAICompatibleProvider` (real inference) behind one interface. This is what allows Postgres to be
augmented by OpenSearch later, and MLX to be replaced by a GPU endpoint later, without rewriting the
incident engine, policy engine, or dashboard.
