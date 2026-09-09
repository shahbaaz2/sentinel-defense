"""Cloud provider backed by DeepSeek's OpenAI-compatible Chat Completions API.

The provider remains advisory and read-only. In addition to schema validation, this implementation
classifies external-provider failures so operators can distinguish a Sentinel problem from an API
billing/auth/rate-limit/upstream problem. DeepSeek's documented HTTP 402 is treated explicitly as
insufficient balance. The status check uses DeepSeek's balance endpoint and does not perform an
inference request.
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
    start = text.find("{")
    if start == -1:
        raise ValueError("no JSON object found in model output")
    decoder = json.JSONDecoder()
    obj, _ = decoder.raw_decode(text, idx=start)
    if not isinstance(obj, dict):
        raise ValueError("decoded JSON is not an object")
    return obj


def _body_preview(resp: httpx.Response, limit: int = 240) -> str:
    text = resp.text.strip().replace("\n", " ")
    return text if len(text) <= limit else text[:limit] + "…"


def _http_error(resp: httpx.Response) -> StructuredCompletionError:
    status = resp.status_code
    body = _body_preview(resp).lower()

    # DeepSeek documents HTTP 402 as insufficient balance. Match body text too so a compatible
    # gateway that remaps the status still produces the correct operator diagnosis.
    if status == 402 or "insufficient balance" in body or "insufficient_balance" in body:
        return StructuredCompletionError(
            "AI advisory is unavailable because the configured DeepSeek account has insufficient API balance. "
            "Sentinel's deterministic detection, correlation, incident, and response controls remain operational.",
            code="AI_PROVIDER_BILLING",
            retryable=False,
        )
    if status in {401, 403}:
        return StructuredCompletionError(
            "AI provider authentication failed. Check the configured DeepSeek API credential. "
            "Sentinel's deterministic security workflow is unaffected.",
            code="AI_PROVIDER_AUTH",
            retryable=False,
        )
    if status == 429:
        return StructuredCompletionError(
            "AI provider rate limit reached. Retry the advisory analysis later; Sentinel's deterministic security workflow is unaffected.",
            code="AI_PROVIDER_RATE_LIMIT",
            retryable=True,
        )
    if status in {500, 502, 503, 504}:
        return StructuredCompletionError(
            f"AI provider service is temporarily unavailable (HTTP {status}). Retry later; Sentinel's deterministic security workflow is unaffected.",
            code="AI_PROVIDER_UPSTREAM",
            retryable=True,
        )
    if status in {400, 422}:
        return StructuredCompletionError(
            f"AI provider rejected the analysis request (HTTP {status}). This is an AI integration/request issue, not a Sentinel detection failure.",
            code="AI_PROVIDER_REQUEST",
            retryable=False,
        )
    return StructuredCompletionError(
        f"AI provider request failed with HTTP {status}. Sentinel's deterministic security workflow is unaffected.",
        code="AI_PROVIDER_HTTP_ERROR",
        retryable=False,
    )


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
        self._last_error_code: str | None = None
        self._loaded_at: datetime | None = None

    def __repr__(self) -> str:
        return f"DeepSeekProvider(model={self._model_name!r}, api_key=***redacted***)"

    @property
    def last_error_code(self) -> str | None:
        return self._last_error_code

    @property
    def last_error_message(self) -> str | None:
        return self._last_error

    def _set_error(self, error: StructuredCompletionError) -> None:
        self._last_error_code = error.code
        self._last_error = str(error)

    def _clear_error(self) -> None:
        self._last_error_code = None
        self._last_error = None

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
            if resp.status_code >= 400:
                error = _http_error(resp)
                logger.warning(
                    "deepseek_request_failed code=%s status=%s detail=%s",
                    error.code,
                    resp.status_code,
                    _body_preview(resp),
                )
                raise error
            try:
                body = resp.json()
            except ValueError as exc:
                raise StructuredCompletionError(
                    "AI provider returned a non-JSON API response. Sentinel's deterministic security workflow is unaffected.",
                    code="AI_PROVIDER_INVALID_RESPONSE",
                    retryable=True,
                ) from exc
        try:
            return body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise StructuredCompletionError(
                "AI provider returned an unexpected response structure. Sentinel's deterministic security workflow is unaffected.",
                code="AI_PROVIDER_INVALID_RESPONSE",
                retryable=True,
            ) from exc

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
            error = StructuredCompletionError(
                "AI advisory is unavailable because no DeepSeek API key is configured. Sentinel's deterministic security workflow is unaffected.",
                code="AI_PROVIDER_CONFIG",
                retryable=False,
            )
            self._set_error(error)
            raise error

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
                self._clear_error()
                self._loaded_at = self._loaded_at or datetime.now(UTC)
                return result
            except TimeoutError as exc:
                error = StructuredCompletionError(
                    f"AI provider analysis exceeded the configured {timeout_seconds}s timeout. Retry later; Sentinel's deterministic security workflow is unaffected.",
                    code="AI_PROVIDER_TIMEOUT",
                    retryable=True,
                )
                self._set_error(error)
                raise error from exc
            except StructuredCompletionError as exc:
                self._set_error(exc)
                raise
            except httpx.HTTPError as exc:
                error = StructuredCompletionError(
                    "AI provider network request failed. Retry later; Sentinel's deterministic security workflow is unaffected.",
                    code="AI_PROVIDER_NETWORK",
                    retryable=True,
                )
                self._set_error(error)
                logger.warning("deepseek_network_failure detail=%s", exc)
                raise error from exc
            except (ValueError, ValidationError, json.JSONDecodeError, KeyError) as exc:
                last_error = exc
                logger.warning("DeepSeek structured output invalid on attempt %d: %s", attempt, exc)

        error = StructuredCompletionError(
            "AI provider returned output that did not match Sentinel's required assessment schema after one retry. "
            "The invalid output was rejected and was not treated as evidence.",
            code="AI_PROVIDER_INVALID_OUTPUT",
            retryable=True,
        )
        self._set_error(error)
        logger.warning("deepseek_invalid_output final_error=%s", last_error)
        raise error

    async def get_status(self) -> ProviderStatus:
        if not self._api_key:
            self._last_error_code = "AI_PROVIDER_CONFIG"
            self._last_error = "No DeepSeek API key is configured."
            return ProviderStatus.DISABLED
        if self._last_error is not None:
            return ProviderStatus.DEGRADED
        if self._loaded_at is not None:
            return ProviderStatus.READY

        # Fresh provider instance: use DeepSeek's balance endpoint as a no-inference operational
        # check. This is what lets the UI say "provider balance" instead of mislabeling it as a
        # Sentinel/system failure.
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                timeout=8.0,
                transport=self._transport,
                headers={"Authorization": f"Bearer {self._api_key}"},
            ) as client:
                resp = await client.get("/user/balance")
        except httpx.HTTPError as exc:
            error = StructuredCompletionError(
                "AI provider health check could not reach DeepSeek. Sentinel's deterministic security workflow remains operational.",
                code="AI_PROVIDER_NETWORK",
                retryable=True,
            )
            self._set_error(error)
            logger.warning("deepseek_balance_check_network_failure detail=%s", exc)
            return ProviderStatus.DEGRADED

        if resp.status_code >= 400:
            error = _http_error(resp)
            self._set_error(error)
            return ProviderStatus.DEGRADED

        try:
            body = resp.json()
        except ValueError:
            error = StructuredCompletionError(
                "AI provider health check returned a non-JSON response. Sentinel's deterministic security workflow remains operational.",
                code="AI_PROVIDER_STATUS_INVALID_RESPONSE",
                retryable=True,
            )
            self._set_error(error)
            return ProviderStatus.DEGRADED

        if body.get("is_available") is False:
            error = StructuredCompletionError(
                "AI advisory is unavailable because the configured DeepSeek account has insufficient API balance. "
                "Sentinel's deterministic detection, correlation, incident, and response controls remain operational.",
                code="AI_PROVIDER_BILLING",
                retryable=False,
            )
            self._set_error(error)
            return ProviderStatus.DEGRADED

        self._clear_error()
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
