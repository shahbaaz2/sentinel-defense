"""Phase 6: deterministic response-planning architecture.

REAL INCIDENT -> deterministic evidence -> optional AI assessment -> approved playbook candidates
-> policy evaluation -> human review -> explicit APPROVE/REJECT -> approved response plan record.

Nothing in this package executes anything. `actions.py` is a schema-only registry of what a future
executor phase could do; `playbooks.py` loads and validates the declarative catalog under
`playbooks/`; `engine.py` is the one deterministic function that decides whether a given playbook
is eligible for a given incident. No AI involvement anywhere in this package.
"""
