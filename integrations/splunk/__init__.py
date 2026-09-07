"""Splunk integration (Phase 8) - READ-ONLY.

Sentinel is not replacing Splunk: this integration lets Sentinel consume evidence from an
organization's existing Splunk environment and add vendor-neutral normalization, evidence-grounded
local AI, human-approved response, verification, and provenance on top of it - see
docs/splunk-integration.md.

No real Splunk instance exists in this Lite-profile lab, so this integration is built and tested
against a local contract/mock HTTP server that speaks Splunk's real REST shapes (`/services/server/
info`, `/services/search/jobs/export`) - see tests/integration/test_splunk_adapter.py. It is
honestly reported NOT_CONFIGURED unless `SENTINEL_SPLUNK_ENABLED=true` and a real base URL/token
are set. If a real instance is ever configured, live validation follows docs/splunk-integration.md
without any code change - the client and mapper are already shaped for a genuine Splunk server.
"""

ADAPTER_VERSION = "SPLUNK-001"
