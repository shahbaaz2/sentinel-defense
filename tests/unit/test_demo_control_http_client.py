"""Unit coverage for Demo Control's centralized upstream response contract."""

import httpx
import pytest

from apps.demo_control.http_client import UpstreamResponseError, request_json


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://service.test")


async def test_retries_transient_gateway_then_returns_json():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] < 3:
            return httpx.Response(502, text="Bad Gateway")
        return httpx.Response(200, json={"status": "ok"})

    async with _client(handler) as client:
        body = await request_json(
            client,
            "GET",
            "/health",
            component="MissionNet",
            retry_safe=True,
            expected_type=dict,
        )

    assert body == {"status": "ok"}
    assert calls["count"] == 3


async def test_non_json_success_is_classified_instead_of_leaking_decoder_error():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(200, text="temporarily unavailable", headers={"content-type": "text/plain"})

    async with _client(handler) as client:
        with pytest.raises(UpstreamResponseError) as exc_info:
            await request_json(
                client,
                "GET",
                "/state",
                component="MissionNet",
                retry_safe=True,
                expected_type=dict,
            )

    assert exc_info.value.code == "UPSTREAM_INVALID_RESPONSE"
    assert "Expecting value" not in str(exc_info.value)
    assert calls["count"] == 3


async def test_empty_json_required_response_is_classified():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"")

    async with _client(handler) as client:
        with pytest.raises(UpstreamResponseError) as exc_info:
            await request_json(
                client,
                "GET",
                "/health",
                component="MissionNet",
                expected_type=dict,
            )

    assert exc_info.value.code == "UPSTREAM_INVALID_RESPONSE"
    assert "empty response" in str(exc_info.value)


async def test_empty_success_can_be_accepted_when_body_is_not_evidence():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(204, content=b"")

    async with _client(handler) as client:
        result = await request_json(
            client,
            "POST",
            "/api/v1/ingest/run",
            component="Sentinel API",
            retry_safe=True,
            allow_non_json_success=True,
        )

    assert result["accepted"] is True
    assert result["http_status"] == 204
    assert result["response_format"] == "empty"


async def test_application_4xx_is_never_retried():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(400, json={"detail": "bad request"})

    async with _client(handler) as client:
        with pytest.raises(UpstreamResponseError) as exc_info:
            await request_json(
                client,
                "GET",
                "/state",
                component="MissionNet",
                retry_safe=True,
            )

    assert exc_info.value.code == "UPSTREAM_HTTP_ERROR"
    assert calls["count"] == 1


async def test_unexpected_json_shape_is_classified():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    async with _client(handler) as client:
        with pytest.raises(UpstreamResponseError) as exc_info:
            await request_json(
                client,
                "GET",
                "/health",
                component="MissionNet",
                expected_type=dict,
            )

    assert exc_info.value.code == "UPSTREAM_INVALID_RESPONSE"
    assert "unexpected type" in str(exc_info.value)
