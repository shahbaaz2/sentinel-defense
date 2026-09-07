"""Phase 7: the deterministic response executor.

REAL INCIDENT -> ... -> human APPROVE -> human EXECUTE -> this package -> real MissionNet state
change -> verification -> rollback where applicable -> audit.

This package has no import, at any depth, of `ai/` or `services/ai_analyst/` - see
`tests/adversarial/test_executor_ai_isolation.py`. It consumes only an already-approved, already
persisted `ResponsePlan` row; nothing here can be reached from AI output. There is no
`execute_shell`, `execute_sql`, `ssh`, `docker_exec`, or arbitrary-URL capability anywhere in this
package - every handler in `registry.py`/`rollback.py` calls one specific, named MissionNet
lab-control endpoint.
"""

EXECUTOR_VERSION = "EX-001"
"""Bump whenever execution semantics change - recorded on every ResponsePlan that gets executed, so
a historical execution record stays an honest description of the executor that actually ran it."""
