"""Vendor-neutral event source boundary.

Sentinel's domain layer must never know whether telemetry came from MissionNet, Wazuh, Splunk, or a
PCAP replay - it only knows `EventSourceAdapter`. `integrations/missionnet/adapter.py` is the first
implementation; `integrations/wazuh`, `integrations/splunk`, etc. (Phase 8+) implement the same
Protocol without any change to the ingestion service, detection engine, or incident engine.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol


@dataclass(frozen=True)
class RawSourceEvent:
    """One untouched record from a source system, before normalization."""

    source: str
    source_event_id: str
    """Stable ID from the source system - the idempotency key for ingestion."""
    stream: str
    """Which sub-stream this came from, e.g. 'audit' or 'telemetry' - used for per-stream
    cursors."""
    occurred_at: datetime
    payload: dict[str, Any]


@dataclass(frozen=True)
class EventBatch:
    events: list[RawSourceEvent]
    next_cursor: datetime | None
    """Watermark to pass as `since` on the next poll. None means nothing new was returned."""


class EventSourceAdapter(Protocol):
    async def fetch_events(
        self,
        *,
        since: datetime | None = None,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> EventBatch: ...

    async def health(self) -> bool:
        """True iff the source is currently reachable/usable. Never raises - a source that can't
        be reached is UNHEALTHY, not an exception the caller has to catch (Phase 8: System
        Assurance and the Data Sources page both call this directly)."""
        ...
