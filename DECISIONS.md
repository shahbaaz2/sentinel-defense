# DECISIONS

ADR-style log of durable engineering decisions. Newest first. Each entry: date, decision, rationale.

---

## 2026-09-06 — Phase 8: Suricata/Zeek run in batch mode against a captured pcap, never as a live sniffer

A continuously-running network sensor needs raw-socket/promiscuous access to a real interface,
which on this machine means either running Docker containers with elevated network capabilities
against a live capture surface, or complex Colima networking - and it would turn Suricata/Zeek into
long-running daemons permanently competing for the same 16 GB the whole Lite profile has to share
with Postgres, MissionNet, Demo Control, and the local LLM. Instead, `services/sensor_lab/
pipeline.py` generates one bounded burst of safe synthetic traffic between ephemeral Docker
containers on an isolated bridge network (`172.28.0.0/24`, no route outside this machine), captures
it to a pcap with `tcpdump` running inside the *client* container's own network namespace (not a
separate capture container attached to the bridge as its own port - a genuine bug found while
building this: a bridge only forwards unicast traffic point-to-point between the two actual
endpoints, so a third "observer" container on the same bridge sees only broadcast/ARP, never the
unicast payload; capturing from inside the client's own netns sees everything the client itself
sends and receives, which is the correct place to observe a single host's own traffic), then runs
Suricata (`--runmode=single`) and Zeek (`-r <pcap>`) once each, in `docker run --rm` containers that
exit in under a second and hold zero memory afterward. This is real Suricata and real Zeek output,
not a fixture - it just never runs as a daemon. See `docs/sensor-pipeline.md`.

## 2026-09-06 — Phase 8: Suricata/Zeek default `false` in `.env`/`.env.example` despite being real and working

Every optional capability this project has ever added - the AI Analyst, RAG, response execution -
ships disabled by default so a fresh checkout behaves identically to the phase before it until an
operator explicitly opts in. Suricata and Zeek follow the same rule even though, unlike Wazuh and
Splunk, they are genuinely functional here: enabling them changes what *every* scenario's ingestion
cycle does (an extra two adapters get polled on every `POST /api/v1/ingest/run`), so leaving them on
by default would be a behavior change to Phase 0-7's demos, not just an addition. `SENTINEL_
SURICATA_ENABLED=true`/`SENTINEL_ZEEK_ENABLED=true` in `.env` turns them on; both default `false`.

## 2026-09-06 — Phase 8: network detections correlate by originating host, not the full 4-tuple flow

NET-001 (a Suricata alert on a client→server connection) and NET-002 (a suspicious DNS query on a
client→DNS-resolver connection) are, in the SCN-NET-001 lab, two *different* flows by IP-pair - the
server and the DNS stub have different addresses. Correlating strictly by 4-tuple (src+dst IP+port)
would never merge them, even though they are obviously the same actor's activity and are exactly
what NET-003 (cross-sensor correlation) is supposed to catch. Every network rule instead sets
`RuleCandidate.correlation_key = f"host:{src_ip}"` - grouping by the *originating* host alone, the
same principle Phase 2's identity-based correlation already uses (group by the common actor, not
every attribute of every individual connection). This required one small, backward-compatible
addition: `RuleCandidate` gained an optional `correlation_key` override (`services/
detection_engine/rules.py`), read by `services/detection_engine/engine.py::_persist_candidate` in
preference to the existing `asset_id or user_id` default - no changes to `services/incident_engine/
engine.py` were needed, since it already groups purely by `Detection.correlation_key` regardless of
what produced it.

## 2026-09-06 — Phase 8: the adapter registry takes a structural `AdapterSettings` Protocol, not `apps.api.config.Settings`

`services/event_ingestor/registry.py::build_adapter_registry` needs `suricata_enabled`, `wazuh_base_
url`, and a dozen other settings fields - but `services/` must never import `apps/` (the same rule
`services/response_executor` follows for MissionNet's lab secret, passing it as a plain argument
from the apps layer instead). Rather than force every caller to import the concrete `apps.api.
config.Settings` class, `registry.py` declares a local, duck-typed `Protocol` naming exactly the
fields it needs; `Settings` satisfies it structurally with zero coupling. The one real wrinkle this
caused: `services/event_ingestor/pipeline.py` (used by both the CLI, which has no `Settings`
object, and indirectly by the API, which does) reads the same `SENTINEL_*` env vars directly via
`os.environ.get(...)` - exactly like it already did for `MISSIONNET_BASE_URL` before this phase -
via a local `_EnvAdapterSettings` dataclass, while `apps/api/admin_routes.py` builds the registry
from the real `Settings` object and passes it in explicitly as an optional `adapter_registry`
parameter. This mirrors Phase 7's `execute_response_plan(missionnet_base_url=...)` pattern exactly:
the services-layer function takes plain data; the apps-layer caller supplies it from settings.

## 2026-09-06 — Phase 8: Splunk field mapping is a configurable per-deployment profile, not a universal schema

No two Splunk deployments necessarily index the same concept under the same field name - a
Suricata Technology Add-on might index `src_ip`/`dest_ip` and a nested `alert.severity` (Splunk
flattens JSON into dotted field names in search results), while a hand-built CIM-compliant index
uses `src`/`dest`/`severity`. Rather than hardcode one field-name table (wrong for most real
deployments) or build a general SPL-parsing layer (explicitly out of scope - blueprint intent),
`integrations/splunk/schemas.py::SplunkFieldMapping` is a small, explicit table of which raw field
holds each canonical concept, loaded from `integrations/splunk/mappings/*.yaml`. Three profiles
ship (`generic_security`, `suricata`, `windows_security`) as realistic starting points, not an
exhaustive list - a new deployment adds a new YAML file, no code change. A field a profile doesn't
declare (`severity_field: null`) leaves that column `None` rather than guessing.

## 2026-09-06 — Phase 8: Wazuh and Splunk are contract/mock-tested, never claimed as live-validated

No live Wazuh manager or Splunk instance exists in this Lite-profile lab - both would be
substantial, heavy, separate services competing for the same 16 GB Suricata/Zeek/Postgres/MissionNet/
MLX already share, and neither is required to prove the architecture (the phase prompt explicitly
sanctions this fallback for both, unlike Suricata/Zeek). Both adapters are built exactly as
production-shaped as MissionNet's or Suricata's - real HTTP clients, real REST envelope shapes
(Wazuh's `{"data": {"affected_items": [...]}}`, Splunk's `/services/search/jobs/export` NDJSON) -
and tested against `httpx.MockTransport` returning genuine, representative fixture payloads
(`tests/unit/test_wazuh_adapter.py`, `tests/unit/test_splunk_client.py`). `GET /api/v1/integrations`
and System Assurance report both `NOT_CONFIGURED` honestly rather than a fabricated `ACTIVE` -
enabling either against a real instance later needs a config change, not a code change.

## 2026-09-06 — Phase 8: `IngestionAdapterStatus` persists real per-adapter ingestion history

The Data Sources UI needs "last successful ingest" and "last error" per adapter (blueprint §11) -
neither is derivable from existing tables. `IngestionCursor` only tracks the polling watermark, not
whether the most recent attempt succeeded, and an `IngestionResult.error` is transient, returned
only in the HTTP response of one `/api/v1/ingest/run` call, never stored. A new table,
`IngestionAdapterStatus(source, stream, last_attempt_at, last_success_at, last_error)`, is updated
on every `ingest_stream` success and every `ingest_all`-caught failure - a failed attempt updates
`last_attempt_at`/`last_error` without touching `last_success_at`, so "when did this last actually
work" and "when did we last try" stay genuinely distinct even through a run of consecutive
failures, mirroring the same care `ActionResult.rollback_status` takes in Phase 7 (never claim a
success that wasn't independently observed).

## 2026-09-06 — Real bugs found and fixed this phase (both caught by testing, not shipped)

1. **MissionNet asset sync wasn't covered by the new multi-adapter error isolation.**
   `run_ingestion_cycle` calls `sync_missionnet_assets` *before* the `ingest_all` loop that wraps
   every adapter/stream in its own try/except - a MissionNet outage during asset sync raised
   uncaught, aborting the whole cycle before Suricata/Zeek/any other adapter ever got a chance to
   run, exactly contradicting this phase's own requirement ("one failed adapter must not stop
   others"). Caught by manually pausing the MissionNet process mid-cycle. Fixed by wrapping the
   asset sync in the same try/except discipline, logging and continuing rather than aborting.
2. **A DB-only reset left stale sensor output on disk, contaminating unrelated scenarios.**
   Suricata/Zeek are file-based adapters with their own persisted cursor - clearing the database
   (via `services/event_ingestor/reset.py::reset()`, which every reset path including every Demo
   Control scenario's own automatic `lab_reset` goes through) resets that cursor to `None`, but the
   actual `eve.json`/Zeek log files on disk survived untouched. The very next unrelated scenario's
   own ingestion cycle would then re-ingest the *old* sensor output from scratch (fresh cursor, same
   stale file), fabricating a spurious `network-intrusion` incident interleaved with that scenario's
   own real one. Caught by a full-suite regression run: SCN-003's own incident-provenance test
   picked up the wrong (stray, `scenario_id: None`) incident because it was created before the real
   one in the same correlation pass. Fixed by having `reset()` itself also delete the generated
   Suricata/Zeek output directories - the fix lives in the one Python function every reset path
   shares, not duplicated in `scripts/reset-lab.sh`, so it's structurally impossible for a future
   reset path to forget it.

## 2026-09-06 — Phase 8: `mypy`'s canonical command now includes `integrations/`

Every prior phase's documented quality-gate command was `mypy ai services apps domain evaluation` -
`integrations/` (present since Phase 1's MissionNet adapter) was never actually in that list, an
oversight rather than a deliberate exclusion. Phase 8 adds five new packages under `integrations/`,
making the gap too large to keep overlooking. The canonical command is now `mypy ai services apps
domain evaluation integrations` (109 files, clean) - documented here so a future phase's "the
usual command" doesn't silently drop it again.

## 2026-09-06 — Phase 7: `execution_status` is a second, independent field - never folded into `status`

Phase 6 deliberately kept a single `status` column because approval and execution weren't yet
separable concepts (see the Phase 6 entry below on this exact question, which explicitly flagged
"revisit if a later phase's execution status genuinely needs to diverge from approval status"). Phase
7 is that later phase: a plan can be `APPROVED` and simultaneously `NOT_EXECUTED`, `EXECUTING`,
`SUCCEEDED`, `FAILED`, or `ROLLED_BACK` - five genuinely different real-world states that all share
one `status` value. Rather than overload `status`'s vocabulary (which would make "is this plan
approved" a substring check against values like `EXECUTING`), `ResponsePlan` gained a second column,
`execution_status`, with its own independent state machine. `status` still answers exactly one
question - did a human approve this plan - and `execution_status` answers a completely different one
- what has actually happened to MissionNet as a result. The API layer (`execution_routes.py`) and UI
(`viewFor()` in `response-center/page.tsx`) both compute derived views from the pair, never from
either field alone.

## 2026-09-06 — Phase 7: execution is a second, explicit human action - never automatic on approval

Approving a `ResponsePlan` (`POST /response-plans/{id}/approve`) only ever sets `status="APPROVED"`;
no code path anywhere touches `execution_status` as a side effect of approval. A human must issue a
separate `POST /response-plans/{id}/execute` call, and the dashboard's `ExecutionControls` component
requires an explicit confirmation dialog naming the playbook and actor before making that call. This
is the phase's central safety property, not an implementation detail: the LLM's role stops at
recommending a playbook ID (Phase 5/6), the policy engine's role stops at declaring a playbook
eligible (Phase 6), and now the executor's role never begins until a human takes a second, distinct
action after having already seen the fully-approved plan. Collapsing approve+execute into one click
was considered (it would make the flagship demo one step shorter) and rejected - it would erase the
one place in the whole system where "the AI queued this, a human approved it" and "MissionNet's real
state actually changed" are forced to be observably different events.

## 2026-09-06 — Phase 7: `required: bool` on `PlaybookAction` governs success/skip, not resolvability

RP-005 (Multi-Signal Incident Containment) is eligible across four different incident categories
with structurally different evidence shapes - some are purely asset-based with no identity/token in
evidence, some are identity-based with no degraded asset. Its `revoke_test_token` step therefore
can't always resolve a target, even for a genuinely eligible incident. Rather than either (a) blocking
execution whenever any action's target is unresolvable, which would make RP-005 permanently
unexecutable for asset-only incidents, or (b) silently treating every unresolvable target as success,
which would let a plan claim `SUCCEEDED` while a token that should have been revoked never was, each
`PlaybookAction` gained a `required: bool = True` field (`services/policy_engine/playbooks.py`).
Only `revoke_test_token` in RP-005 is `required: false`. The executor's rule: an unresolvable
`required=false` target action is `SKIPPED` and never blocks or fails the plan; an unresolvable
`required=true` target blocks execution before anything runs; and the plan's overall `SUCCEEDED`
determination only ever considers `required=true` actions' status and verification. Verified live:
the SCN-010 flagship incident (asset-only, no identity signal) executed RP-005 to `SUCCEEDED` with
`revoke_test_token` correctly `SKIPPED`, not `FAILED`.

## 2026-09-06 — Phase 7: targets resolve twice - once to decide whether to block, once per action to run

Every action's target is resolved (`services/response_executor/targets.py::resolve_target`) from
trusted stored context only: the incident's own linked `NormalizedEventRecord`s (for a user/token) or
its own `primary_asset_id`/evidence (for an asset) - never from the action definition, never from
free-form input. Resolution happens twice for a reason. First, an up-front pass before any action
runs decides whether execution should even start (a `required=true` action with no resolvable target
blocks the whole plan via `_block()`, before `execution_status` ever leaves `NOT_EXECUTED`). Second,
immediately before each action actually executes, its target is resolved again, fresh, using the
plan's own in-progress results so far. This second resolution is not redundant - it's what let a real
bug get caught and fixed this phase (see "real bugs found" below): `verify_service_health`'s target
depends on whether `request_replacement_instance` already ran earlier in the *same* execution, which
an up-front-only resolution computed before any action ran could never see.

## 2026-09-06 — Phase 7: verification always re-reads real MissionNet state, never trusts the action's own HTTP 200

`services/response_executor/verifier.py` has 8 functions, one per playbook `expected_verification`
value, and every one of them makes its own independent `GET` call against MissionNet after the
action already ran - `verify_service_health` re-reads the replacement asset's status, `token_invalid`
re-reads the token's `valid` flag, and so on. An action handler returning HTTP 200 proves the *request*
succeeded, not that the state change actually took effect or is still true a moment later - conflating
the two was exactly the failure mode this phase's verification requirement (blueprint §12) exists to
rule out. This is also why resuming a crashed plan re-verifies every previously-`SUCCEEDED` action
rather than trusting its persisted `verification_status`: a test that inserted a fake "already
succeeded and verified" `ActionResult` without actually calling MissionNet's suspend endpoint was
correctly caught by this design (verification failed, since the user genuinely wasn't suspended) -
fixed by making the test actually perform the action first, not by weakening verification.

## 2026-09-06 — Phase 7: rollback claims `NOT_APPLICABLE`, never a false `ROLLED_BACK`

`services/response_executor/rollback.py::ROLLBACK_HANDLERS` covers only 4 of the 8 registered
actions - `preserve_evidence` (undoing a snapshot isn't meaningful), `request_replacement_instance`
(a provisioned replacement asset is a real Phase-7-forward fact, not a mistake to undo), and
`verify_service_health` (a read-only check has no state to reverse) intentionally have no handler.
When `_run_rollback` reaches an action with no registered handler, it sets
`rollback_status="NOT_APPLICABLE"` and moves on - it never marks an action `ROLLED_BACK` unless a
handler actually ran and MissionNet's state actually changed back. This mirrors the same principle as
verification: a status field must only ever describe something that was actually observed to happen,
never something assumed. `rollback_rotate_test_token` is the one handler that reverses two facts at
once (revokes the new, rotated token AND reactivates the original) using `old_token_id`/`new_token_id`
persisted in the original action's own `result_metadata` - proof that idempotent, deterministic child
IDs (`{token_id}-rotated`) are enough to make rollback correct without a separate "undo log."

## 2026-09-06 — Phase 7: `ActionResult` rows keyed by `(response_plan_id, action_index)` make resume idempotent by construction

Rather than adding a "has this plan been partially executed" flag or a separate resume code path, the
executor's main loop always runs the same way: for each action index, check whether an `ActionResult`
already exists with status `SUCCEEDED`/`SKIPPED`, and if so, move on without calling MissionNet again.
A crash between actions, a duplicate `execute` call from a double-clicked button, or a genuine
retry after a transient MissionNet outage are all the identical code path - there is no special
"resuming" state to get wrong. The unique constraint on `(response_plan_id, action_index)` makes a
duplicate `ActionResult` for the same action structurally impossible at the database level, not just
avoided by application logic. Verified live: calling `execute` twice on an already-`SUCCEEDED` plan
left the action count unchanged at 4.

## 2026-09-06 — Phase 7: the executor imports `services.ai_analyst.evidence`, not `ai.providers` - documented, not accidental

`services/response_executor/executor.py::_revalidate` calls `build_evidence_pack` and
`evaluate_policy` again immediately before execution, to catch an incident that stopped being
eligible between approval and execution (e.g. it was resolved, or a playbook was disabled, in the
interim). `build_evidence_pack` lives in `services/ai_analyst/evidence.py`, which makes it, by path,
look like an AI-package import - but the function itself only reads `NormalizedEventRecord`/
`Detection`/`Incident` rows and returns a plain dataclass; it never touches `ai.providers`, never
calls a model, and Phase 6's `policy_engine.service` already relied on this exact same function for
the identical reason. `tests/adversarial/test_executor_ai_isolation.py` encodes this distinction
explicitly: `FORBIDDEN_MODULE_PREFIXES` names `ai.providers`, `ai.schemas`, and
`services.ai_analyst.service` (the actual LLM-orchestrating module) but deliberately excludes
`services.ai_analyst.evidence`, with an inline comment and a dedicated positive test asserting the
evidence import IS present while the two forbidden ones are NOT - so a future reader (or reviewer)
doesn't "fix" this into a wholesale `services.ai_analyst` ban that would break revalidation.

## 2026-09-06 — Real bugs found and fixed this phase (both caught by testing, not shipped)

1. **Stale MissionNet server.** The `uvicorn` process serving MissionNet had been running since a
   much earlier phase without `--reload` (see the existing entry below on why `--reload` isn't
   default for lab servers) and never picked up the 5 new `/lab/*` endpoints this phase added. The
   first live execution attempt 404'd on `request_replacement_instance` and correctly rolled back -
   the executor behaved exactly as designed given a genuinely broken dependency. Fixed by restarting
   the process; not a code bug, but a re-confirmation of the same operational lesson from Phase 5/6.
2. **Target-resolution timing bug** (a genuine executor bug, not a test artifact). Targets were
   originally resolved once, entirely up front, before any action ran. `verify_service_health`'s
   target-preference logic (prefer a same-plan `request_replacement_instance` result over the
   original, still-quarantined asset) therefore could never see that action's outcome, since it
   hadn't happened yet at resolution time - `SUCCEEDED` plans were incorrectly ending up
   `ROLLED_BACK`. Fixed in `executor.py` by re-resolving each action's target immediately before it
   runs (see the target-resolution entry above); the up-front pass is now used only to decide whether
   to block execution before it starts.

## 2026-09-06 — Phase 6: `allowed_asset_types` matches MissionNet's `mission_role`, not Sentinel's
`asset_type`

The blueprint's example playbook schema uses `allowed_asset_types: [telemetry_gateway]`, implying
Sentinel's own `SentinelAsset.asset_type` column as the discriminator. But every asset MissionNet
seeds has `asset_type == "service"` (`apps/missionnet/seed.py`) - that column can never distinguish
one playbook's eligible assets from another's in this deployment. The field that actually varies is
MissionNet's own `mission_role` (`identity`/`gateway`/`data`/`edge`), already carried through to
Sentinel as `SentinelAsset.extra["mission_role"]` since Phase 2. `services/ai_analyst/evidence.py::
EvidenceAsset` gained a `mission_role` field for this reason, and `services/policy_engine/engine.py`
matches `allowed_asset_types` against it, not `asset_type`. The YAML field keeps its blueprint name
for fidelity to the spec's shape; only its *values* and the column they're checked against changed -
documented here so nobody "fixes" it back to `asset_type` and silently makes every asset-scoped
playbook match every asset.

## 2026-09-06 — Phase 6: RP-005 eligibility is detection count, not incident category

`services/incident_engine/engine.py` sets an incident's `category` once, at creation, from
whichever detection happened to arrive first - it's never updated when later detections merge into
the same incident (only severity/last_seen/mitre_techniques are). This means a genuinely
multi-signal incident (SCN-010's flagship: DET-002 + DET-004 + DET-005, all on one asset) ends up
with a single-detection-looking `category` like `"asset-degradation"`, not anything that says
"multi-signal." Rather than add a new incident-engine feature to compute a real "multi-signal"
category (out of scope for a Phase 6 response-planning task, and a change to already-shipped,
tested Phase 2 behavior), RP-005 lists every category a multi-signal incident could plausibly carry
*and* requires `minimum_detection_count: 2` (`PlaybookDefinition.minimum_detection_count`,
`services/policy_engine/engine.py`'s own check). This correctly makes RP-005 eligible exactly when
an incident has multiple correlated detections, independent of which category label it happened to
land on - verified live: the SCN-010 flagship incident shows both RP-003 and RP-005 as eligible, and
the real local AI model recommended RP-005 for it unprompted.

## 2026-09-06 — Phase 6: policy bundle version moved from `settings.policy_bundle` to code

`apps/api/config.py` previously had a placeholder `policy_bundle: str = "PB-local-dev"` field, set
before any real policy engine existed. Now that `services/policy_engine/engine.py` implements real,
versioned rules, `POLICY_BUNDLE_VERSION = "PB-001"` was moved into that module as a plain constant
and the `settings.policy_bundle` field (plus `SENTINEL_POLICY_BUNDLE` in `.env`/`.env.example`) was
removed entirely, rather than kept as parallel, driftable configuration. A policy bundle version
describes which deterministic rules are *actually loaded in this process* - that can only be true
of a value in the code implementing those rules, never a string in an env file that could disagree
with it. `scripts/healthcheck.sh`'s old "Policy bundle present" check (which tested the now-removed
env var) was replaced with "Playbook catalog loads (5 playbooks)" - a check against real, observable
behavior instead of a config string's mere presence. `knowledge_bundle` stays a settings placeholder,
deliberately, since no real knowledge bundle exists until RAG is built.

## 2026-09-06 — Phase 6: a `ResponsePlan` row's mere existence already proves it passed policy

`services/policy_engine/service.py::create_response_plan` evaluates policy *before* ever
constructing a `ResponsePlan` object - if `evaluate_policy` returns `allowed=False`, the function
writes one audit entry (`response_plan.policy_evaluated`, so the attempt itself has provenance) and
returns `(None, decision)` without touching the `response_plans` table at all. This means there is
no `ResponsePlan` row anywhere in the database, ever, whose policy was `DENY` - a query for "how many
denied plans exist" is always zero by construction, not by convention. The alternative (persist
every attempt, including denied ones, with a `DENIED` status) was considered and rejected: it would
mean every reader of `response_plans` needs to remember to filter by policy outcome, whereas "a row
exists" being sufficient proof of eligibility is a stronger, harder-to-misuse invariant. Denied
attempts are still fully auditable via `audit_log`, just not via a table row.

## 2026-09-06 — Phase 6: `DRAFT`/`POLICY_REVIEW` are vocabulary-only; policy evaluation is
synchronous

The blueprint's approval lifecycle names `DRAFT -> POLICY_REVIEW -> AWAITING_APPROVAL -> APPROVED/
REJECTED`, suggesting policy evaluation might be a distinct, observable step. In this phase it is
synchronous - `create_response_plan` evaluates policy and, if allowed, persists straight into
`AWAITING_APPROVAL` in the same function call, in the same transaction as the policy-evaluated audit
entry. There is no `DRAFT` state a plan sits in while awaiting evaluation, and no `POLICY_REVIEW`
state to poll. Both remain valid values in `ResponsePlanStatus`/the `status` column's vocabulary
(for schema/API forward-compatibility, and in case a future phase makes evaluation asynchronous -
e.g. if it starts depending on a slow external check) but no code path in this phase ever sets a
plan to either. Similarly, `EXPIRED` is a defined, valid status with no TTL/timeout mechanism behind
it yet - reserved, not implemented.

## 2026-09-06 — Phase 6: no separate `approval_status` column - `status` is the single source of
truth

The blueprint's suggested `ResponsePlan` fields list both `status` and `approval_status` as
separate columns. `domain/models/orm.py::ResponsePlan` implements only `status` (one of
DRAFT/AWAITING_APPROVAL/APPROVED/REJECTED/CANCELLED/EXPIRED) - a plan's approval state and its
overall lifecycle state are the same thing in Phase 6 (there is no state a plan can be in that's
"approved" but not "AWAITING_APPROVAL -> APPROVED", since execution doesn't exist to have its own
separate status track yet). Keeping two columns that would always need to agree is exactly the kind
of duplicate-source-of-truth bug this project actively avoids elsewhere (see the incident-status /
`TERMINAL_INCIDENT_STATUSES` shared-constant decision). Revisit if a later phase's execution status
genuinely needs to diverge from approval status (e.g. an approved-but-failed-to-execute plan).

## 2026-09-06 — Phase 6: AI Analyst's evidence pack now computes real playbook eligibility

`services/ai_analyst/evidence.py::build_evidence_pack` imports `services.policy_engine.engine::
compute_eligible_playbook_ids` (lazily, inside the function, to avoid a module-level import cycle -
`policy_engine.engine` itself takes an `EvidencePack` as input, so it must be able to import
`ai_analyst.evidence`'s types first). This is the only cross-package dependency in either direction:
`policy_engine` never imports anything from `ai_analyst` or `ai/` at module scope, keeping the
policy engine's "never touches the AI" guarantee (`docs/policy-engine.md`) intentionally easy to
verify by grep, not just by reading control flow.

## 2026-09-06 — Existing Phase 4/5 assurance tests already covered this correctly; no regressions
introduced

Phase 6 added five new `SystemAssuranceOut` fields (`response_planning`, `policy_engine`,
`human_approval`, `response_execution`, `autonomous_response`) with fixed defaults matching the
blueprint's required literal strings exactly (`"ENABLED"`, `"OPERATIONAL"`, `"DISABLED - NEXT
PHASE"`, etc.) - these are not computed from any live check, unlike `ai_analyst_status`, because
there is nothing to truthfully *check* yet (no execution engine, no autonomous-agent code path to
query the state of). This is consistent with `response_authority: "NONE"` already being a fixed
Phase 5 default rather than a computed value, for the same reason: a field can only be "truthfully
computed" once the thing it describes exists to observe.


## 2026-09-06 — Phase 5: MLX loads in-process, not as a separate `mlx_lm.server` sidecar

`ai/providers/mlx_provider.py::MLXProvider` calls `mlx_lm.load()`/`mlx_lm.generate()` directly
inside the Sentinel API worker process, lazily on the first `POST .../ai/analyze` call, rather than
running `mlx_lm.server` as a second process and talking to it over `SENTINEL_LLM_BASE_URL` (the
config field the Phase 0 scaffold already had, suggesting that was the original plan). In-process
won because: (1) it's one fewer moving part to start/monitor/restart on a 16GB Lite-profile laptop;
(2) `ai/providers/get_provider()` being a process-wide singleton is what actually guarantees "never
load the model twice" - a separate server process doesn't need that guarantee enforced in Python,
but then nothing stops someone from accidentally starting two server instances; (3) the
`LLMProvider` Protocol boundary (`ai/providers/base.py`) already isolates all MLX-specific code to
one file - `apps/api/`, `apps/dashboard/`, and `services/ai_analyst/` never import `mlx`/`mlx_lm`
directly, so the "Sentinel's API/dashboard must not depend directly on MLX-specific code"
requirement is satisfied without needing a network boundary too. The tradeoff: the model's ~3GB
footprint now lives inside the same process as the rest of the API, so an MLX crash could in theory
take the API down with it - mitigated by `_ensure_loaded()` catching every load exception and
setting `DEGRADED` status rather than propagating, and `structured_completion` never being called
from anywhere except `services/ai_analyst/service.py`'s already-isolated `run_analysis`. Revisit if
a later phase wants to run inference on a separate machine/GPU.

`scripts/healthcheck.sh`'s old "Local model endpoint" check (`curl .../v1/models`, written for the
sidecar-server design) was replaced with a check against Sentinel's own `/api/v1/ai/status` -
non-critical, passes whether AI is enabled or not, since a fresh checkout with
`SENTINEL_AI_ENABLED=false` is exactly as healthy as one with it on.

## 2026-09-06 — Provider abstraction: `LLMProvider` Protocol + `mock`/`mlx`, closed allowlist

`ai/providers/base.py::LLMProvider` is a `typing.Protocol` with exactly one capability
(`structured_completion`) plus two read-only status methods (`get_status`, `get_provenance`) - no
method that could plausibly write anything, by construction. `ai/providers/__init__.py::
build_provider` is a closed `if/elif/raise` over provider names, not a registry/plugin system - adding
a cloud provider means adding a new module and a new `elif` branch that a reviewer will see, not
silently working because someone typed a new string into `.env`. `SENTINEL_LLM_PROVIDER=mock` (the
`.env.example` default) is a deterministic in-process stand-in used by every fast test; `mlx` is the
only real inference path. `get_provider()` caches one singleton per `(provider_name, model_name)` -
the whole point being that the 16GB Lite profile must never have two real models resident at once.

## 2026-09-06 — Evidence Pack: curated fields only, hashed, no playbook catalog yet

`services/ai_analyst/evidence.py::build_evidence_pack` reads exactly: the incident's own columns,
its linked detections (with their own linked event IDs), its linked normalized events, the primary
asset's context if any, and the union of MITRE technique IDs already attached by deterministic
code. No raw SQL, no unbounded query, no other table. `available_playbook_ids` is hardcoded to `[]`
in Phase 5 - no playbook catalog exists yet (`playbooks/` is still an empty scaffold directory from
Phase 0), so there is nothing real to populate it with; inventing a fake allowlist just to exercise
the field would violate the same "no fabricated content" rule this whole project runs on. The pack
is sha256-hashed (`evidence_pack_hash`, recorded on every `AIAssessment` row) so two assessments of
the same incident can be checked for whether the underlying evidence actually changed between them
without diffing the full JSON.

## 2026-09-06 — Structured output: schema validation and hallucination validation are two separate,
both-mandatory gates

`ai/schemas.py::AIIncidentAssessment` (`extra="forbid"`, `confidence` bounded via `Field(ge=0.0,
le=1.0)`) only proves the model's output has the right *shape*. `services/ai_analyst/validation.py
::validate_assessment` separately proves it has the right *content* - every `event_id`/
`detection_id`/entry in `affected_assets`/`recommended_playbook_id` must exist in the literal
evidence pack that was sent. A single invented ID anywhere rejects the *entire* assessment
(`validation_status = REJECTED_HALLUCINATION`, `assessment = null` in the persisted row) - there is
deliberately no partial-credit mode that shows the valid-looking fields and hides only the bad one,
because a human analyst skimming a mostly-real assessment with one fabricated citation buried in it
is exactly the failure mode this project's "no fabricated detections/incidents/events" rule exists
to prevent, extended to AI output.

**A real instance of this firing, found via the live SCN-010 browser verification (not a
hypothetical)**: the first real-model analysis of a genuine, live incident returned
`affected_assets: ["u-operator-01"]` - a real, correctly-spelled user ID, but a *username*, not an
*asset* ID, and this identity-only incident has no `primary_asset_id` at all (`affected_assets`'
valid set was therefore empty). Validation correctly rejected it as `REJECTED_HALLUCINATION`. This
was not "the model hallucinating a fake ID" in the adversarial sense - it was reasonable behavior
given an ambiguous field name and no better place to put the user identity - so the fix was to
clarify `ai/prompts/incident_analysis_v1.txt`'s field semantics ("affected_assets is for ASSET IDs
only... leave it empty for identity-only incidents"), not to loosen `validate_assessment`. Re-running
the same incident after the prompt fix produced `affected_assets: []` and a clean `VALID` result.
Re-running the full 14-case evaluation harness (`evaluation/llm/cases.py`) before/after this fix
moved `hallucination_free_rate` from `0.857` (12/14 - the same failure mode hit two other
identity/token-only cases) to `1.0` (14/14), with `schema_valid_rate` and `keyword_match_rate`
unaffected - see PROGRESS.md for the full before/after numbers.

## 2026-09-06 — `SENTINEL_LLM_MAX_TOKENS` raised from an initial 700 to 1500

The first live SCN-010 analysis attempt returned `PROVIDER_ERROR` with "Unterminated string" - the
model's own JSON output was cut off mid-field by the 700-token cap on a 3-event incident with
several list fields (`hypotheses`, `recommended_investigation_steps`, `evidence_refs` each with a
`relevance` string). A direct measurement (`mlx_lm.generate` against a single-event evidence pack)
showed ~450 tokens for a *minimal* response; a 3-event incident with more to say needs
comfortably more. 1500 gives real responses (observed 400-900 tokens in practice) generous headroom
without materially increasing worst-case latency, since generation stops at the model's own
end-of-message token, not at the cap, for any response that actually finishes.

## 2026-09-06 — AI Analyst has no write path to any table except `ai_assessments`/`audit_log` - by
construction, not by policy

`services/ai_analyst/service.py::run_analysis` is the only function that persists AI output, and it
touches exactly two tables. No module under `ai/` or `services/ai_analyst/` imports
`domain.models.orm.Incident`/`Detection`/`SentinelAsset` for writing, imports `apps.missionnet`, or
calls any adapter. This means the "AI cannot create/modify a detection or incident, cannot change
severity/status/disposition, cannot touch MissionNet/firewall/credential/container/OS state" set of
constraints from the Phase 5 spec hold structurally, not because the system prompt asks nicely - see
`docs/ai-security-boundaries.md` and the adversarial tests in `tests/adversarial/`, which prove this
even when the model's output is constructed to look maximally compliant with an injected
instruction. This is also why `run_analysis` never raises: a provider failure only ever produces a
differently-labeled row in `ai_assessments`, never an unhandled exception that could take down the
request path shared with deterministic Sentinel endpoints.

## 2026-09-06 — Bugfix: `services/event_ingestor/reset.py` missing `AIAssessment` (third occurrence)

Same bug class as the Phase 4 `IncidentNote`/`AuditLogEntry` omission: a new table
(`ai_assessments`, FK to `incidents.incident_id`) was added without updating `_DELETE_ORDER` in the
shared reset script, which would have caused a foreign-key violation the next time `make
sentinel-reset` ran against a database with any AI assessment rows. Caught and fixed before it ever
shipped, but this is now the *third* time a new Phase's table has hit this exact bug - worth a
standing habit: grep `_DELETE_ORDER` whenever a migration adds a table with a FK into
`incidents`/`detections`/`normalized_events`, rather than relying on remembering to update it.

## 2026-09-06 — Pre-existing gap noted, not fixed: `scripts/offline-check.sh` does not exist

`Makefile`'s `offline-check` target and `RUNBOOK.md`'s "Offline check" section both reference
`scripts/offline-check.sh`, but the file isn't in the repository - discovered while documenting
Phase 5's own offline behavior (verified manually instead: `HF_HUB_OFFLINE=1` model load succeeds
against the already-cached model). This predates Phase 5 and isn't caused by anything in this
phase; writing a full offline-check script is out of scope for an AI Analyst phase and is flagged
here rather than silently worked around, so a future phase (or this one, if asked) can pick it up
deliberately.

## 2026-09-06 — Bugfix: don't assert a live server's response against this test process's mutable
`settings` object

`test_assurance_reports_truthful_state_no_fake_certifications` initially asserted
`assurance["ai_analyst_status"]` against `apps.api.config.settings.ai_enabled` read in the *test
process*. That looked reasonable in isolation but is wrong: `/api/v1/system/assurance` is served by
a separately-running live uvicorn process whose `settings` were fixed at *its own* startup, while
`tests/integration/test_ai_analyst_api.py` and `tests/adversarial/test_prompt_injection*.py`
mutate the *test process's* `settings.ai_enabled` (True in setup, False in teardown) via FastAPI
dependency overrides against an in-process ASGI app. Because `pytest -q` runs every test file in
one process, whichever value those other files' teardown last left `settings.ai_enabled` at leaked
into this unrelated test - passing or failing depending entirely on file collection order, not on
anything actually wrong. Fixed by asserting internal consistency of the live response instead
(`ai_analyst_status == "NOT ENABLED"` iff `local_llm_runtime == "NOT ENABLED"`) rather than
comparing two independent processes' state through a shared mutable global. General lesson: a
process-wide singleton (`settings`) mutated by one integration test file's fixtures is never safe
to also read as an oracle from a different test file, even if it happens to hold "the right" value
during isolated runs of either file.

## 2026-09-06 — Bugfix: `uvicorn --reload` watching the whole repo caused a real hang during
development, not shipped in any test

While iterating on this phase, `--reload`'s default watch scope (the entire repository, not just
`apps/`) meant every edit to a test file or a `.md` doc triggered a full worker restart on the
already-running dev API - including, once, a restart that raced a live pytest run's TCP connection
and got stuck at "Waiting for connections to close" indefinitely, making the entire API
unresponsive (even `GET /health`) until the process was force-killed. This wasted real debugging
time (the initial symptom looked exactly like a hung MLX inference call, not a reload bug) before
`tail /tmp/sentinel_api.log` showed the actual `WatchFiles detected changes... Reloading...
Shutting down` sequence. Not a code change - just a documented operational gotcha: prefer running
the dev API *without* `--reload` while actively editing files outside `apps/`/`domain/`/`services/`
during a test session, and restart it manually (`make api` already uses `--reload` for normal
day-to-day backend iteration, which is fine when edits are confined to Python source under active
watch, just not while a pytest run is also hitting the same port).

## 2026-09-06 — Existing Phase 4 assurance test updated for a truthful, not hardcoded, AI state

`tests/integration/test_coverage_and_assurance.py::
test_assurance_reports_truthful_state_no_fake_certifications` originally hardcoded `ai_analyst_status
== "NOT ENABLED"`, which was correct *only* because Phase 5 didn't exist yet. Now that
`SENTINEL_AI_ENABLED=true` is this machine's real, intended end-state (System Assurance correctly
reports `OPERATIONAL`), the test was updated to assert *truthfulness relative to config* rather than
a specific hardcoded value - if `settings.ai_enabled` is true it must report one of
`OPERATIONAL`/`LOADING`/`DEGRADED` (never a fabricated `NOT ENABLED`), and if false it must report
exactly `NOT ENABLED`. The test's actual point - no fabricated certification language, real
integration statuses - was preserved and strengthened (added assertions for the new
`response_authority`/`rag_status` fields), not weakened.

## 2026-09-06 — Phase 4: SSE, not polling, for the main SOC dashboard

`apps/api/stream_routes.py` exposes `GET /api/v1/stream`, an async generator yielding a full
snapshot (`event: snapshot`) every 2 seconds over `StreamingResponse(media_type="text/event-stream")`.
`apps/dashboard/app/LiveDataProvider.tsx` opens exactly one `EventSource` per browser tab (in a
context provider wrapping the whole app) and every live page (`OverviewLive`, `IncidentsLive`)
reads from that single shared connection via `useLiveData()`.

This is the opposite choice from Phase 3's Demo Control run page, which polls every 1.5s — and the
difference is deliberate, not inconsistent: a scenario run page has exactly one consumer watching
one short-lived (2-5s) resource, where poll latency barely matters and a dedicated connection isn't
worth the complexity. The SOC dashboard has multiple pages that all want the *same* live counts
simultaneously (Overview's cards, Incidents' live table, potentially more later) for the entire
session, where N independent polling loops would mean N times the backend load for identical data.
One SSE connection, fanned out via React context, serves all of them from one query. `EventSource`
also auto-reconnects on drop with no custom retry logic needed, which satisfies the "reconnect
behavior" requirement in the Phase 4 spec for free.

## 2026-09-06 — Incident workflow status vocabulary is deliberately narrower than the blueprint's

`domain/incidents.py` defines `INCIDENT_STATUSES = (OPEN, INVESTIGATING, MONITORING, RESOLVED,
DISMISSED)` and `TERMINAL_INCIDENT_STATUSES = (RESOLVED, DISMISSED)`. This is an *earlier*, simpler
state machine than the blueprint's full response lifecycle (which includes playbook
recommendation/approval/execution states that don't exist until Phase 6-7) — it covers exactly what
a human analyst can do to an incident today: investigate it, watch it, close it with a disposition.
When Phase 6 adds playbooks, this vocabulary should be *extended* (e.g. an
`AWAITING_APPROVAL`/`CONTAINMENT_IN_PROGRESS` status) rather than replaced, since OPEN through
DISMISSED remains a valid description of pre-response incident state. `IncidentDisposition`
(TRUE_POSITIVE/BENIGN_TRUE_POSITIVE/FALSE_POSITIVE/TEST_SCENARIO/UNDETERMINED) is a separate field
from status specifically so "why did we close it" survives independently of "what state is it in."

Both tuples live in one module imported by `services/incident_engine/engine.py` and
`apps/api/routes.py` so the two can't drift — a stale duplicate of the old `"closed"` literal
(pre-dating this vocabulary) had already caused exactly that kind of drift once (see the bugfix
entry below), which is why the constant is now shared rather than each caller defining its own.

## 2026-09-06 — Audit design: one shared `write_audit()` helper, called from every write path

`domain/audit.py::write_audit()` is the single function that inserts into `audit_log`
(timestamp, entity_type, entity_id, action, actor, source, scenario_id, detail-as-JSON). It's called
from the ingestion service (`ingestion.cycle_completed`), the detection engine
(`detection.created`), the incident engine (`incident.created`, `incident.detection_merged`), and
all four incident-workflow API endpoints (`incident.status_changed`, `incident.assigned`,
`incident.note_added`, `incident.disposition_set`) — one call site per meaningful state change,
never a generic "log everything" middleware, so `detail` can carry a genuinely useful structured
payload (e.g. `{"old_status": "OPEN", "new_status": "INVESTIGATING"}`) specific to that action rather
than a generic request/response dump. `audit_log` is append-only by convention (no UPDATE/DELETE
route exists for it anywhere in the API) and is not itself versioned/partitioned — acceptable at
this prototype's volume; revisit if it ever needs retention limits.

No new indexes were added on `audit_log` or the other Phase 4 tables beyond what the migration's
autogenerated primary/foreign keys provide — table sizes at this prototype's scale (a handful of
scenario runs, dozens of incidents) don't yet justify a composite index on
`(entity_type, entity_id)` or `(scenario_id)`. Revisit if the Audit page's query time becomes
noticeable against a much larger synthetic dataset.

## 2026-09-06 — Detection Coverage validation status is computed live over HTTP, never joined via a shared DB

`apps/api/coverage_routes.py` fetches Demo Control's `GET /api/v1/scenarios` (for the static
scenario→rule mapping) and `GET /api/v1/runs` (for PASS/FAIL history) over real HTTP, the same way
the Sentinel dashboard would observe *any* external system — not via a shared database or a
cross-app Python import, even though both are running on the same machine and it would have been
one line to just join tables directly. Both calls are wrapped in `try/except httpx.HTTPError`,
logging a warning and returning empty dicts so the page degrades to "NOT_TESTED for everything"
rather than crashing if Demo Control is down. `validation_status` per rule is genuinely derived:
VALIDATED only if a real run mapped to that rule PASSED, FAILED only if one failed and none passed,
NOT_TESTED otherwise — there is no code path that can report VALIDATED without a real Demo Control
run existing. `tests/integration/test_coverage_and_assurance.py` locks in the exact SCN→DET mapping
as a regression test specifically so a future scenario edit can't silently change what "validates"
a rule without a test failing.

## 2026-09-06 — System Assurance page: literal truthful values, not a maturity score

`apps/api/assurance_routes.py` (replacing Phase 2's inline stub in `main.py`) does real work per
field rather than returning a static document: `_reachable()` does an actual `GET /health` with a
2-second timeout against MissionNet and Demo Control, and a real `SELECT 1` against Postgres wrapped
in try/except. Every value is one of a small set of literal, uppercase strings the Phase 4 spec
requires verbatim (`"ONLINE"`/`"OFFLINE"`, `"ACTIVE"`/`"NOT_CONFIGURED"`, `"DISABLED"`,
`"NOT ENABLED"`) rather than a synthesized percentage or maturity score, because a computed "88%
ready" figure would imply a methodology this prototype doesn't have and can't defend. The page's own
copy states plainly that "mapping to controls is not certification" and never mentions
DoD/CMMC/FedRAMP/classified-ready — enforced by
`test_system_assurance_reports_external_ai_disabled` asserting those strings are absent from the
response.

## 2026-09-06 — Scenario-id provenance gap: MissionNet's public endpoints, fixed; TelemetrySample, not yet

Two related provenance gaps surfaced while building Phase 4's Incident Detail provenance section
(section G), which needed every incident's `scenario_id` to be genuinely non-null when it should be:

1. **Fixed.** Demo Control's action functions (`apps/demo_control/actions.py`) and MissionNet's
   public `POST /identity/login` / `GET /mission-data/records/{id}` endpoints never forwarded
   `scenario_id`, even though the `/lab/*` endpoints have supported a `ScenarioContext` with
   `scenario_id` since Phase 2/3. Any incident whose *only* evidence came from an auth-failure or
   record-access signal (rather than an asset-degrade or token-revoke signal, which do go through
   `/lab/*`) would have shown `scenario_id: null` despite genuinely originating from a scenario.
   Fixed by adding `scenario_id` to `LoginRequest` and the record-access query params
   (`apps/missionnet/schemas.py`, `routes.py`), and having every Demo Control action forward
   `parameters.get("scenario_id")` (`actions.py`) with the runner injecting it into every step's
   parameters (`runner.py`). Verified via a real SCN-010 run showing `scenario_id: "SCN-010"`
   correctly on all three resulting incidents.
2. **Not fixed — documented as a known limitation instead.** MissionNet's `TelemetrySample` table
   (`apps/missionnet/models.py`) has no `scenario_id` column at all (unlike `AuditEvent`), so
   `telemetry.sample` normalized events can never carry scenario provenance, even when directly
   caused by a scenario's `inject_telemetry` action — discovered while visually QA-ing the Event
   Explorer's scenario column showing `—` on a telemetry event that was clearly part of a just-run
   SCN-010. This does not corrupt *incident*-level provenance (an incident's `scenario_id` is
   derived from the first non-null value across all its evidence events —
   `_detection_scenario_id()` in `services/incident_engine/engine.py` — and the co-occurring
   `asset.degrade`/`telemetry.inject` audit events do carry it correctly). Left unfixed in Phase 4
   because it requires a schema migration on MissionNet (`TelemetrySample.scenario_id`) plus
   threading `ScenarioContext` through the telemetry-sample-generation path, which is out of scope
   for a dashboard-hardening phase — worth picking up whenever MissionNet's schema is next touched.

## 2026-09-06 — Bugfix: `services/event_ingestor/reset.py` missing the new Phase 4 tables

Adding `IncidentNote` and `AuditLogEntry` (both FK-referencing or referenced-by `incidents`) without
updating `_DELETE_ORDER` in `reset.py` caused `ForeignKeyViolationError` on `DELETE FROM incidents`
the first time any test added a note before triggering a reset — the note row survived the delete
and blocked it. Fixed by adding `IncidentNote` (before `Incident`, since it's the child) and
`AuditLogEntry` (order-independent, no FK) to the tuple. Recorded because this is the second time a
new table has been added without updating this list (see the Phase 2 idempotency section) — any
future new table with a FK into an existing table needs the same treatment.

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
