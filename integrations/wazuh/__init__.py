"""Wazuh integration (Phase 8). No live Wazuh manager/indexer runs in this Lite-profile lab - a
full Wazuh stack is too heavy to run alongside MissionNet/Suricata/Zeek on a 16 GB machine without
destabilizing it (see DECISIONS.md). This adapter is built and tested against real, representative
Wazuh alert JSON (the well-known `rule`/`agent`/`decoder`/`data` shape Wazuh actually emits) via
contract/mock validation - see tests/unit/test_wazuh_mapper.py and
tests/integration/test_wazuh_adapter.py. It is honestly reported NOT_CONFIGURED unless a real
`SENTINEL_WAZUH_BASE_URL` is set.
"""

ADAPTER_VERSION = "WAZUH-001"
