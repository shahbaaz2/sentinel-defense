"""Splunk REST client tests against `httpx.MockTransport` speaking Splunk's real endpoint shapes
(`/services/server/info`, `/services/search/jobs/export`) - no real Splunk instance required (see
integrations/splunk/__init__.py)."""

import httpx
import pytest

from integrations.splunk.client import SplunkAuthError, SplunkClient, SplunkTimeoutError
from integrations.splunk.schemas import SplunkSearchRequest


def _client(handler, **kwargs) -> SplunkClient:
    transport = httpx.MockTransport(handler)
    return SplunkClient(
        base_url="https://splunk.example.internal:8089", token="tok", transport=transport, **kwargs
    )


async def test_health_parses_real_server_info_shape():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/services/server/info"
        assert request.headers["authorization"] == "Bearer tok"
        return httpx.Response(
            200,
            json={"entry": [{"content": {"version": "9.2.1", "serverName": "splunk-idx-01"}}]},
        )

    info = await _client(handler).health()
    assert info is not None
    assert info.version == "9.2.1"
    assert info.server_name == "splunk-idx-01"


async def test_health_returns_none_on_unauthorized():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="Unauthorized")

    assert await _client(handler).health() is None


async def test_health_returns_none_on_network_error_not_a_crash():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    assert await _client(handler).health() is None


async def test_search_parses_ndjson_export_results():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/services/search/jobs/export"
        body = (
            '{"preview": false, "result": {"_time": "1700000000", "host": "web-01"}}\n'
            '{"preview": false, "result": {"_time": "1700000001", "host": "web-02"}}\n'
        )
        return httpx.Response(200, text=body)

    results = await _client(handler).search(SplunkSearchRequest(query="index=security"))
    assert len(results) == 2
    assert results[0]["host"] == "web-01"


async def test_search_prefixes_a_bare_query_with_search_keyword():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read().decode()
        return httpx.Response(200, text="")

    await _client(handler).search(SplunkSearchRequest(query="index=security src_ip=*"))
    assert "search=search+index" in captured["body"] or "search=search%20index" in captured["body"]


async def test_search_raises_auth_error_on_401():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="Unauthorized")

    with pytest.raises(SplunkAuthError):
        await _client(handler).search(SplunkSearchRequest(query="index=security"))


async def test_search_raises_timeout_error_on_timeout():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out")

    with pytest.raises(SplunkTimeoutError):
        await _client(handler).search(SplunkSearchRequest(query="index=security"))


async def test_search_result_count_is_bounded_by_request_count():
    def handler(request: httpx.Request) -> httpx.Response:
        body = "".join(
            f'{{"result": {{"_time": "{1700000000 + i}"}}}}\n' for i in range(10)
        )
        return httpx.Response(200, text=body)

    results = await _client(handler).search(SplunkSearchRequest(query="index=security", count=3))
    assert len(results) == 3


def test_repr_never_leaks_the_token():
    client = SplunkClient(base_url="https://splunk.example.internal", token="super-secret-token")
    assert "super-secret-token" not in repr(client)
