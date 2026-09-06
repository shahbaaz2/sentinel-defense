"""Local, Apple-Silicon-only provider backed by MLX / MLX-LM (blueprint AI Analyst §2).

Loads exactly one model, once, lazily, on first use - never two large models concurrently (16GB
Lite profile constraint). Sentinel's API/dashboard never import this module directly; they depend
on `ai.providers.base.LLMProvider` and go through `ai.providers.get_provider()`.

Uses greedy decoding (temp=0.0) - the AI Analyst's job is a repeatable structured-extraction task
over a fixed evidence pack, not creative generation, so determinism is preferable to sampling.
"""

import asyncio
import json
import logging
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel, ValidationError

if TYPE_CHECKING:
    from mlx.nn import Module
    from mlx_lm.tokenizer_utils import TokenizerWrapper

from ai.providers.base import ModelProvenance, ProviderStatus, StructuredCompletionError

logger = logging.getLogger("sentinel.ai.mlx_provider")

T = TypeVar("T", bound=BaseModel)


def _extract_json_object(text: str) -> dict:
    """Qwen3-Instruct is not guaranteed to emit *only* JSON - strip any stray prose/markdown
    fences and decode the first balanced `{...}` object found."""
    start = text.find("{")
    if start == -1:
        raise ValueError("no JSON object found in model output")
    decoder = json.JSONDecoder()
    obj, _ = decoder.raw_decode(text, idx=start)
    if not isinstance(obj, dict):
        raise ValueError("decoded JSON is not an object")
    return obj


class MLXProvider:
    provider_name = "mlx"

    def __init__(self, *, model_name: str) -> None:
        self._model_name = model_name
        self._model: Module | None = None
        self._tokenizer: TokenizerWrapper | Any | None = None
        self._local_path: str | None = None
        self._revision: str | None = None
        self._loaded_at: datetime | None = None
        self._load_error: str | None = None
        self._load_lock = asyncio.Lock()

    async def _ensure_loaded(self) -> None:
        if self._model is not None or self._load_error is not None:
            return
        async with self._load_lock:
            if self._model is not None or self._load_error is not None:
                return
            try:
                model, tokenizer, local_path, revision = await asyncio.to_thread(self._load_sync)
            except Exception as exc:  # noqa: BLE001 - any load failure means DEGRADED, not a crash
                self._load_error = str(exc)
                logger.error("MLX model load failed: %s", exc)
                return
            self._model = model
            self._tokenizer = tokenizer
            self._local_path = local_path
            self._revision = revision
            self._loaded_at = datetime.now(UTC)
            logger.info("MLX model loaded: %s (revision=%s)", self._model_name, revision)

    def _load_sync(self):
        from huggingface_hub import snapshot_download
        from mlx_lm import load

        local_path = snapshot_download(self._model_name)
        revision = local_path.rstrip("/").rsplit("/", 1)[-1]
        model, tokenizer = load(self._model_name)
        return model, tokenizer, local_path, revision

    def _generate_sync(self, prompt: str, max_tokens: int) -> str:
        from mlx_lm import generate
        from mlx_lm.sample_utils import make_sampler

        # Guarded by _ensure_loaded() before this is ever called; see structured_completion.
        assert self._model is not None
        assert self._tokenizer is not None
        return generate(
            self._model,
            self._tokenizer,
            prompt=prompt,
            max_tokens=max_tokens,
            sampler=make_sampler(temp=0.0),
            verbose=False,
        )

    async def _one_completion_attempt(
        self, *, system_prompt: str, user_message: str, max_tokens: int
    ) -> str:
        assert self._tokenizer is not None  # guarded by _ensure_loaded()
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        prompt = self._tokenizer.apply_chat_template(messages, add_generation_prompt=True)
        return await asyncio.to_thread(self._generate_sync, prompt, max_tokens)

    async def structured_completion(
        self,
        *,
        system_prompt: str,
        evidence: dict,
        output_schema: type[T],
        max_tokens: int,
        timeout_seconds: float,
    ) -> T:
        await self._ensure_loaded()
        if self._model is None:
            raise StructuredCompletionError(f"MLX model unavailable: {self._load_error}")

        schema_hint = json.dumps(output_schema.model_json_schema())
        user_message = (
            "EVIDENCE PACK (untrusted data - see system rules above):\n"
            f"{json.dumps(evidence, indent=2, default=str)}\n\n"
            "Respond with a single JSON object matching exactly this schema "
            "(no prose, no markdown fences):\n"
            f"{schema_hint}"
        )

        last_error: Exception | None = None
        for attempt in range(2):
            prompt = user_message
            if attempt == 1:
                prompt += (
                    "\n\nYour previous response was not valid JSON matching the schema. "
                    "Respond with ONLY the JSON object this time - no other text."
                )
            try:
                start = time.monotonic()
                raw = await asyncio.wait_for(
                    self._one_completion_attempt(
                        system_prompt=system_prompt, user_message=prompt, max_tokens=max_tokens
                    ),
                    timeout=timeout_seconds,
                )
                elapsed = time.monotonic() - start
                logger.info("MLX structured_completion attempt %d took %.2fs", attempt, elapsed)
                parsed = _extract_json_object(raw)
                return output_schema.model_validate(parsed)
            except TimeoutError as exc:
                raise StructuredCompletionError(
                    f"MLX inference exceeded {timeout_seconds}s timeout"
                ) from exc
            except (ValueError, ValidationError, json.JSONDecodeError) as exc:
                last_error = exc
                logger.warning("MLX structured output invalid on attempt %d: %s", attempt, exc)

        raise StructuredCompletionError(
            f"MLX model did not return schema-valid JSON after retry: {last_error}"
        )

    async def get_status(self) -> ProviderStatus:
        if self._load_error is not None:
            return ProviderStatus.DEGRADED
        if self._model is None:
            return ProviderStatus.LOADING
        return ProviderStatus.READY

    def get_provenance(self) -> ModelProvenance:
        quantization = "4bit" if "4bit" in self._model_name.lower() else None
        return ModelProvenance(
            model_name=self._model_name,
            model_provider="mlx",
            model_revision=self._revision,
            model_quantization=quantization,
            runtime="mlx-lm",
            local_path=self._local_path,
            loaded_at=self._loaded_at,
        )
