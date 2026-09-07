"""Polls a Wazuh deployment's alert-listing endpoint over HTTP - shaped after Wazuh's real REST API
response envelope (`{"data": {"affected_items": [...]}}`), Bearer-token authenticated, TLS
verification on by default. No live Wazuh manager is required to exist for this module to be
correct: tests exercise it against `httpx.MockTransport` returning this exact envelope with real,
representative alert fixtures (integrations/wazuh/__init__.py explains why nothing live runs here).
"""

from datetime import datetime

import httpx

from integrations.wazuh.mapper import parse_wazuh_timestamp
from services.event_ingestor.ports import EventBatch, EventSourceAdapter, RawSourceEvent

DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_LIMIT = 200


class WazuhAdapter(EventSourceAdapter):
    def __init__(
        self,
        base_url: str,
        api_token: str,
        *,
        verify_tls: bool = True,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        transport: httpx.AsyncBaseTransport | None = None,
        scenario_id: str | None = None,
    ) -> None:
        self.stream = "alerts"
        self._base_url = base_url.rstrip("/")
        self._api_token = api_token
        self._verify_tls = verify_tls
        self._timeout_seconds = timeout_seconds
        self._transport = transport
        self._scenario_id = scenario_id

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout_seconds,
            verify=self._verify_tls,
            transport=self._transport,
            headers={"Authorization": f"Bearer {self._api_token}"},
        )

    async def fetch_events(
        self,
        *,
        since: datetime | None = None,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> EventBatch:
        params: dict[str, str | int] = {"limit": limit or DEFAULT_LIMIT}
        if since is not None:
            params["since"] = since.isoformat()

        async with self._client() as client:
            resp = await client.get("/alerts", params=params)
            resp.raise_for_status()
            body = resp.json()

        alerts = body.get("data", {}).get("affected_items", [])
        events: list[RawSourceEvent] = []
        for alert in alerts:
            occurred_at = parse_wazuh_timestamp(alert["timestamp"])
            if since is not None and occurred_at <= since:
                continue
            if self._scenario_id is not None:
                alert = {**alert, "_sentinel_scenario_id": self._scenario_id}
            events.append(
                RawSourceEvent(
                    source="wazuh",
                    source_event_id=str(alert["id"]),
                    stream=self.stream,
                    occurred_at=occurred_at,
                    payload=alert,
                )
            )
        if not events:
            return EventBatch(events=[], next_cursor=None)
        return EventBatch(events=events, next_cursor=max(e.occurred_at for e in events))

    async def health(self) -> bool:
        try:
            async with self._client() as client:
                resp = await client.get("/alerts", params={"limit": 1})
                return resp.status_code == 200
        except httpx.HTTPError:
            return False


def wazuh_alerts_adapter(
    base_url: str,
    api_token: str,
    *,
    verify_tls: bool = True,
    transport: httpx.AsyncBaseTransport | None = None,
    scenario_id: str | None = None,
) -> WazuhAdapter:
    return WazuhAdapter(
        base_url=base_url,
        api_token=api_token,
        verify_tls=verify_tls,
        transport=transport,
        scenario_id=scenario_id,
    )
