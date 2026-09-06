"""A deterministic, in-process provider used by the test suite and CI. Never loads a model, never
touches the network - lets AI Analyst service/API/persistence logic be tested quickly and without
requiring MLX or a 2GB+ model download. `SENTINEL_LLM_PROVIDER=mock` is also the safe default for
a fresh checkout that hasn't set up a local model yet (see config.py).
"""

import asyncio
from datetime import UTC, datetime
from typing import TypeVar

from pydantic import BaseModel

from ai.providers.base import ModelProvenance, ProviderStatus, StructuredCompletionError

T = TypeVar("T", bound=BaseModel)


class MockProvider:
    provider_name = "mock"

    def __init__(
        self,
        *,
        fixed_output: BaseModel | None = None,
        raise_error: Exception | None = None,
        latency_ms: float = 5.0,
    ) -> None:
        """Exactly one of `fixed_output` / `raise_error` should be set per test - there is no
        default assessment, so a misconfigured test fails loudly rather than silently passing
        against a fabricated response the test author didn't write."""
        self._fixed_output = fixed_output
        self._raise_error = raise_error
        self._latency_ms = latency_ms
        self._loaded_at = datetime.now(UTC)

    async def structured_completion(
        self,
        *,
        system_prompt: str,
        evidence: dict,
        output_schema: type[T],
        max_tokens: int,
        timeout_seconds: float,
    ) -> T:
        await asyncio.sleep(self._latency_ms / 1000)
        if self._raise_error is not None:
            raise self._raise_error
        if self._fixed_output is None:
            raise StructuredCompletionError("MockProvider has no fixed_output or raise_error set")
        if not isinstance(self._fixed_output, output_schema):
            raise StructuredCompletionError(
                f"MockProvider fixed_output is {type(self._fixed_output)}, not {output_schema}"
            )
        return self._fixed_output

    async def get_status(self) -> ProviderStatus:
        return ProviderStatus.READY

    def get_provenance(self) -> ModelProvenance:
        return ModelProvenance(
            model_name="mock-deterministic",
            model_provider="mock",
            model_revision=None,
            model_quantization=None,
            runtime="in-process (no model loaded)",
            local_path=None,
            loaded_at=self._loaded_at,
        )
