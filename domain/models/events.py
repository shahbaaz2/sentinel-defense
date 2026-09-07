"""Normalized event contract (blueprint §8).

Every source-specific adapter maps into this one schema before anything else in Sentinel sees it.
The LLM never parses raw vendor formats or natural-language event fields as instructions - only
this strict, size-bounded, validated shape.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

EventSource = Literal["missionnet", "suricata", "zeek", "wazuh", "falco", "osquery", "synthetic"]
EventCategory = Literal[
    "network", "endpoint", "identity", "application", "runtime", "vulnerability", "control"
]
Severity = Literal["info", "low", "medium", "high", "critical"]

# Bounds exist to prevent prompt-injection payload bloat and storage abuse (blueprint §8.1) - they
# are not arbitrary. Raw events are always preserved in full (with a hash) regardless of these
# limits.
MAX_SHORT_STR = 256
MAX_SUMMARY_LEN = 2000
MAX_LIST_ITEMS = 50


class NormalizedEvent(BaseModel):
    model_config = {"frozen": True}

    event_id: str = Field(max_length=128, description="Immutable, unique identifier.")
    timestamp: datetime = Field(description="Source-reported event time.")
    received_at: datetime = Field(description="Sentinel ingest time.")

    source: EventSource
    event_category: EventCategory
    severity: Severity

    asset_id: str | None = Field(default=None, max_length=MAX_SHORT_STR)
    user_id: str | None = Field(default=None, max_length=MAX_SHORT_STR)
    rule_id: str | None = Field(default=None, max_length=MAX_SHORT_STR)

    src_ip: str | None = Field(default=None, max_length=64)
    dst_ip: str | None = Field(default=None, max_length=64)
    src_port: int | None = Field(default=None, ge=1, le=65535)
    dst_port: int | None = Field(default=None, ge=1, le=65535)
    process_name: str | None = Field(default=None, max_length=MAX_SHORT_STR)
    dns_query: str | None = Field(default=None, max_length=MAX_SHORT_STR)

    technique_ids: list[str] = Field(default_factory=list, max_length=MAX_LIST_ITEMS)
    tags: list[str] = Field(default_factory=list, max_length=MAX_LIST_ITEMS)

    summary: str = Field(max_length=MAX_SUMMARY_LEN)
    raw_event_ref: str = Field(max_length=MAX_SHORT_STR, description="Pointer to raw_events row.")

    scenario_id: str | None = Field(default=None, max_length=MAX_SHORT_STR)
