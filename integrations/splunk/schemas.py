"""Contracts for the Splunk REST shapes this client reads, and for a field-mapping profile
(see integrations/splunk/mappings/*.yaml) - Splunk deployments do not share one universal event
schema, so field names are configurable per source/sourcetype rather than hardcoded."""

from pydantic import BaseModel, Field


class SplunkServerInfo(BaseModel):
    """Subset of the real `/services/server/info` response used only for a health check."""

    version: str | None = None
    server_name: str | None = None


class SplunkFieldMapping(BaseModel):
    """One mapping profile: which raw Splunk result field holds each canonical concept. A field
    left as `None` means that profile's events never carry that concept - the mapper leaves the
    corresponding NormalizedEventRecord column `None` rather than guessing."""

    name: str
    description: str = ""
    time_field: str = "_time"
    host_field: str = "host"
    source_field: str = "source"
    sourcetype_field: str = "sourcetype"
    src_ip_field: str | None = "src"
    dst_ip_field: str | None = "dest"
    user_field: str | None = "user"
    severity_field: str | None = "severity"
    signature_field: str | None = "signature"
    rule_id_field: str | None = "rule_id"
    default_severity: str = "medium"


class SplunkSearchRequest(BaseModel):
    """Bounds Sentinel always applies to a Splunk search - never an unbounded query."""

    query: str
    earliest_time: str = "-1h"
    latest_time: str = "now"
    count: int = Field(default=200, ge=1, le=1000)
