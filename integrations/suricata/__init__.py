"""Suricata integration (Phase 8): ingests real Suricata EVE JSON alert records produced by running
Suricata against a safe, synthetic local pcap (see services/sensor_lab/pipeline.py) - never a live
capture of arbitrary network traffic. See docs/sensor-pipeline.md.
"""

ADAPTER_VERSION = "SUR-001"
