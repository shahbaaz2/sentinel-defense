# Human approval workflow (Phase 6)

A `ResponsePlan` row only ever exists because `services/policy_engine/engine.py::evaluate_policy`
already returned `allowed=True` for that exact (playbook, incident) pair - see
`domain/models/orm.py::ResponsePlan`'s docstring. Everything in this document is about what happens
*after* that: a human decides whether the plan should actually happen, and - in Phase 6 - "happen"
still only means "be marked APPROVED," never "run."

## States

```
                    (policy denies -> no row is ever created)
                                |
create_response_plan  ---->  AWAITING_APPROVAL  ---->  APPROVED
                                    |                       (execution_status stays
                                    |                        EXECUTION_NOT_ENABLED
                                    +----------------->  REJECTED   forever in Phase 6)
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

## Why execution stays disabled

`ResponsePlan.execution_status` is hardcoded `"EXECUTION_NOT_ENABLED"` - there is no executor
module, no code path that flips it, and no API field that accepts a different value. This is
deliberate scope discipline for Phase 6 (blueprint §25: "Do NOT implement actual: token revocation,
account disablement, container quarantine, network blocking, workload restart, firewall changes"):
proving Sentinel can safely *recommend and authorize* a bounded response plan is a genuinely
separate milestone from proving it can *execute* one, and conflating them would mean shipping
containment automation without having independently verified the recommendation/policy/approval
chain first. Real execution - actually calling MissionNet's `/lab/*` endpoints for a playbook's
actions, with its own verification and rollback - is explicitly the next phase's work.
