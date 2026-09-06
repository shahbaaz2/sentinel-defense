# DECISIONS

ADR-style log of durable engineering decisions. Newest first. Each entry: date, decision, rationale.

---

## 2026-09-06 — Demo Control structure: `apps/demo_control` + `apps/demo-control-console`

Mirrors the existing `apps/api`+`apps/dashboard` (Sentinel) and `apps/missionnet`+`apps/missionnet-
console` (MissionNet) pattern exactly: one FastAPI backend, one Next.js frontend, each independently
runnable. The Python package directory is `demo_control` (underscore - Python doesn't allow hyphens
in importable package names) while its own database, ports, and the frontend directory use the
hyphenated `demo-control`/`demo-control-console` naming to match the blueprint's `apps/demo-control`
suggestion as closely as syntax allows. This is a fourth full app, not a subdirectory of Sentinel or
MissionNet, because §17 of the blueprint and the Phase 3 prompt are explicit that Demo Control is a
third, independent product - visually and architecturally distinct from both.

## 2026-09-06 — Proof the Scenario Controller cannot create Sentinel incidents/detections directly

This is the load-bearing safety property of Phase 3, so it is stated plainly: `apps/demo_control`
has no import of, or dependency on, `domain.models.orm`, `services.detection_engine`, or
`services.incident_engine`. Its only way to affect Sentinel's state is `POST /api/v1/ingest/run`
(`apps/api/admin_routes.py`), which runs Sentinel's real, unmodified Phase 2 pipeline - the same
adapter, mapper, detection rules, and correlation engine already tested in Phase 2 - and every other
Sentinel call the controller makes is a `GET`. `apps/demo_control/verification.py` derives every
PASS/FAIL check from those real GET responses; there is no function anywhere in `apps/demo_control`
that constructs a `Detection` or `Incident` object. `tests/integration/test_demo_control_e2e.py`
independently cross-checks a run's captured incident ID against Sentinel's own API
(`test_scn003_passes_with_real_ids_at_every_layer`) rather than trusting the controller's own record.

## 2026-09-06 — Scenario definition format and the DET-numbering correction

YAML, one file per scenario in `cyber-range/scenarios/SCN-*.yaml`, parsed by
`apps/demo_control/scenarios.py` into a Pydantic `ScenarioDefinition` - schema-validated at load
time, not just structurally-typed at runtime. Steps support both `repeat` (same target N times,
e.g. SCN-001's auth-failure burst) and `targets` (a list, one call per item, e.g. SCN-004's spread
across five different mission records) because DET-001 and DET-003 need different traffic shapes to
trigger genuinely, not because the format needed both for its own sake.

The Phase 3 prompt's suggested rule IDs per scenario (DET-002 for "Service Credential Anomaly",
DET-003 for "Mission-Critical Asset Degradation", DET-004 for "Sensitive Record Access") come from
the *original* blueprint's suggested list, not the catalog Phase 2 actually shipped. Every scenario
here targets the rule that matches its *described behavior* in the real catalog instead - see the
"Phase 3 scenario-to-rule mapping" entry below for the full SCN-to-DET mapping. This is called out
in each scenario's own `description` field too, so a reader hitting a scenario file directly isn't
confused.

## 2026-09-06 — Execution state machine and why polling, not SSE

`apps/demo_control/runner.py` implements PENDING → PREPARING → RUNNING → WAITING_FOR_TELEMETRY →
WAITING_FOR_SENTINEL → VERIFYING → PASSED/FAILED, with CANCELLED reachable at any point via a
`cancel_requested` flag checked between steps and poll iterations. Each transition is persisted
immediately (`_update_run`/`_append_timeline`), so `GET /api/v1/runs/{id}` always reflects genuine
progress - the UI's timeline entries are exactly what `_append_timeline` wrote, in the order it wrote
them, never animated client-side.

The frontend polls `GET /api/v1/runs/{id}` every 1.5s (`RunView.tsx`) rather than using
Server-Sent Events. A real scenario run completes in 2-5 seconds end to end (measured: SCN-003 ~2s,
SCN-010 ~3s), so SSE's main advantage - avoiding poll latency on long-lived connections - doesn't
apply here, and polling is trivially simpler to reason about, test, and keep working across a
background-tab-throttled browser. Revisit only if a future scenario's real duration grows enough
that 1.5s of staleness becomes noticeable.

## 2026-09-06 — Verification is baseline-diffed, not reset-dependent

`apps/demo_control/verification.py` captures the set of existing detection/incident IDs *before* a
scenario's steps run (`capture_baseline`) and only counts IDs absent from that baseline as caused by
this run. Every shipped scenario also resets the lab first (`reset.strategy: lab_reset`) for
demo determinism, but verification does not rely on that: a scenario with `reset.strategy: none`
still gets correct baseline-diffed results (exercised directly by
`tests/integration/test_demo_control_e2e.py::test_precondition_failure_reported_as_failed_not_passed`,
which needs the pre-reset state preserved to test the failure path at all). MissionNet-side
observation (`_poll_missionnet_events` in runner.py) uses the same principle via `since=<run start
time>` rather than a baseline snapshot, since MissionNet's audit/telemetry endpoints already support
time-based filtering.

## 2026-09-06 — `POST /api/v1/ingest/run` and `/api/v1/admin/reset`: the only two Sentinel writes

Phase 2's ingestion pipeline only had a CLI entrypoint (`make ingest-once`). Demo Control runs as a
separate process and needed a way to trigger it without importing Sentinel's internals or shelling
out to a subprocess. Refactored the CLI's logic into `services/event_ingestor/pipeline.py`
(`run_ingestion_cycle`) and exposed it as `POST /api/v1/ingest/run` on Sentinel's own API
(`apps/api/admin_routes.py`) - both `make ingest-once` and the new endpoint now call the identical
function, so there is exactly one ingestion code path, not two that could drift. `POST
/api/v1/admin/reset` similarly wraps the existing `services/event_ingestor/reset.reset()` (`make
sentinel-reset`). Both are POSTs but neither writes an event, detection, or incident directly - they
each invoke Sentinel's own pre-existing, already-tested logic wholesale.

## 2026-09-06 — Next.js `allowedDevOrigins` and CORS: two real bugs found building the console

Two genuine bugs surfaced building the first interactive (client-component) frontend in this repo -
recorded because they silently broke functionality with no obvious error message:

1. **Hydration silently failed** when the app was loaded via `http://127.0.0.1:3200` instead of
   `http://localhost:3200`. Next.js 16 introduced `allowedDevOrigins` as a security default that
   blocks cross-origin *dev* resource requests - and this blocks more than the HMR websocket; it
   blocked the client bundle chunks needed for hydration entirely, leaving every "use client"
   component visually present (server-rendered HTML) but permanently inert (no React fiber attached,
   confirmed via `Object.keys(el).filter(k => k.startsWith('__react'))` returning empty). No console
   error pointed at this - only a `⚠ Blocked cross-origin request` line in the dev server's own
   stdout. Fixed by adding `allowedDevOrigins: ["127.0.0.1", "localhost"]` to `next.config.ts` in
   **all three** Next.js apps (dashboard, missionnet-console, demo-control-console), since the same
   127.0.0.1-vs-localhost mismatch could bite any of them the moment they grow a client component.
2. **CORS blocked the browser's fetch** from the console (`:3200`) to the Demo Control API (`:8100`)
   - a different origin. FastAPI has no CORS policy by default. Added `CORSMiddleware` to
   `apps/demo_control/main.py` restricted to the console's own dev origins only; Sentinel's and
   MissionNet's APIs don't need this yet because nothing calls them from browser JS on a different
   port (their own dashboards use server-side `fetch` in Server Components, which isn't subject to
   browser CORS).

## 2026-09-06 — Phase 3 scenario-to-rule mapping uses the real DET catalog, not the prompt's numbering

The Phase 3 continuation prompt's suggested scenarios cite DET-* IDs from the *original* blueprint
suggestion list (DET-002 "Service Credential...", DET-003 "Mission-Critical Asset...", DET-004
"Sensitive Record Access..."). Phase 2 deliberately renamed/renumbered these during implementation
(see the "genuine signals only" decisions below) because the original names didn't correspond to
achievable signals - the *actual, shipped, tested* catalog in `docs/detection-engine.md` is:
DET-001 Repeated Authentication Failures, DET-002 Mission-Critical Asset Degraded Unexpectedly,
DET-003 Sensitive Mission Record Access Anomaly, DET-004 Suspicious Telemetry Anomaly, DET-005
Multi-Signal Asset Compromise Indicator, DET-006 Identity Compromise Indicator (token revoke +
record access).

Rather than force a scenario to reference a rule ID that doesn't do what the scenario name implies,
each Phase 3 scenario targets the rule that actually matches its *described behavior*:
- SCN-001 "Repeated Authentication Failures" → **DET-001** (matches on both name and number).
- SCN-002 "Service Credential Anomaly" → **DET-006** (the real token-revoke-based identity rule;
  the prompt said "DET-002", which is asset degradation in the shipped catalog, not credentials).
- SCN-003 "Mission-Critical Asset Degradation" → **DET-002** (prompt said "DET-003").
- SCN-004 "Sensitive Record Access Anomaly" → **DET-003** (prompt said "DET-004").
- SCN-010 combines all of the above plus DET-005 (multi-signal correlation falls out naturally when
  SCN-003's degrade and a telemetry injection land on the same asset within the correlation window).

This is called out explicitly, in code comments and in each scenario YAML's `description`, so a
future reader isn't confused by scenario name vs. rule ID appearing mismatched.

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
