from datetime import UTC, datetime

import httpx

from integrations.splunk.adapter import SplunkAdapter
from integrations.splunk.client import SplunkClient
from integrations.splunk.mapper import load_mapping_profile


def _adapter(handler, **kwargs) -> SplunkAdapter:
    transport = httpx.MockTransport(handler)
    client = SplunkClient(
        base_url="https://splunk.example.internal", token="tok", transport=transport
    )
    mapping = load_mapping_profile("generic_security")
    return SplunkAdapter(client, "index=security", mapping, **kwargs)


async def test_fetch_events_maps_search_results_into_raw_events():
    def handler(request: httpx.Request) -> httpx.Response:
        body = '{"result": {"_time": "1700000000", "host": "web-01", "_cd": "3:100"}}\n'
        return httpx.Response(200, text=body)

    adapter = _adapter(handler)
    batch = await adapter.fetch_events()
    assert len(batch.events) == 1
    assert batch.events[0].source_event_id == "3:100"
    assert batch.events[0].payload["host"] == "web-01"


async def test_fetch_events_excludes_results_at_or_before_since():
    def handler(request: httpx.Request) -> httpx.Response:
        body = '{"result": {"_time": "1700000000", "host": "web-01", "_cd": "3:100"}}\n'
        return httpx.Response(200, text=body)

    adapter = _adapter(handler)
    since = datetime.fromtimestamp(1700000000, tz=UTC)
    batch = await adapter.fetch_events(since=since)
    assert batch.events == []


async def test_scenario_id_is_stamped_into_every_fetched_event():
    def handler(request: httpx.Request) -> httpx.Response:
        body = '{"result": {"_time": "1700000000", "host": "web-01", "_cd": "3:100"}}\n'
        return httpx.Response(200, text=body)

    adapter = _adapter(handler, scenario_id="SCN-TEST")
    batch = await adapter.fetch_events()
    assert batch.events[0].payload["_sentinel_scenario_id"] == "SCN-TEST"


async def test_health_reflects_the_underlying_client():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/services/server/info":
            return httpx.Response(200, json={"entry": [{"content": {}}]})
        return httpx.Response(200, text="")

    adapter = _adapter(handler)
    assert await adapter.health() is True
