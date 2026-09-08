"""DeepSeekProvider tests against `httpx.MockTransport` - no real DeepSeek API key or network
access required. Proves the same structured-completion contract every provider must honor
(schema-valid-or-raise, never a partial/best-effort object) without spending a real API call.
"""

import json

import httpx
import pytest
from pydantic import BaseModel

from ai.providers.base import ProviderStatus, StructuredCompletionError
from ai.providers.deepseek_provider import DeepSeekProvider


class _Assessment(BaseModel):
    classification: str
    confidence: float


def _provider(handler, **kwargs) -> DeepSeekProvider:
    transport = httpx.MockTransport(handler)
    return DeepSeekProvider(api_key="test-key", transport=transport, **kwargs)


def _chat_response(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


async def test_structured_completion_parses_valid_json_response():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-key"
        body = json.loads(request.read())
        assert body["response_format"] == {"type": "json_object"}
        return _chat_response(json.dumps({"classification": "malicious", "confidence": 0.9}))

    provider = _provider(handler)
    result = await provider.structured_completion(
        system_prompt="sys", evidence={"x": 1}, output_schema=_Assessment,
        max_tokens=100, timeout_seconds=5.0,
    )
    assert result.classification == "malicious"
    assert await provider.get_status() == ProviderStatus.READY


async def test_structured_completion_strips_prose_around_json():
    def handler(request: httpx.Request) -> httpx.Response:
        content = 'Here is the result:\n{"classification": "benign", "confidence": 0.1}\nDone.'
        return _chat_response(content)

    provider = _provider(handler)
    result = await provider.structured_completion(
        system_prompt="sys", evidence={}, output_schema=_Assessment,
        max_tokens=100, timeout_seconds=5.0,
    )
    assert result.classification == "benign"


async def test_structured_completion_retries_once_on_invalid_json_then_raises():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return _chat_response("not json at all")

    provider = _provider(handler)
    with pytest.raises(StructuredCompletionError):
        await provider.structured_completion(
            system_prompt="sys", evidence={}, output_schema=_Assessment,
            max_tokens=100, timeout_seconds=5.0,
        )
    assert calls["count"] == 2  # one retry, matching MLXProvider's own retry discipline


async def test_structured_completion_raises_on_http_error_never_returns_partial_object():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid api key"})

    provider = _provider(handler)
    with pytest.raises(StructuredCompletionError):
        await provider.structured_completion(
            system_prompt="sys", evidence={}, output_schema=_Assessment,
            max_tokens=100, timeout_seconds=5.0,
        )
    assert await provider.get_status() == ProviderStatus.DEGRADED


async def test_structured_completion_raises_on_timeout():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out")

    provider = _provider(handler)
    with pytest.raises(StructuredCompletionError, match="timed out"):
        await provider.structured_completion(
            system_prompt="sys", evidence={}, output_schema=_Assessment,
            max_tokens=100, timeout_seconds=5.0,
        )


async def test_missing_api_key_raises_immediately_without_a_network_call():
    called = {"yes": False}

    def handler(request: httpx.Request) -> httpx.Response:
        called["yes"] = True
        return _chat_response("{}")

    transport = httpx.MockTransport(handler)
    provider = DeepSeekProvider(api_key="", transport=transport)
    with pytest.raises(StructuredCompletionError, match="no API key"):
        await provider.structured_completion(
            system_prompt="sys", evidence={}, output_schema=_Assessment,
            max_tokens=100, timeout_seconds=5.0,
        )
    assert called["yes"] is False


async def test_status_disabled_without_api_key():
    provider = DeepSeekProvider(api_key="")
    assert await provider.get_status() == ProviderStatus.DISABLED


def test_repr_never_leaks_the_api_key():
    provider = DeepSeekProvider(api_key="super-secret-deepseek-key")
    assert "super-secret-deepseek-key" not in repr(provider)


def test_provenance_reports_no_local_path():
    provider = DeepSeekProvider(api_key="test-key", model_name="deepseek-chat")
    provenance = provider.get_provenance()
    assert provenance.model_provider == "deepseek"
    assert provenance.local_path is None
    assert provenance.runtime == "deepseek-api (cloud)"
