# Verification and rollback (Phase 7)

An action handler returning HTTP 200 proves the request was accepted - it does not prove MissionNet's
state actually changed, or is still true a moment later. This document covers the two mechanisms
that turn "we called the endpoint" into "we confirmed it worked," and how a plan un-does what it did
when it didn't. See `docs/response-executor.md` for the surrounding execution lifecycle.

## Verification is always a fresh, independent read

`services/response_executor/verifier.py::VERIFIERS` has one function per playbook
`expected_verification` value:

| `expected_verification` | What it re-reads |
|---|---|
| `token_invalid` | `GET` the token; confirms `valid == False`. |
| `token_rotated` | `GET` the new, rotated token by its deterministic ID; confirms it exists and is valid. |
| `user_suspended` | `GET` the identity user; confirms `status == "suspended"`. |
| `workload_isolated` | `GET` the asset; confirms `status == "quarantined"` and `network_state == "quarantined"`. |
| `network_restored` | `GET` the asset; confirms `network_state == "normal"`. |
| `evidence_snapshot_created` | `GET` the snapshot by its returned ID; confirms it exists. |
| `replacement_provisioned` | `GET` the replacement asset by its deterministic ID; confirms `status == "nominal"`. |
| `service_healthy` | `GET` the (possibly replacement) asset; confirms `status == "nominal"`. |

Every one of these is a brand-new HTTP call made *after* the action already ran and returned - never
a re-inspection of the action's own response body, and never a trust of its HTTP status code alone.
This is why resuming a plan after a crash re-verifies every already-`SUCCEEDED` action rather than
trusting the persisted `verification_status`: a persisted "VERIFIED" from three minutes ago says
nothing about whether the state is still true now (or was ever true, if the persisted row is a test
fixture instead of a real prior run - see DECISIONS.md for the test bug this caught).

`verification_status` values: `NOT_CHECKED` (default, before the verification phase runs),
`VERIFIED`, `FAILED`, `NOT_APPLICABLE` (the action has no `expected_verification` defined - occurs
for `SKIPPED` non-required actions).

## Success rule

A `ResponsePlan` reaches `execution_status = SUCCEEDED` if and only if every `required: true`
action's `ActionResult.status == "SUCCEEDED"` **and** its `verification_status` is `VERIFIED` or
`NOT_APPLICABLE`. A single required action that ran but failed verification is enough to make the
whole plan `FAILED`, even if every other action succeeded - there is no partial-success state and no
override.

## Rollback

`services/response_executor/rollback.py::ROLLBACK_HANDLERS` covers 4 of the 8 registered actions:

| Action | Rollback |
|---|---|
| `quarantine_workload` | `restore_workload_network` - returns the asset's network state to normal. |
| `suspend_test_user` | Reinstate the identity user to `active`. |
| `revoke_test_token` | Reactivate the original token. |
| `rotate_test_token` | Reverses *both* halves: reactivates the original token and revokes the rotated one, using `old_token_id`/`new_token_id` persisted in the original action's own `result_metadata` - no separate undo log needed. |

`preserve_evidence`, `request_replacement_instance`, and `verify_service_health` have no handler by
design - undoing a snapshot or a provisioned replacement asset isn't a meaningful "rollback," and a
read-only check has no state to reverse. An action with no handler gets
`rollback_status = "NOT_APPLICABLE"` when rollback runs - never `ROLLED_BACK`, since nothing was
actually reversed.

Rollback runs in **reverse action order** (undo the last thing first), and only ever touches actions
whose `ActionResult.status == "SUCCEEDED"` - an action that never ran, or that failed, has nothing to
roll back.

Two entry points share one internal implementation (`executor.py::_run_rollback`):

- **Automatic**, triggered when execution reaches `FAILED` and `plan.reversible` is true - happens
  in the same call as `execute()`, no separate human action needed to clean up a failed attempt.
- **Manual** (`rollback_response_plan()` / `POST /response-plans/{id}/rollback`) - available from a
  terminal `SUCCEEDED` or `FAILED` execution state, requires `plan.reversible` and at least one
  `SUCCEEDED` action, otherwise raises `PlanStateError` -> HTTP 409. This is how an analyst
  deliberately un-does a successful containment once the underlying issue is resolved (e.g. restore
  a quarantined asset to service).

Final rollback status: `ROLLBACK_FAILED` if any rollback action itself failed, else `ROLLED_BACK` if
at least one succeeded, else the plan stays `FAILED` (nothing was reversible). Every rollback action
writes its own `response_plan.rollback_result` audit entry, and the whole rollback attempt writes
`response_plan.rollback_started`/`.rollback_completed`.
