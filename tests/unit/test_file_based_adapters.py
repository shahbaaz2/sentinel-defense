"""Cursor/idempotency behavior of the file-based sensor adapters (Suricata/Zeek/Falco) - no Docker,
no live sensor, just real file I/O against a temp directory."""

import json

from integrations.falco.adapter import FalcoFileAdapter
from integrations.suricata.adapter import SuricataFileAdapter
from integrations.zeek.adapter import ZeekFileAdapter


def _write_jsonl(path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")


async def test_suricata_adapter_returns_nothing_when_file_absent(tmp_path):
    adapter = SuricataFileAdapter(eve_path=str(tmp_path / "missing.json"))
    batch = await adapter.fetch_events()
    assert batch.events == []
    assert batch.next_cursor is None


async def test_suricata_adapter_reads_only_alert_events_not_flow_or_stats(tmp_path):
    eve_path = tmp_path / "eve.json"
    _write_jsonl(
        eve_path,
        [
            {"event_type": "flow", "timestamp": "2026-01-01T00:00:00.000000+0000"},
            {
                "event_type": "alert",
                "timestamp": "2026-01-01T00:00:01.000000+0000",
                "flow_id": 1,
                "src_ip": "10.0.0.1",
                "dest_ip": "10.0.0.2",
                "proto": "TCP",
                "alert": {
                    "action": "allowed", "gid": 1, "signature_id": 1, "rev": 1,
                    "signature": "test", "category": "test", "severity": 2,
                },
            },
        ],
    )
    adapter = SuricataFileAdapter(eve_path=str(eve_path))
    batch = await adapter.fetch_events()
    assert len(batch.events) == 1
    assert batch.events[0].payload["event_type"] == "alert"


async def test_suricata_adapter_cursor_excludes_already_seen_events(tmp_path):
    eve_path = tmp_path / "eve.json"
    _write_jsonl(
        eve_path,
        [
            {
                "event_type": "alert", "timestamp": "2026-01-01T00:00:01.000000+0000",
                "flow_id": 1, "src_ip": "10.0.0.1", "dest_ip": "10.0.0.2", "proto": "TCP",
                "alert": {"action": "a", "gid": 1, "signature_id": 1, "rev": 1, "signature": "s",
                          "category": "c", "severity": 1},
            },
            {
                "event_type": "alert", "timestamp": "2026-01-01T00:00:02.000000+0000",
                "flow_id": 2, "src_ip": "10.0.0.1", "dest_ip": "10.0.0.2", "proto": "TCP",
                "alert": {"action": "a", "gid": 1, "signature_id": 2, "rev": 1, "signature": "s",
                          "category": "c", "severity": 1},
            },
        ],
    )
    adapter = SuricataFileAdapter(eve_path=str(eve_path))
    first = await adapter.fetch_events()
    assert len(first.events) == 2

    second = await adapter.fetch_events(since=first.next_cursor)
    assert second.events == []
    assert second.next_cursor is None


async def test_suricata_adapter_skips_malformed_lines_without_crashing(tmp_path):
    eve_path = tmp_path / "eve.json"
    eve_path.write_text("not valid json\n")
    adapter = SuricataFileAdapter(eve_path=str(eve_path))
    batch = await adapter.fetch_events()
    assert batch.events == []


async def test_zeek_adapter_reads_the_right_log_file_per_stream(tmp_path):
    conn_record = {
        "ts": 1700000000.0, "uid": "C1", "id.orig_h": "10.0.0.1", "id.orig_p": 1,
        "id.resp_h": "10.0.0.2", "id.resp_p": 2, "proto": "tcp",
    }
    dns_record = {
        "ts": 1700000000.0, "uid": "C2", "id.orig_h": "10.0.0.1", "id.orig_p": 1,
        "id.resp_h": "10.0.0.2", "id.resp_p": 53, "query": "example.test",
    }
    _write_jsonl(tmp_path / "conn.log", [conn_record])
    _write_jsonl(tmp_path / "dns.log", [dns_record])

    conn_adapter = ZeekFileAdapter(stream="conn", log_dir=str(tmp_path))
    dns_adapter = ZeekFileAdapter(stream="dns", log_dir=str(tmp_path))

    conn_batch = await conn_adapter.fetch_events()
    dns_batch = await dns_adapter.fetch_events()

    assert len(conn_batch.events) == 1
    assert conn_batch.events[0].payload["uid"] == "C1"
    assert len(dns_batch.events) == 1
    assert dns_batch.events[0].payload["uid"] == "C2"


async def test_zeek_health_false_before_any_run_true_after(tmp_path):
    adapter = ZeekFileAdapter(stream="conn", log_dir=str(tmp_path))
    assert await adapter.health() is False
    _write_jsonl(tmp_path / "conn.log", [{"ts": 1700000000.0, "uid": "C1",
                 "id.orig_h": "10.0.0.1", "id.orig_p": 1, "id.resp_h": "10.0.0.2",
                 "id.resp_p": 2, "proto": "tcp"}])
    assert await adapter.health() is True


async def test_falco_adapter_deduplicates_by_content_hash(tmp_path):
    log_path = tmp_path / "falco.json"
    record = {
        "output": "test", "priority": "Notice", "rule": "test rule",
        "time": "2026-01-01T00:00:00.000000000Z", "output_fields": {},
    }
    _write_jsonl(log_path, [record])
    adapter = FalcoFileAdapter(log_path=str(log_path))
    first = await adapter.fetch_events()
    assert len(first.events) == 1
    first_id = first.events[0].source_event_id

    second = await adapter.fetch_events()
    assert second.events[0].source_event_id == first_id  # same content -> same stable ID
