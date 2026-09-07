# Response executor (Phase 7)

`services/response_executor/` is the one and only place in Sentinel that calls MissionNet to
actually change its state in response to an incident. It is a closed, deterministic package - no
LLM call anywhere in it - that runs an already-`APPROVED` `ResponsePlan`'s actions and records
exactly what happened. See `docs/verification-and-rollback.md` for the verification/rollback half of
this same package, and `docs/human-approval.md` for what happens before execution is even possible.

## The absolute rule

**The LLM never executes anything.** The AI Analyst (`ai/`, `services/ai_analyst/`) can recommend a
`playbook_id`. The policy engine (`services/policy_engine/`) can declare a playbook eligible. A
human can approve a plan. None of that calls MissionNet. Only a human's separate, explicit
`POST /response-plans/{id}/execute` call reaches this package, and this package is the only code
that imports `apps.missionnet.lab`'s Sentinel-only endpoints. `tests/adversarial/
test_executor_ai_isolation.py` proves, both by source-text scan and by walking the live
`sys.modules` graph at runtime, that nothing in `services/response_executor/` ever imports
`ai.providers`, `ai.schemas`, or `services.ai_analyst.service`.

## Package layout

| Module | Responsibility |
|---|---|
| `models.py` | Plain dataclasses (`ExecutionContext`, `ResolvedTarget`, `ActionOutcome`, `VerificationOutcome`) and exceptions (`ExecutionBlockedError`, `ExecutionInProgressError`, `PlanNotFoundError`) - no ORM, no HTTP. |
| `targets.py` | `resolve_target()` - the only place a MissionNet target (asset/user/token) is derived from an incident's own stored evidence. |
| `registry.py` | `ACTION_HANDLERS` - one function per registered action, each one real HTTP call to a named MissionNet endpoint. |
| `verifier.py` | `VERIFIERS` - one function per playbook `expected_verification` value, each an independent re-read of MissionNet state. |
| `rollback.py` | `ROLLBACK_HANDLERS` - one function per reversible action; actions with none get `NOT_APPLICABLE`, never a false `ROLLED_BACK`. |
| `executor.py` | Orchestration: `execute_response_plan()` and `rollback_response_plan()`, the only two public entry points. |

## The closed action surface

`registry.py::ACTION_HANDLERS` covers exactly the 8 actions in `services/policy_engine/actions.py`'s
registry - `revoke_test_token`, `rotate_test_token`, `suspend_test_user`, `quarantine_workload`,
`restore_workload_network` (rollback-only - it has no forward handler, only a rollback one),
`preserve_evidence`, `request_replacement_instance`, `verify_service_health`. There is no generic
"run this action" function that takes a name and dispatches dynamically to arbitrary code - each
handler is its own named function making its own named HTTP call, so grepping for `def handle_` in
`registry.py` is a complete, static list of everything this system can ever do to MissionNet.
`tests/unit/test_response_executor_registry.py::
test_no_forbidden_execution_primitive_anywhere_in_the_executor_source` additionally scans the whole
package's source for `execute_shell`, `ssh`, `execute_sql`, `docker_exec`, `firewall`, `run_script`,
`subprocess`, and `os.system` - none exist.

## Execution lifecycle

```
NOT_EXECUTED --execute()--> EXECUTING --> VERIFYING --+--> SUCCEEDED
                  |                                    |
          (pre-execution revalidation                  +--> FAILED --rollback()--> ROLLING_BACK --+--> ROLLED_BACK
           fails: stays NOT_EXECUTED,                                                              +--> ROLLBACK_FAILED
           execution_block_reason set,
           ExecutionBlockedError raised)
```

`execute_response_plan()` (`executor.py`):

1. **Idempotency/concurrency guard.** A terminal plan (`SUCCEEDED`/`FAILED`/`ROLLED_BACK`/
   `ROLLBACK_FAILED`) returns as-is without doing anything. An in-progress plan
   (`EXECUTING`/`VERIFYING`/`ROLLING_BACK`) raises `ExecutionInProgressError` -> HTTP 409.
2. **Pre-execution revalidation** (`_revalidate`) - re-checks everything that could have changed
   between approval and execution: `plan.status == APPROVED`, the incident and playbook still
   exist, the playbook is still enabled at the same version, the policy bundle version is
   unchanged, and a fresh `evaluate_policy` call still says `ALLOW`. Any failure calls `_block()`,
   which sets `execution_block_reason` and raises `ExecutionBlockedError` -> HTTP 422 *without*
   moving `execution_status` off `NOT_EXECUTED` - a blocked execution attempt leaves no trace on
   MissionNet and no ambiguity about whether anything ran.
3. **Up-front target check.** Every action's target is resolved once to decide whether execution
   should even start (a `required: true` action with no resolvable target blocks here); this
   up-front resolution is *not* reused to actually run the actions - see
   `docs/verification-and-rollback.md` and DECISIONS.md for why each action re-resolves its own
   target fresh, immediately before it runs.
4. **Main loop.** For each action, in order: skip if already `SUCCEEDED`/`SKIPPED` (crash/restart
   resume); re-resolve its target; `SKIP` if unresolvable and `required: false`; otherwise call the
   registered handler, persist an `ActionResult`, and stop the loop early if a `required: true`
   action fails.
5. **Verification phase** - see `docs/verification-and-rollback.md`.
6. **Final status** - `SUCCEEDED` iff every `required: true` action is `SUCCEEDED` with verification
   `VERIFIED`/`NOT_APPLICABLE`; otherwise `FAILED`, followed by automatic rollback if
   `plan.reversible`.

Every state transition writes an audit entry (`response_plan.execution_started`,
`.action_started`, `.action_result`, `.action_verified`, `.execution_succeeded`/`.execution_failed`,
`.rollback_started`/`.rollback_result`/`.rollback_completed`) - `GET /audit?entity_id=<incident_id>`
shows the complete chain.

## Executor versioning

`EXECUTOR_VERSION = "EX-001"` (`services/response_executor/__init__.py`) is stamped on every
`ResponsePlan` that reaches `EXECUTING`, alongside `executed_by` and the two timestamps. Bump it
whenever the executor's behavior changes meaningfully (a new action, a changed verification rule) -
existing executed plans keep whatever version ran them, so a historical plan's record stays an
honest description of the code that actually executed it, the same versioning discipline
`POLICY_BUNDLE_VERSION` already applies to the policy engine.

## Kill switch

`settings.response_execution_enabled` (`SENTINEL_RESPONSE_EXECUTION_ENABLED` in `.env`) gates both
execution endpoints at the API layer (`apps/api/execution_routes.py::_require_execution_enabled` ->
503 when false) without touching approval, policy, or planning - a deployment can run the entire
recommend/plan/approve chain with execution switched off, exactly as Phase 6 did before this
package existed.
