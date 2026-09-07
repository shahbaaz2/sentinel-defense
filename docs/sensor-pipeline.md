# The real Suricata/Zeek sensor pipeline (Phase 8)

Suricata and Zeek both run for real in this project - not fixtures, not mocks - against safe,
synthetic lab traffic that Sentinel generates itself. `services/sensor_lab/pipeline.py` is the one
module that does this; SCN-NET-001 (`cyber-range/scenarios/SCN-NET-001.yaml`) is the Demo Control
scenario that drives it.

## Why batch pcap analysis, not a live capture

A continuously-running network sniffer needs raw-socket access to a real interface and would
either require root on the host or complex Colima networking, and it would turn Suricata/Zeek into
long-running daemons competing for the same 16 GB this whole Lite profile has to share. Batch
analysis - generate one bounded burst of traffic, capture it to a pcap, then run each tool once
against that pcap in `--runmode=single`/one-shot mode - gets genuinely real Suricata/Zeek output
with none of that: both tools run in ephemeral `docker run --rm` containers that exit in well under
a second once the pcap is written, and hold no memory afterward. This is exactly the flow the phase
scope describes: "safe PCAP or isolated lab traffic → Suricata → Zeek → Sentinel."

## The pipeline, step by step

`services/sensor_lab/pipeline.py::run_network_sensor_lab()`:

1. **Generate lab traffic.** Creates an isolated Docker bridge network (`sentinel-sensor-lab`,
   `172.28.0.0/24`, no route to anything outside this machine) with three ephemeral containers at
   fixed IPs: an `nginx:alpine` server (`.10`), a `dnsmasq` DNS stub (`.11`), and a client
   (`nicolaka/netshoot`, `.3`) running `tcpdump` on its own interface. The client makes exactly two
   HTTP requests (one with a marker header, one with a `cmd=cat%20/etc/passwd`-style query string -
   a deliberately suspicious, synthetic pattern) and two DNS queries (one DGA-shaped test hostname,
   one benign-looking one) against the stub server. All traffic stays on the isolated bridge; no
   external network call is ever made. The client's own capture is copied out to
   `var/sensor-lab/pcap/lab.pcap`, and every container is removed immediately after.
2. **Run Suricata** (`jasonish/suricata:latest`, `--runmode=single`) against that pcap with one
   local custom ruleset (`var/sensor-lab/suricata-rules/local.rules`, two rules matching the
   synthetic markers above - SIDs 1000001/1000002, no external ruleset ever downloaded) - produces
   a real `eve.json` in `var/sensor-lab/suricata-out/`.
3. **Run Zeek** (`zeek/zeek:latest`, `zeek -C -r <pcap> LogAscii::use_json=T`) against the same
   pcap - produces real `conn.log`/`dns.log`/`http.log` in `var/sensor-lab/zeek-out/`.
4. Returns counts (alerts, conn/dns/http records) for the calling scenario step to report.

Every `docker` invocation goes through an explicit timeout (`services/sensor_lab/pipeline.py::_run`)
and the whole pipeline cleans up its containers/network in a `finally` block - a failed run never
leaves lab infrastructure behind, and `SensorLabError` propagates as a normal `ActionError` to Demo
Control's runner, failing the scenario step cleanly.

## From files to Sentinel

`integrations/suricata/adapter.py::SuricataFileAdapter` and `integrations/zeek/adapter.py::
ZeekFileAdapter` read these output files exactly like `integrations/missionnet/adapter.py` polls
MissionNet's HTTP API - same `EventSourceAdapter` contract, same per-(source, stream) cursor
(`IngestionCursor`), same idempotency guarantee, just over a local file instead of a network call.
Suricata's `flow_id:signature_id:timestamp` and Zeek's own `uid` field are both genuinely stable
per-record identifiers, used directly as the idempotency key.

## The two detection rules and the one cross-sensor rule

- **NET-001** (Suricata High-Severity Lab Alert) fires on a single Suricata alert already at
  high/critical severity (Suricata's own priority 1/2, translated by
  `integrations/suricata/mapper.py`).
- **NET-002** (Suspicious DNS Pattern from Zeek) fires when a Zeek DNS query's leftmost label is
  DGA-shaped (>= 10 characters, >= 3 digits) - a deterministic heuristic evaluated at detection
  time against the real `dns_query` field, never a live threat-intel lookup. Zeek evidence is never
  itself a detection until this rule says so.
- **NET-003** (Suricata + Zeek Cross-Sensor Correlation) fires when a Suricata alert and
  independent Zeek evidence (conn/dns/http) share the same originating host (`src_ip`) within 60
  seconds - proof the two sensors' outputs were genuinely correlated by Sentinel, not merely
  ingested side by side. All three rules group by `correlation_key = f"host:{src_ip}"`, reusing the
  same incident-engine grouping mechanism Phase 2's asset/identity correlation already uses - no
  changes to `services/incident_engine/engine.py` were needed.

## Reproducibility

`services/event_ingestor/reset.py::reset()` - the one function every reset path goes through
(`make reset-lab`, `make sentinel-reset`, and every Demo Control scenario's own automatic
`lab_reset` via `POST /api/v1/admin/reset`) - also clears the generated `eve.json`/Zeek log output,
not just the database. A DB-only reset would leave stale sensor output on disk that the next
unrelated scenario's ingestion cycle would re-ingest with a freshly-cleared cursor, fabricating a
spurious network-intrusion incident interleaved with that scenario's own real one - a real bug this
phase found and fixed (see DECISIONS.md). Running SCN-NET-001 twice in a row (each preceded by its
own `lab_reset`) produces two `PASSED` runs with entirely disjoint detection/incident IDs, verified
live.

## Running it

See `RUNBOOK.md`'s "Network sensor pipeline (Suricata + Zeek, Phase 8)" section and
`docs/demo-runbook.md`'s SCN-NET-001 walkthrough.
