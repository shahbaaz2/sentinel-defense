from dataclasses import dataclass

from services.event_ingestor.registry import build_adapter_registry


@dataclass
class _FakeSettings:
    missionnet_base_url: str = "http://127.0.0.1:8090"
    suricata_enabled: bool = False
    suricata_eve_path: str = "var/sensor-lab/suricata-out/eve.json"
    zeek_enabled: bool = False
    zeek_log_dir: str = "var/sensor-lab/zeek-out"
    wazuh_enabled: bool = False
    wazuh_base_url: str = ""
    wazuh_api_token: str = ""
    wazuh_verify_tls: bool = True
    splunk_enabled: bool = False
    splunk_base_url: str = ""
    splunk_token: str = ""
    splunk_verify_tls: bool = True
    splunk_index: str = ""
    splunk_query: str = ""
    falco_enabled: bool = False


def test_default_registry_has_only_missionnet_enabled():
    registry = build_adapter_registry(_FakeSettings())
    by_id = {d.adapter_id: d for d in registry}
    assert set(by_id) == {"missionnet", "suricata", "zeek", "wazuh", "splunk", "falco"}
    assert by_id["missionnet"].enabled is True
    assert by_id["missionnet"].streams  # MissionNet is always-on
    for adapter_id in ("suricata", "zeek", "wazuh", "splunk", "falco"):
        assert by_id[adapter_id].enabled is False
        assert by_id[adapter_id].streams == {}


def test_enabling_suricata_without_touching_others_only_adds_its_stream():
    registry = build_adapter_registry(_FakeSettings(suricata_enabled=True))
    by_id = {d.adapter_id: d for d in registry}
    assert by_id["suricata"].enabled is True
    assert set(by_id["suricata"].streams) == {"alerts"}
    assert by_id["zeek"].enabled is False


def test_zeek_registers_all_three_log_streams_independently():
    registry = build_adapter_registry(_FakeSettings(zeek_enabled=True))
    by_id = {d.adapter_id: d for d in registry}
    assert set(by_id["zeek"].streams) == {"conn", "dns", "http"}


def test_wazuh_requires_both_enabled_and_a_base_url():
    enabled_no_url = build_adapter_registry(_FakeSettings(wazuh_enabled=True, wazuh_base_url=""))
    assert {d.adapter_id: d for d in enabled_no_url}["wazuh"].streams == {}

    enabled_with_url = build_adapter_registry(
        _FakeSettings(wazuh_enabled=True, wazuh_base_url="https://wazuh.example.internal")
    )
    assert {d.adapter_id: d for d in enabled_with_url}["wazuh"].streams


def test_splunk_requires_enabled_base_url_and_query():
    missing_query = build_adapter_registry(
        _FakeSettings(
            splunk_enabled=True, splunk_base_url="https://splunk.example.internal", splunk_query=""
        )
    )
    assert {d.adapter_id: d for d in missing_query}["splunk"].streams == {}

    fully_configured = build_adapter_registry(
        _FakeSettings(
            splunk_enabled=True,
            splunk_base_url="https://splunk.example.internal",
            splunk_query="search index=security",
        )
    )
    assert {d.adapter_id: d for d in fully_configured}["splunk"].streams


async def test_status_is_not_configured_when_disabled():
    registry = build_adapter_registry(_FakeSettings())
    by_id = {d.adapter_id: d for d in registry}
    assert await by_id["suricata"].status() == "NOT_CONFIGURED"
    assert await by_id["wazuh"].status() == "NOT_CONFIGURED"


async def test_status_is_degraded_when_enabled_but_output_file_missing(tmp_path):
    missing_path = str(tmp_path / "does-not-exist" / "eve.json")
    registry = build_adapter_registry(
        _FakeSettings(suricata_enabled=True, suricata_eve_path=missing_path)
    )
    by_id = {d.adapter_id: d for d in registry}
    assert await by_id["suricata"].status() == "DEGRADED"


async def test_status_is_active_once_output_file_exists(tmp_path):
    eve_path = tmp_path / "eve.json"
    eve_path.write_text('{"event_type": "flow", "timestamp": "2026-01-01T00:00:00+0000"}\n')
    registry = build_adapter_registry(
        _FakeSettings(suricata_enabled=True, suricata_eve_path=str(eve_path))
    )
    by_id = {d.adapter_id: d for d in registry}
    assert await by_id["suricata"].status() == "ACTIVE"


def test_configuration_requirements_name_the_actual_env_vars():
    registry = build_adapter_registry(_FakeSettings())
    by_id = {d.adapter_id: d for d in registry}
    assert "SENTINEL_SPLUNK_TOKEN" in by_id["splunk"].configuration_requirements
    assert "SENTINEL_WAZUH_API_TOKEN" in by_id["wazuh"].configuration_requirements
    assert by_id["missionnet"].configuration_requirements == []
