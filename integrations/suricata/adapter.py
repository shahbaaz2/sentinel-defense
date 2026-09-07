"""Reads a real Suricata `eve.json` file produced by running Suricata (in Docker, via
services/sensor_lab/pipeline.py) against a safe local pcap - batch analysis, never a live capture
of arbitrary traffic (see docs/sensor-pipeline.md). The file is treated as append-only evidence:
each ingestion cycle re-reads it and skips anything at or before the last-seen timestamp, exactly
like MissionNet's HTTP polling adapter, just over a local file instead of an HTTP endpoint.
"""

import json
from datetime import datetime
from pathlib import Path

from integrations.suricata import ADAPTER_VERSION
from services.event_ingestor.ports import EventBatch, EventSourceAdapter, RawSourceEvent

DEFAULT_EVE_PATH = "var/sensor-lab/suricata-out/eve.json"
DEFAULT_LIMIT = 500


class SuricataFileAdapter(EventSourceAdapter):
    def __init__(self, eve_path: str = DEFAULT_EVE_PATH, scenario_id: str | None = None) -> None:
        self._eve_path = Path(eve_path)
        self._scenario_id = scenario_id
        self.stream = "alerts"

    def _read_alerts(self) -> list[dict]:
        if not self._eve_path.exists():
            return []
        alerts = []
        with self._eve_path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue  # a malformed line is skipped, not fatal to the whole file
                if record.get("event_type") == "alert":
                    alerts.append(record)
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
            occurred_at = datetime.fromisoformat(record["timestamp"])
            if since is not None and occurred_at <= since:
                continue
            if self._scenario_id is not None:
                record = {**record, "_sentinel_scenario_id": self._scenario_id}
            signature_id = record["alert"]["signature_id"]
            source_event_id = f"{record['flow_id']}:{signature_id}:{record['timestamp']}"
            events.append(
                RawSourceEvent(
                    source="suricata",
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
        """A file-based adapter is "healthy" iff its output file exists and parses - there is no
        remote endpoint to ping. An empty/absent file (no sensor run yet) is NOT_CONFIGURED at the
        registry layer, not a health failure - see services/event_ingestor/registry.py."""
        if not self._eve_path.exists():
            return False
        try:
            self._read_alerts()
            return True
        except OSError:
            return False


def suricata_alerts_adapter(
    eve_path: str = DEFAULT_EVE_PATH, scenario_id: str | None = None
) -> SuricataFileAdapter:
    return SuricataFileAdapter(eve_path=eve_path, scenario_id=scenario_id)


__all__ = ["ADAPTER_VERSION", "SuricataFileAdapter", "suricata_alerts_adapter"]
