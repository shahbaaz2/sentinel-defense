"""Zeek integration (Phase 8): ingests real Zeek `conn.log`/`dns.log`/`http.log` records produced
by running Zeek against the same safe, synthetic local pcap Suricata analyzes (see
services/sensor_lab/pipeline.py). Zeek telemetry is evidence, not automatically a detection - see
services/detection_engine/rules.py's NET-002/NET-003 for the one deterministic rule that reads it.
"""

ADAPTER_VERSION = "ZEEK-001"
