"""File-based adapter for Falco's JSON alert output (one alert object per line, `json_output:
true`). Not run live in this lab (falco_enabled defaults False) - see
integrations/falco/__init__.py.
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path

from integrations.falco import ADAPTER_VERSION
from integrations.falco.mapper import parse_falco_timestamp
from services.event_ingestor.ports import EventBatch, EventSourceAdapter, RawSourceEvent

DEFAULT_LOG_PATH = "var/sensor-lab/falco-out/falco_events.json"
DEFAULT_LIMIT = 500


class FalcoFileAdapter(EventSourceAdapter):
    def __init__(self, log_path: str = DEFAULT_LOG_PATH, scenario_id: str | None = None) -> None:
        self._log_path = Path(log_path)
        self._scenario_id = scenario_id
        self.stream = "alerts"

    def _read_alerts(self) -> list[dict]:
        if not self._log_path.exists():
            return []
        alerts = []
        with self._log_path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    alerts.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return alerts

    async def fetch_events(
        self,
        *,
        since: datetime | None = None,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> EventBatch:
        alerts = self._read_alerts()
        events: list[RawSourceEvent] = []
        for record in alerts:
            occurred_at = parse_falco_timestamp(record["time"])
            if since is not None and occurred_at <= since:
                continue
            if self._scenario_id is not None:
                record = {**record, "_sentinel_scenario_id": self._scenario_id}
            canonical = json.dumps(record, sort_keys=True, default=str)
            source_event_id = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
            events.append(
                RawSourceEvent(
                    source="falco",
                    source_event_id=source_event_id,
                    stream=self.stream,
                    occurred_at=occurred_at,
                    payload=record,
                )
            )
        events.sort(key=lambda e: e.occurred_at)
        events = events[: limit or DEFAULT_LIMIT]
        if not events:
            return EventBatch(events=[], next_cursor=None)
        return EventBatch(events=events, next_cursor=max(e.occurred_at for e in events))

    async def health(self) -> bool:
        if not self._log_path.exists():
            return False
        try:
            self._read_alerts()
            return True
        except OSError:
            return False


def falco_alerts_adapter(
    log_path: str = DEFAULT_LOG_PATH, scenario_id: str | None = None
) -> FalcoFileAdapter:
    return FalcoFileAdapter(log_path=log_path, scenario_id=scenario_id)


__all__ = ["ADAPTER_VERSION", "FalcoFileAdapter", "falco_alerts_adapter"]
