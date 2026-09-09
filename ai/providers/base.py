"""Replaceable LLM provider interface for Sentinel's advisory AI Analyst."""

from datetime import datetime
from enum import StrEnum
from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class ProviderStatus(StrEnum):
    """Truthful runtime state surfaced through the AI status endpoint and System Assurance."""

    READY = "READY"
    LOADING = "LOADING"
    DEGRADED = "DEGRADED"
    DISABLED = "DISABLED"


class ModelProvenance(BaseModel):
    """Recorded with every AI assessment so an analyst can identify model provenance."""

    model_name: str
    model_provider: str
    model_revision: str | None = None
    model_quantization: str | None = None
    runtime: str
    local_path: str | None = None
    loaded_at: datetime | None = None


class StructuredCompletionError(Exception):
    """A provider failure classified for logging and safe operator-facing diagnostics.

    ``message`` must be safe to persist in an assessment record. ``code`` lets the API/UI separate
    provider billing, authentication, rate limiting, upstream availability, timeout, network, and
    model-output failures without pretending those failures belong to Sentinel's deterministic
    detection pipeline.
    """

    def __init__(
        self,
        message: str,
        *,
        code: str = "AI_PROVIDER_ERROR",
        retryable: bool = False,
    ) -> None:
        self.code = code
        self.retryable = retryable
        super().__init__(message)


class LLMProvider(Protocol):
    """Read-only LLM provider contract. No method can alter Sentinel/MissionNet state."""

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
        """Return schema-valid output or raise ``StructuredCompletionError``."""
        ...

    async def get_status(self) -> ProviderStatus: ...

    def get_provenance(self) -> ModelProvenance:
        """Return model/runtime provenance without exposing secrets."""
        ...
