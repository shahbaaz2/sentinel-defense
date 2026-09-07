# Policy engine (Phase 6)

`services/policy_engine/engine.py::evaluate_policy` is the one deterministic function that decides
whether a playbook is eligible for an incident. It never calls the AI, never makes a network call,
and always returns the same output for the same input - see `tests/unit/test_policy_engine.py` for
the full positive/negative matrix.

## Input and output

```python
def evaluate_policy(
    playbook: PlaybookDefinition | None,
    pack: EvidencePack,   # the exact same object services/ai_analyst/evidence.py builds
) -> PolicyDecision:
    ...

@dataclass(frozen=True)
class PolicyDecision:
    decision: Literal["ALLOW", "DENY"]
    playbook_id: str
    allowed: bool
    reasons: list[str]            # why each check passed
    blocking_reasons: list[str]   # why each check failed - empty iff allowed
    requires_human_approval: bool
```

Reusing `EvidencePack` (Phase 5's curated, real-data pack) as the policy engine's input means
computing "which playbooks are eligible for this incident" (`compute_eligible_playbook_ids`) costs
no extra database queries beyond what the AI Analyst - or the eligible-playbooks API endpoint - was
already going to run.

## The rules, in order

1. **Playbook exists.** `playbook is None` (an unknown ID) denies immediately with `playbook_id:
   ""` - this is what a hallucinated or mistyped playbook ID hits.
2. **Playbook enabled.** `enabled: false` in the YAML denies regardless of everything else.
3. **Incident not terminal.** `incident_status` must not be `RESOLVED`/`DISMISSED`
   (`domain.incidents.TERMINAL_INCIDENT_STATUSES` - the same constant the incident workflow uses,
   so the two can't drift).
4. **Category allowed.** `incident_category` must be in the playbook's `allowed_incident_categories`.
5. **Severity floor met.** The incident's severity rank (`SEVERITY_ORDER`) must be at least the
   *lowest*-ranked entry in `minimum_incident_severity` - see docs/response-playbooks.md for why
   that's a floor, not an exact-match set.
6. **Detection count met.** `len(pack.detections) >= playbook.minimum_detection_count`.
7. **Asset scope.** If `allowed_asset_types` is non-empty, the incident's asset must exist and its
   `mission_role` must be in that list; an empty list means the playbook is asset-agnostic and this
   check always passes.
8. **Actions registered.** Every `action_id` on the playbook must exist in `ACTION_REGISTRY` - a
   second, independent check on top of the schema-time validation in `playbooks.py`, so a playbook
   object built any other way (`model_construct`, a future loader) still can't sneak an unregistered
   action past policy.

`allowed = not blocking_reasons` - there is no partial-allow, no override, and no code path that
sets `allowed = True` while `blocking_reasons` is non-empty.

## Policy bundle versioning

`POLICY_BUNDLE_VERSION = "PB-001"` (`services/policy_engine/engine.py`) is recorded on every
`ResponsePlan` row at creation time and reported on `GET /api/v1/system/assurance`. It lives in
code, not `.env`/settings, because it describes which deterministic rules are actually loaded in
this process - a configuration file can't accidentally drift from the code that implements it.
Bump it whenever a rule above changes meaning; existing `ResponsePlan` rows keep whatever version
was in effect when they were created, so historical plans stay an honest record of the rules that
actually applied to them.

## What policy evaluation is not

It is not a review of whether the *response is a good idea* - that's what human approval is for
(`docs/human-approval.md`). Policy answers a narrower question: "is this playbook, applied to this
incident, within the boundaries someone already decided were acceptable to even present for
approval." A playbook can be perfectly `ALLOW`ed and still get rejected by a human, and that's the
expected, common case for anything with real mission impact.
