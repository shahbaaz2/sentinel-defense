"""Non-persisted, in-flight data shapes used only within the executor's own call graph. Persisted
shapes live in `domain/models/orm.py::ActionResult`/`ResponsePlan` - these dataclasses exist so
`registry.py`/`rollback.py`/`verifier.py`/`targets.py` don't need to import the ORM or talk to a
database directly; they receive a `ResolvedTarget` and an `ExecutionContext` and return an outcome.
"""

from dataclasses import dataclass, field
from typing import Literal

TargetType = Literal["asset", "identity_user", "service_token", "incident"]


@dataclass(frozen=True)
class ExecutionContext:
    """Everything a handler needs about *how* to reach MissionNet - never *what* to do, which
    always comes from the closed action registry, and never *which* incident/plan, which the
    executor's own loop already resolved before calling a handler."""

    missionnet_base_url: str
    missionnet_lab_secret: str
    scenario_id: str | None
    executor_version: str


@dataclass(frozen=True)
class ResolvedTarget:
    target_type: TargetType
    target_id: str


@dataclass(frozen=True)
class ActionOutcome:
    success: bool
    result_metadata: dict = field(default_factory=dict)
    """Structured, non-secret facts only - e.g. {"new_token_id": "tok-x-rotated"}. Never a
    password, token value, or other secret (blueprint §7)."""
    error_code: str | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class VerificationOutcome:
    verified: bool
    detail: dict = field(default_factory=dict)


class ExecutionBlockedError(Exception):
    """Raised by pre-execution revalidation (blueprint §9) - execution never starts, so
    `execution_status` never leaves NOT_EXECUTED; the reason is persisted to
    `ResponsePlan.execution_block_reason` instead."""


class ExecutionInProgressError(Exception):
    """Raised when `execute` is called on a plan whose execution_status is already
    EXECUTING/VERIFYING/ROLLING_BACK - a duplicate/concurrent execute request, not a state that
    should be silently retried or silently ignored."""


class PlanNotFoundError(Exception):
    pass
