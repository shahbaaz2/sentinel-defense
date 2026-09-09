"""Tests for operator-facing DeepSeek provider failure classification."""

import httpx
import pytest

from ai.providers.base import ProviderStatus, StructuredCompletionError
from ai.providers.deepseek_provider import DeepSeekProvider


class _Assessment:
    pass


def _provider(handler) -> DeepSeekProvider:
    return DeepSeekProvider(api_key="test-key", transport=httpx.MockTransport(handler))


async def test_balance_unavailable_reports_billing_degraded():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/user/balance"
        return httpx.Response(200, json={"is_available": False})

    provider = _provider(handler)
    assert await provider.get_status() == ProviderStatus.DEGRADED
    assert provider.last_error_code == "AI_PROVIDER_BILLING"
    assert "insufficient API balance" in (provider.last_error_message or "")


async def test_balance_available_reports_ready():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/user/balance"
        return httpx.Response(200, json={"is_available": True})

    provider = _provider(handler)
    assert await provider.get_status() == ProviderStatus.READY
    assert provider.last_error_code is None


async def test_balance_http_402_is_classified_as_billing():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(402, json={"error": {"message": "Insufficient Balance"}})

    provider = _provider(handler)
    assert await provider.get_status() == ProviderStatus.DEGRADED
    assert provider.last_error_code == "AI_PROVIDER_BILLING"


async def test_chat_402_returns_billing_error_not_generic_provider_error():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/chat/completions":
            return httpx.Response(402, json={"error": {"message": "Insufficient Balance"}})
        return httpx.Response(200, json={"is_available": True})

    provider = _provider(handler)

    from pydantic import BaseModel

    class Assessment(BaseModel):
        classification: str

    with pytest.raises(StructuredCompletionError) as exc_info:
        await provider.structured_completion(
            system_prompt="system",
            evidence={},
            output_schema=Assessment,
            max_tokens=50,
            timeout_seconds=5.0,
        )

    assert exc_info.value.code == "AI_PROVIDER_BILLING"
    assert exc_info.value.retryable is False
    assert provider.last_error_code == "AI_PROVIDER_BILLING"


async def test_rate_limit_is_retryable_provider_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"message": "rate limit"}})

    provider = _provider(handler)

    from pydantic import BaseModel

    class Assessment(BaseModel):
        classification: str

    with pytest.raises(StructuredCompletionError) as exc_info:
        await provider.structured_completion(
            system_prompt="system",
            evidence={},
            output_schema=Assessment,
            max_tokens=50,
            timeout_seconds=5.0,
        )

    assert exc_info.value.code == "AI_PROVIDER_RATE_LIMIT"
    assert exc_info.value.retryable is True
