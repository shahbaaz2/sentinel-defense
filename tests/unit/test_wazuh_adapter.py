"""Wazuh adapter tests against `httpx.MockTransport` returning Wazuh's real REST envelope shape -
no live Wazuh manager required (see integrations/wazuh/__init__.py for why)."""

from datetime import UTC, datetime

import httpx
import pytest

from integrations.wazuh.adapter import WazuhAdapter

ALERT = {
    "id": "1690000000.1",
    "timestamp": "2024-01-01T00:00:00.000+0000",
    "rule": {"id": "5720", "level": 10, "description": "Multiple auth failures", "groups": []},
    "agent": {"id": "001", "name": "web-01"},
    "data": {"srcip": "203.0.113.5"},
}


def _adapter(handler, **kwargs) -> WazuhAdapter:
    transport = httpx.MockTransport(handler)
    return WazuhAdapter(
        base_url="https://wazuh.example.internal", api_token="tok", transport=transport, **kwargs
    )


async def test_fetch_events_parses_the_real_wazuh_envelope():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer tok"
        return httpx.Response(200, json={"data": {"affected_items": [ALERT]}})

    adapter = _adapter(handler)
    batch = await adapter.fetch_events()
    assert len(batch.events) == 1
    assert batch.events[0].source_event_id == "1690000000.1"
    assert batch.next_cursor is not None


async def test_fetch_events_respects_since_cursor():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {"affected_items": [ALERT]}})

    adapter = _adapter(handler)
    since = datetime(2025, 1, 1, tzinfo=UTC)  # after the fixture's 2024 timestamp
    batch = await adapter.fetch_events(since=since)
    assert batch.events == []


async def test_unauthorized_response_makes_health_false():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid token"})

    adapter = _adapter(handler)
    assert await adapter.health() is False


async def test_healthy_response_makes_health_true():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {"affected_items": []}})

    adapter = _adapter(handler)
    assert await adapter.health() is True


async def test_network_error_makes_health_false_not_a_crash():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    adapter = _adapter(handler)
    assert await adapter.health() is False


async def test_unauthorized_response_on_fetch_raises_for_the_ingestor_to_isolate():
    """`fetch_events` raises on a non-2xx response (`raise_for_status`), exactly like
    MissionNetAdapter - it is `services/event_ingestor/service.py::ingest_all`'s per-adapter
    try/except that turns this into an isolated failure, not the adapter swallowing it."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid token"})

    adapter = _adapter(handler)
    with pytest.raises(httpx.HTTPStatusError):
        await adapter.fetch_events()
