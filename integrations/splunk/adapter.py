"""EventSourceAdapter over a bounded, read-only Splunk search (see client.py). `since` becomes the
search's `earliest_time` bound - Sentinel never issues an unbounded Splunk query."""

import functools
import hashlib
import json
from datetime import datetime

from integrations.splunk.client import SplunkClient
from integrations.splunk.mapper import normalize_splunk_event, parse_splunk_time
from integrations.splunk.schemas import SplunkFieldMapping, SplunkSearchRequest
from services.event_ingestor.ports import EventBatch, EventSourceAdapter, RawSourceEvent

DEFAULT_LOOKBACK = "-24h"
DEFAULT_LIMIT = 200


def _stable_result_id(result: dict) -> str:
    """Splunk's own `_cd` (bucket:offset) is a stable per-event ID within an index; fall back to a
    content hash for a mock/fixture result that omits it."""
    cd = result.get("_cd")
    if cd:
        return str(cd)
    canonical = json.dumps(result, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


class SplunkAdapter(EventSourceAdapter):
    def __init__(
        self,
        client: SplunkClient,
        query: str,
        mapping: SplunkFieldMapping,
        *,
        index: str | None = None,
        scenario_id: str | None = None,
    ) -> None:
        self.stream = "search_results"
        self._client = client
        self._query = query
        self._mapping = mapping
        self._index = index
        self._scenario_id = scenario_id
        # Splunk is the one source whose normalizer needs a per-instance mapping profile, unlike
        # every other source's fixed-signature `normalize_x_event(raw)` - the ingestor looks for
        # this attribute before falling back to its global source->mapper table (see
        # services/event_ingestor/service.py).
        self.mapper = functools.partial(normalize_splunk_event, mapping=mapping)

    async def fetch_events(
        self,
        *,
        since: datetime | None = None,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> EventBatch:
        earliest = since.strftime("%m/%d/%Y:%H:%M:%S") if since is not None else DEFAULT_LOOKBACK
        query = self._query
        if self._index:
            query = f"index={self._index} {query}"
        request = SplunkSearchRequest(
            query=query, earliest_time=earliest, latest_time="now", count=limit or DEFAULT_LIMIT
        )
        results = await self._client.search(request)

        events: list[RawSourceEvent] = []
        for result in results:
            if self._mapping.time_field not in result:
                continue
            occurred_at = parse_splunk_time(result[self._mapping.time_field])
            if since is not None and occurred_at <= since:
                continue
            payload = dict(result)
            if self._scenario_id is not None:
                payload["_sentinel_scenario_id"] = self._scenario_id
            events.append(
                RawSourceEvent(
                    source="splunk",
                    source_event_id=_stable_result_id(result),
                    stream=self.stream,
                    occurred_at=occurred_at,
                    payload=payload,
                )
            )
        if not events:
            return EventBatch(events=[], next_cursor=None)
        return EventBatch(events=events, next_cursor=max(e.occurred_at for e in events))

    async def health(self) -> bool:
        info = await self._client.health()
        return info is not None
