"""Reads real Zeek JSON log files (`conn.log`/`dns.log`/`http.log`, one line per record, produced
by `zeek -r <pcap> LogAscii::use_json=T` in services/sensor_lab/pipeline.py). Each log is its own
independent stream/cursor - mirrors integrations/missionnet/adapter.py's one-adapter-instance-per-
stream pattern exactly, just reading a local file instead of polling HTTP.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from integrations.zeek import ADAPTER_VERSION
from services.event_ingestor.ports import EventBatch, EventSourceAdapter, RawSourceEvent

DEFAULT_LOG_DIR = "var/sensor-lab/zeek-out"
DEFAULT_LIMIT = 500
_LOG_FILENAMES = {"conn": "conn.log", "dns": "dns.log", "http": "http.log"}


class ZeekFileAdapter(EventSourceAdapter):
    def __init__(
        self, stream: str, log_dir: str = DEFAULT_LOG_DIR, scenario_id: str | None = None
    ) -> None:
        if stream not in _LOG_FILENAMES:
            raise ValueError(f"unsupported Zeek stream: {stream!r}")
        self.stream = stream
        self._log_path = Path(log_dir) / _LOG_FILENAMES[stream]
        self._scenario_id = scenario_id

    def _read_records(self) -> list[dict]:
        if not self._log_path.exists():
            return []
        records = []
        with self._log_path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return records

    async def fetch_events(
        self,
        *,
        since: datetime | None = None,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> EventBatch:
        records = self._read_records()
        events: list[RawSourceEvent] = []
        for record in records:
            occurred_at = datetime.fromtimestamp(record["ts"], tz=UTC)
            if since is not None and occurred_at <= since:
                continue
            if self._scenario_id is not None:
                record = {**record, "_sentinel_scenario_id": self._scenario_id}
            source_event_id = f"{self.stream}:{record['uid']}"
            events.append(
                RawSourceEvent(
                    source="zeek",
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
            self._read_records()
            return True
        except OSError:
            return False


def zeek_conn_adapter(
    log_dir: str = DEFAULT_LOG_DIR, scenario_id: str | None = None
) -> ZeekFileAdapter:
    return ZeekFileAdapter(stream="conn", log_dir=log_dir, scenario_id=scenario_id)


def zeek_dns_adapter(
    log_dir: str = DEFAULT_LOG_DIR, scenario_id: str | None = None
) -> ZeekFileAdapter:
    return ZeekFileAdapter(stream="dns", log_dir=log_dir, scenario_id=scenario_id)


def zeek_http_adapter(
    log_dir: str = DEFAULT_LOG_DIR, scenario_id: str | None = None
) -> ZeekFileAdapter:
    return ZeekFileAdapter(stream="http", log_dir=log_dir, scenario_id=scenario_id)


__all__ = [
    "ADAPTER_VERSION",
    "ZeekFileAdapter",
    "zeek_conn_adapter",
    "zeek_dns_adapter",
    "zeek_http_adapter",
]
