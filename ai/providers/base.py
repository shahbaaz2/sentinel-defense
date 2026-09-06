"""The replaceable LLM provider interface (Phase 5, blueprint AI Analyst §3).

Sentinel's API and the AI Analyst service depend only on `LLMProvider`, `ProviderStatus`, and
`ModelProvenance` - never on a concrete provider module. Adding a second provider later (a
different local runtime, for instance) means writing one new file in this package, not touching
`services/ai_analyst/` or `apps/api/`.
"""

from datetime import datetime
from enum import StrEnum
from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class ProviderStatus(StrEnum):
    """Truthful runtime state, surfaced verbatim on /api/v1/ai/status and System Assurance."""

    READY = "READY"
    LOADING = "LOADING"
    DEGRADED = "DEGRADED"
    DISABLED = "DISABLED"


class ModelProvenance(BaseModel):
    """Recorded with every AI assessment (blueprint §10) so an analyst can always answer "which
    model produced this, from where, and when" - never just a bare "AI said so"."""

    model_name: str
    model_provider: str
    model_revision: str | None = None
    model_quantization: str | None = None
    runtime: str
    local_path: str | None = None
    loaded_at: datetime | None = None


class StructuredCompletionError(Exception):
    """Raised whenever a provider cannot return schema-valid structured output: model unavailable,
    load failure, inference timeout, invalid JSON, or invalid schema after retries. The caller
    (services/ai_analyst/service.py) is required to catch this and persist a failed assessment
    record rather than let it propagate - an AI failure must never break the API process."""


class LLMProvider(Protocol):
    """Every provider must be READ-ONLY with respect to Sentinel/MissionNet state - this Protocol
    has no method that could plausibly write anything. Structured completion is the only
    capability, deliberately narrow (blueprint AI Analyst §11: "do not expose arbitrary user
    prompts")."""

    provider_name: str

    async def structured_completion(
        self,
        *,
        system_prompt: str,
        evidence: dict,
        output_schema: type[T],
        max_tokens: int,
        timeout_seconds: float,
    ) -> T:
        """Send `system_prompt` and the (already-curated, already-untrusted-labelled) `evidence`
        dict to the model and return an instance of `output_schema`. Must raise
        StructuredCompletionError - never return a partially-valid or best-effort object - if the
        model's output cannot be parsed and validated as `output_schema` within `timeout_seconds`,
        even after the provider's own internal retry."""
        ...

    async def get_status(self) -> ProviderStatus: ...

    def get_provenance(self) -> ModelProvenance:
        """Must be safe to call even before the model has loaded (e.g. while READY -> LOADING)."""
        ...
