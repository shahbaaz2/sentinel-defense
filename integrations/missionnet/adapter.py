"""Polls MissionNet's own public API for new audit/telemetry records.

Two streams (`audit`, `telemetry`) are exposed as two adapter instances rather than one adapter
fetching both, so each gets its own cursor row in `ingestion_cursors` and a failure in one stream
never blocks the other. Both streams already support `?since=<ISO8601>&limit=<n>` ascending-order
polling (added to MissionNet's public API specifically for this - see apps/missionnet/routes.py).
"""

from datetime import datetime

import httpx

from services.event_ingestor.ports import EventBatch, EventSourceAdapter, RawSourceEvent

DEFAULT_BASE_URL = "http://127.0.0.1:8090"
POLL_LIMIT = 200


class MissionNetAdapter(EventSourceAdapter):
    def __init__(
        self,
        stream: str,
        path: str,
        id_field: str,
        time_field: str,
        base_url: str = DEFAULT_BASE_URL,
    ) -> None:
        self.stream = stream
        self._path = path
        self._id_field = id_field
        self._time_field = time_field
        self._base_url = base_url.rstrip("/")

    async def fetch_events(
        self,
        *,
        since: datetime | None = None,
        cursor: str | None = None,
    ) -> EventBatch:
        params: dict[str, str | int] = {"limit": POLL_LIMIT}
        if since is not None:
            params["since"] = since.isoformat()

        async with httpx.AsyncClient(base_url=self._base_url, timeout=10.0) as client:
            resp = await client.get(self._path, params=params)
            resp.raise_for_status()
            records: list[dict] = resp.json()

        if not records:
            return EventBatch(events=[], next_cursor=None)

        events = [
            RawSourceEvent(
                source="missionnet",
                source_event_id=str(record[self._id_field]),
                stream=self.stream,
                occurred_at=datetime.fromisoformat(record[self._time_field]),
                payload=record,
            )
            for record in records
        ]
        next_cursor = max(e.occurred_at for e in events)
        return EventBatch(events=events, next_cursor=next_cursor)


def missionnet_audit_adapter(base_url: str = DEFAULT_BASE_URL) -> MissionNetAdapter:
    return MissionNetAdapter(
        stream="audit",
        path="/audit",
        id_field="audit_id",
        time_field="timestamp",
        base_url=base_url,
    )


def missionnet_telemetry_adapter(base_url: str = DEFAULT_BASE_URL) -> MissionNetAdapter:
    return MissionNetAdapter(
        stream="telemetry",
        path="/telemetry",
        id_field="sample_id",
        time_field="generated_at",
        base_url=base_url,
    )
