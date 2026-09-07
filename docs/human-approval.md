# Human approval workflow (Phase 6; execution is Phase 7 - see docs/response-executor.md)

A `ResponsePlan` row only ever exists because `services/policy_engine/engine.py::evaluate_policy`
already returned `allowed=True` for that exact (playbook, incident) pair - see
`domain/models/orm.py::ResponsePlan`'s docstring. This document is about what this file's approval
lifecycle (`ResponsePlan.status`) covers: a human decides whether the plan should be approved.
"Approved" still only ever means that - a second, independent field (`execution_status`, Phase 7)
tracks whether the approved plan has actually been run; approving a plan never executes it. See
`docs/response-executor.md` for everything after approval.

## States

```
                    (policy denies -> no row is ever created)
                                |
create_response_plan  ---->  AWAITING_APPROVAL  ---->  APPROVED
                                    |                       (execution_status starts
                                    |                        NOT_EXECUTED - see
                                    +----------------->  REJECTED   docs/response-executor.md)
                                    |
                                    +----------------->  CANCELLED
```

`DRAFT` and `POLICY_REVIEW` are part of the blueprint's state vocabulary but are never persisted in
Phase 6 - policy evaluation is synchronous (`services/policy_engine/service.py::
create_response_plan` evaluates and either persists straight into `AWAITING_APPROVAL` or persists
nothing at all), so there is no in-between state to observe. `EXPIRED` is a defined, valid `status`
value with no code path that sets it yet - reserved for a future TTL/timeout policy, not exercised
in Phase 6. See DECISIONS.md.

## Who can move a plan, and how

| Endpoint | From | To | Requires |
|---|---|---|---|
| `POST .../response-plan` | (nothing) | `AWAITING_APPROVAL` | policy `allowed=True` |
| `POST .../response-plans/{id}/approve` | `AWAITING_APPROVAL` | `APPROVED` | `actor` (required, no default) |
| `POST .../response-plans/{id}/reject` | `AWAITING_APPROVAL` | `REJECTED` | `actor` + non-empty `reason` |
| `POST .../response-plans/{id}/cancel` | any non-terminal | `CANCELLED` | `actor` |

Every transition other than the listed `From` state raises `PlanStateError` -> HTTP 409
(`services/policy_engine/service.py`). This is what stops a duplicate approval, an approval after
rejection, or an approval of a cancelled plan - not a policy the API asks the caller to follow, but
the only three functions capable of changing `status` refusing to run outside their one legal
starting state. See `tests/integration/test_response_plans_api.py::test_cannot_approve_a_plan_
twice` / `test_cannot_approve_after_rejection` / `test_cannot_approve_a_cancelled_plan`.

`approved_by`/`approved_at`, `rejected_by`/`rejected_at`/`rejection_reason`, and
`cancelled_by`/`cancelled_at` are populated only by their respective transition, straight from the
request's own `actor` field - there is no "system" or default actor for any of these, unlike
`write_audit`'s `actor="system"` default for automated pipeline events. A human approval always
names a human.

## The AI cannot approve anything

`AIIncidentAssessment` (`ai/schemas.py`) has no approval-related field at all - see
`tests/adversarial/test_ai_cannot_approve.py::test_ai_assessment_schema_has_no_approval_related_
field`, which also proves an injected `approval_status` field in raw model output is rejected by
schema validation (`extra="forbid"`), not merely ignored. `services/policy_engine/service.py` -
the only module that can set `status = APPROVED` - has zero import-time contact with `ai.providers`
or any LLM call (`test_policy_engine_service_never_imports_the_llm_provider`). The AI's only
influence on a response plan is supplying a `recommended_playbook_id` that a *human* then chooses
to submit via `POST .../response-plan` with `recommendation_source: "ai"` - a request the API
treats identically to an analyst's own manual choice in every other respect.

## Why approval never executes anything

Approving a plan (`POST .../response-plans/{id}/approve`) only ever sets `status="APPROVED"` - no
code path in `services/policy_engine/service.py` touches `execution_status` as a side effect. This
was deliberate scope discipline in Phase 6 (blueprint §25: "Do NOT implement actual: token
revocation, account disablement, container quarantine, network blocking, workload restart, firewall
changes") and remains a deliberate architectural boundary in Phase 7, now enforced by a second human
action instead of by execution not existing at all: `services/response_executor/` is a separate
package with its own entry point (`POST .../response-plans/{id}/execute`), so "a human approved
this" and "MissionNet's real state changed" stay two observably different events even now that
execution is real. See `docs/response-executor.md` and `docs/verification-and-rollback.md`.
