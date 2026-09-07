"""Vendor-neutral adapter registry (Phase 8, blueprint continuation prompt §3). Every source
Sentinel can ingest from - MissionNet and every Phase 8 sensor - is described here by one
`AdapterDescriptor`, built fresh from live `Settings` on every call rather than cached at import
time, so enabling/disabling an adapter in `.env` and restarting the API is always enough to change
what this reports. Nothing here performs I/O except the optional `status()` health check.
"""

from dataclasses import dataclass, field
from typing import Literal, Protocol

from integrations.falco import ADAPTER_VERSION as FALCO_VERSION
from integrations.falco.adapter import falco_alerts_adapter
from integrations.missionnet.adapter import missionnet_audit_adapter, missionnet_telemetry_adapter
from integrations.splunk import ADAPTER_VERSION as SPLUNK_VERSION
from integrations.splunk.adapter import SplunkAdapter
from integrations.splunk.client import SplunkClient
from integrations.splunk.mapper import load_mapping_profile
from integrations.suricata import ADAPTER_VERSION as SURICATA_VERSION
from integrations.suricata.adapter import suricata_alerts_adapter
from integrations.wazuh import ADAPTER_VERSION as WAZUH_VERSION
from integrations.wazuh.adapter import wazuh_alerts_adapter
from integrations.zeek import ADAPTER_VERSION as ZEEK_VERSION
from integrations.zeek.adapter import zeek_conn_adapter, zeek_dns_adapter, zeek_http_adapter
from services.event_ingestor.ports import EventSourceAdapter

AdapterStatus = Literal["ACTIVE", "DEGRADED", "NOT_CONFIGURED"]

MISSIONNET_VERSION = "MN-001"


class AdapterSettings(Protocol):
    """Structural (duck-typed) view of exactly the settings fields this module needs -
    `apps.api.config.Settings` satisfies this without `services/` ever importing `apps/` (the
    same layering rule `services/response_executor` follows for MissionNet's lab secret)."""

    missionnet_base_url: str
    suricata_enabled: bool
    suricata_eve_path: str
    zeek_enabled: bool
    zeek_log_dir: str
    wazuh_enabled: bool
    wazuh_base_url: str
    wazuh_api_token: str
    wazuh_verify_tls: bool
    splunk_enabled: bool
    splunk_base_url: str
    splunk_token: str
    splunk_verify_tls: bool
    splunk_index: str
    splunk_query: str
    falco_enabled: bool


@dataclass(frozen=True)
class AdapterDescriptor:
    adapter_id: str
    name: str
    version: str
    capabilities: list[str]
    """What this adapter can do, e.g. "alert-ingestion", "evidence-ingestion",
    "read-only-search"."""
    configuration_requirements: list[str]
    """Settings/env fields an operator must set for this adapter to become configured."""
    supported_event_categories: list[str]
    enabled: bool
    """Whether the operator has turned this adapter on in settings - independent of `status()`,
    which additionally checks reachability."""
    streams: dict[str, EventSourceAdapter] = field(default_factory=dict)
    """stream name -> adapter instance; empty exactly when `enabled` is False or required config
    (e.g. a Splunk base URL) is missing."""

    async def status(self) -> AdapterStatus:
        if not self.enabled or not self.streams:
            return "NOT_CONFIGURED"
        healths = [await adapter.health() for adapter in self.streams.values()]
        return "ACTIVE" if all(healths) else "DEGRADED"


def missionnet_registry(base_url: str) -> list[AdapterDescriptor]:
    """MissionNet's descriptor, wrapped in the registry list shape `ingest_all` expects - a
    convenience for any caller (tests included) that only needs MissionNet's two streams rather
    than the full multi-source registry `build_adapter_registry` returns."""
    return [
        AdapterDescriptor(
            adapter_id="missionnet",
            name="MissionNet",
            version=MISSIONNET_VERSION,
            capabilities=["alert-ingestion", "evidence-ingestion", "lab-control"],
            configuration_requirements=[],
            supported_event_categories=["identity", "application", "runtime", "control"],
            enabled=True,  # MissionNet is Sentinel's always-on core adapter, not an optional sensor
            streams={
                "audit": missionnet_audit_adapter(base_url),
                "telemetry": missionnet_telemetry_adapter(base_url),
            },
        )
    ]


def _missionnet_descriptor(settings: AdapterSettings) -> AdapterDescriptor:
    return missionnet_registry(settings.missionnet_base_url)[0]


def _suricata_descriptor(
    settings: AdapterSettings, scenario_id: str | None = None
) -> AdapterDescriptor:
    streams: dict[str, EventSourceAdapter] = {}
    if settings.suricata_enabled:
        streams = {
            "alerts": suricata_alerts_adapter(settings.suricata_eve_path, scenario_id=scenario_id)
        }
    return AdapterDescriptor(
        adapter_id="suricata",
        name="Suricata",
        version=SURICATA_VERSION,
        capabilities=["alert-ingestion"],
        configuration_requirements=["SENTINEL_SURICATA_ENABLED", "SENTINEL_SURICATA_EVE_PATH"],
        supported_event_categories=["network"],
        enabled=settings.suricata_enabled,
        streams=streams,
    )


def _zeek_descriptor(
    settings: AdapterSettings, scenario_id: str | None = None
) -> AdapterDescriptor:
    streams: dict[str, EventSourceAdapter] = {}
    if settings.zeek_enabled:
        streams = {
            "conn": zeek_conn_adapter(settings.zeek_log_dir, scenario_id=scenario_id),
            "dns": zeek_dns_adapter(settings.zeek_log_dir, scenario_id=scenario_id),
            "http": zeek_http_adapter(settings.zeek_log_dir, scenario_id=scenario_id),
        }
    return AdapterDescriptor(
        adapter_id="zeek",
        name="Zeek",
        version=ZEEK_VERSION,
        capabilities=["evidence-ingestion"],
        configuration_requirements=["SENTINEL_ZEEK_ENABLED", "SENTINEL_ZEEK_LOG_DIR"],
        supported_event_categories=["network"],
        enabled=settings.zeek_enabled,
        streams=streams,
    )


def _wazuh_descriptor(
    settings: AdapterSettings, scenario_id: str | None = None
) -> AdapterDescriptor:
    streams: dict[str, EventSourceAdapter] = {}
    if settings.wazuh_enabled and settings.wazuh_base_url:
        streams = {
            "alerts": wazuh_alerts_adapter(
                settings.wazuh_base_url,
                settings.wazuh_api_token,
                verify_tls=settings.wazuh_verify_tls,
                scenario_id=scenario_id,
            )
        }
    return AdapterDescriptor(
        adapter_id="wazuh",
        name="Wazuh",
        version=WAZUH_VERSION,
        capabilities=["alert-ingestion"],
        configuration_requirements=[
            "SENTINEL_WAZUH_ENABLED",
            "SENTINEL_WAZUH_BASE_URL",
            "SENTINEL_WAZUH_API_TOKEN",
        ],
        supported_event_categories=["endpoint"],
        enabled=settings.wazuh_enabled,
        streams=streams,
    )


def _splunk_descriptor(
    settings: AdapterSettings, scenario_id: str | None = None
) -> AdapterDescriptor:
    streams: dict[str, EventSourceAdapter] = {}
    if settings.splunk_enabled and settings.splunk_base_url and settings.splunk_query:
        client = SplunkClient(
            settings.splunk_base_url, settings.splunk_token, verify_tls=settings.splunk_verify_tls
        )
        mapping = load_mapping_profile("generic_security")
        streams = {
            "search_results": SplunkAdapter(
                client,
                settings.splunk_query,
                mapping,
                index=settings.splunk_index or None,
                scenario_id=scenario_id,
            )
        }
    return AdapterDescriptor(
        adapter_id="splunk",
        name="Splunk",
        version=SPLUNK_VERSION,
        capabilities=["read-only-search"],
        configuration_requirements=[
            "SENTINEL_SPLUNK_ENABLED",
            "SENTINEL_SPLUNK_BASE_URL",
            "SENTINEL_SPLUNK_TOKEN",
            "SENTINEL_SPLUNK_QUERY",
        ],
        supported_event_categories=["application", "network", "identity", "endpoint"],
        enabled=settings.splunk_enabled,
        streams=streams,
    )


def _falco_descriptor(
    settings: AdapterSettings, scenario_id: str | None = None
) -> AdapterDescriptor:
    streams: dict[str, EventSourceAdapter] = {}
    if settings.falco_enabled:
        streams = {"alerts": falco_alerts_adapter(scenario_id=scenario_id)}
    return AdapterDescriptor(
        adapter_id="falco",
        name="Falco",
        version=FALCO_VERSION,
        capabilities=["alert-ingestion"],
        configuration_requirements=["SENTINEL_FALCO_ENABLED"],
        supported_event_categories=["endpoint"],
        enabled=settings.falco_enabled,
        streams=streams,
    )


def build_adapter_registry(
    settings: AdapterSettings, scenario_id: str | None = None
) -> list[AdapterDescriptor]:
    """`scenario_id`, when given, is stamped onto every event every enabled sensor adapter fetches
    (via each adapter's own `_sentinel_scenario_id` payload key) - used by SCN-NET-001 so its
    sensor-derived events carry the same provenance every MissionNet-driven scenario's events do."""
    return [
        _missionnet_descriptor(settings),
        _suricata_descriptor(settings, scenario_id),
        _zeek_descriptor(settings, scenario_id),
        _wazuh_descriptor(settings, scenario_id),
        _splunk_descriptor(settings, scenario_id),
        _falco_descriptor(settings, scenario_id),
    ]
