"""Cloud provider backed by DeepSeek's OpenAI-compatible Chat Completions API.

Exists for deployments where no Apple-Silicon host is available to run `MLXProvider` (e.g. a
Render-hosted API process) - the AI Analyst's contract, guardrails, and read-only role are
completely unchanged: this provider still only ever returns schema-validated structured output
built from the same curated evidence pack, still cannot write to any Sentinel/MissionNet table,
and still cannot approve or execute anything (see docs/ai-security-boundaries.md). The only real
difference from `MLXProvider` is where inference happens - a real network call to a third-party
API instead of an in-process model - which is why `external_ai_enabled` must be explicitly set
alongside `SENTINEL_LLM_PROVIDER=deepseek`: enabling this provider is a genuine, honest change to
System Assurance's "internet required" and "inference location" claims, never silently implied.
"""

import asyncio
import json
import logging
import time
from datetime import UTC, datetime
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from ai.providers.base import ModelProvenance, ProviderStatus, StructuredCompletionError

logger = logging.getLogger("sentinel.ai.deepseek_provider")

T = TypeVar("T", bound=BaseModel)

DEFAULT_BASE_URL = "https://api.deepseek.com"


def _extract_json_object(text: str) -> dict:
    """Mirrors MLXProvider's own extraction - DeepSeek's `response_format: json_object` mode makes
    this the common case rather than the fallback, but a model can still wrap output in prose."""
    start = text.find("{")
    if start == -1:
        raise ValueError("no JSON object found in model output")
    decoder = json.JSONDecoder()
    obj, _ = decoder.raw_decode(text, idx=start)
    if not isinstance(obj, dict):
        raise ValueError("decoded JSON is not an object")
    return obj


class DeepSeekProvider:
    provider_name = "deepseek"

    def __init__(
        self,
        *,
        api_key: str,
        model_name: str = "deepseek-chat",
        base_url: str = DEFAULT_BASE_URL,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._model_name = model_name
        self._base_url = base_url.rstrip("/")
        self._transport = transport
        self._last_error: str | None = None
        self._loaded_at: datetime | None = None

    def __repr__(self) -> str:
        # Never let a stray repr()/traceback leak the key - same discipline as SplunkClient.
        return f"DeepSeekProvider(model={self._model_name!r}, api_key=***redacted***)"

    async def _one_completion_attempt(
        self, *, system_prompt: str, user_message: str, max_tokens: int, timeout_seconds: float
    ) -> str:
        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=timeout_seconds,
            transport=self._transport,
            headers={"Authorization": f"Bearer {self._api_key}"},
        ) as client:
            resp = await client.post(
                "/chat/completions",
                json={
                    "model": self._model_name,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    "max_tokens": max_tokens,
                    "temperature": 0.0,
                    "response_format": {"type": "json_object"},
                },
            )
            resp.raise_for_status()
            body = resp.json()
        return body["choices"][0]["message"]["content"]

    async def structured_completion(
        self,
        *,
        system_prompt: str,
        evidence: dict,
        output_schema: type[T],
        max_tokens: int,
        timeout_seconds: float,
    ) -> T:
        if not self._api_key:
            raise StructuredCompletionError("DeepSeek provider has no API key configured")

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
                        system_prompt=system_prompt,
                        user_message=prompt,
                        max_tokens=max_tokens,
                        timeout_seconds=timeout_seconds,
                    ),
                    timeout=timeout_seconds,
                )
                elapsed = time.monotonic() - start
                logger.info(
                    "DeepSeek structured_completion attempt %d took %.2fs", attempt, elapsed
                )
                parsed = _extract_json_object(raw)
                result = output_schema.model_validate(parsed)
                self._last_error = None
                self._loaded_at = self._loaded_at or datetime.now(UTC)
                return result
            except TimeoutError as exc:
                self._last_error = f"timed out after {timeout_seconds}s"
                raise StructuredCompletionError(
                    f"DeepSeek inference exceeded {timeout_seconds}s timeout"
                ) from exc
            except httpx.HTTPStatusError as exc:
                self._last_error = f"HTTP {exc.response.status_code}"
                raise StructuredCompletionError(
                    f"DeepSeek API returned {exc.response.status_code}: {exc.response.text}"
                ) from exc
            except httpx.HTTPError as exc:
                self._last_error = str(exc)
                raise StructuredCompletionError(f"DeepSeek API request failed: {exc}") from exc
            except (ValueError, ValidationError, json.JSONDecodeError, KeyError) as exc:
                last_error = exc
                self._last_error = str(exc)
                logger.warning("DeepSeek structured output invalid on attempt %d: %s", attempt, exc)

        raise StructuredCompletionError(
            f"DeepSeek model did not return schema-valid JSON after retry: {last_error}"
        )

    async def get_status(self) -> ProviderStatus:
        if not self._api_key:
            return ProviderStatus.DISABLED
        if self._last_error is not None:
            return ProviderStatus.DEGRADED
        return ProviderStatus.READY

    def get_provenance(self) -> ModelProvenance:
        return ModelProvenance(
            model_name=self._model_name,
            model_provider="deepseek",
            model_revision=None,
            model_quantization=None,
            runtime="deepseek-api (cloud)",
            local_path=None,
            loaded_at=self._loaded_at,
        )
