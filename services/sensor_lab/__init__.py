"""Orchestrates SCN-NET-001's safe, synthetic network-sensor lab (Phase 8): generates one bounded
burst of lab-only HTTP/DNS traffic between ephemeral Docker containers on an isolated bridge
network, captures it to a local pcap, then runs real Suricata and Zeek (also in ephemeral
containers) against that pcap in batch mode - never a live capture of arbitrary traffic, and never
a long-running sensor daemon. See docs/sensor-pipeline.md.
"""
