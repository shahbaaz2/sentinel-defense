"""Phase 8 end-to-end proof: real Suricata/Zeek-shaped output files (written as fixtures, no
Docker needed for this suite - services/sensor_lab/pipeline.py is what runs the real containers,
proven separately/live) ingested through Sentinel's real adapter/normalizer/detection/incident
pipeline and exposed through the real API. Also covers multi-adapter error isolation, raw
provenance, and the /api/v1/integrations status endpoint.

Requires `make dev-up` (Postgres) and a live MissionNet server (`make missionnet` on :8090) -
matches tests/integration/test_sentinel_ingestion_pipeline.py's requirements exactly.
"""

import json
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.main import app as sentinel_app
from apps.missionnet.seed import reset_and_seed as reset_missionnet
from domain.db import Base, SessionLocal, engine
from domain.models import orm  # noqa: F401 - registers tables on Base.metadata
from integrations.suricata.adapter import suricata_alerts_adapter
from integrations.zeek.adapter import zeek_conn_adapter, zeek_dns_adapter, zeek_http_adapter
from services.detection_engine.engine import run_detection_engine
from services.event_ingestor.registry import AdapterDescriptor
from services.event_ingestor.reset import reset as reset_sentinel
from services.event_ingestor.service import ingest_all
from services.incident_engine.engine import run_incident_correlation

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
async def _reset_everything():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await reset_missionnet()
    await reset_sentinel()
    yield
    await reset_missionnet()
    await reset_sentinel()


def _write_suricata_fixture(tmp_path, src_ip="172.28.0.3") -> str:
    tmp_path.mkdir(parents=True, exist_ok=True)
    eve_path = tmp_path / "eve.json"
    now = datetime.now(UTC)
    alert = {
        "event_type": "alert",
        "timestamp": now.strftime("%Y-%m-%dT%H:%M:%S.%f+0000"),
        "flow_id": 1,
        "src_ip": src_ip,
        "src_port": 40000,
        "dest_ip": "172.28.0.10",
        "dest_port": 80,
        "proto": "TCP",
        "alert": {
            "action": "allowed", "gid": 1, "signature_id": 1000001, "rev": 1,
            "signature": "SENTINEL LAB test alert", "category": "Web Application Attack",
            "severity": 1,
        },
    }
    eve_path.write_text(json.dumps(alert) + "\n")
    return str(eve_path)


def _write_zeek_fixtures(tmp_path, src_ip="172.28.0.3") -> str:
    tmp_path.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).timestamp()
    conn_record = {
        "ts": ts, "uid": "Cconn1", "id.orig_h": src_ip, "id.orig_p": 40000,
        "id.resp_h": "172.28.0.10", "id.resp_p": 80, "proto": "tcp", "conn_state": "SF",
    }
    dns_record = {
        "ts": ts, "uid": "Cdns1", "id.orig_h": src_ip, "id.orig_p": 50000,
        "id.resp_h": "172.28.0.11", "id.resp_p": 53,
        "query": "a8f3k2m9x7q1z5.sentinel-lab-dga-test.example", "qtype_name": "A",
        "rcode_name": "NOERROR",
    }
    (tmp_path / "conn.log").write_text(json.dumps(conn_record) + "\n")
    (tmp_path / "dns.log").write_text(json.dumps(dns_record) + "\n")
    (tmp_path / "http.log").write_text("")
    return str(tmp_path)


def _sensor_registry(tmp_path, src_ip="172.28.0.3") -> list[AdapterDescriptor]:
    eve_path = _write_suricata_fixture(tmp_path / "suricata", src_ip)
    zeek_dir = _write_zeek_fixtures(tmp_path / "zeek", src_ip)
    return [
        AdapterDescriptor(
            adapter_id="suricata", name="Suricata", version="test", capabilities=[],
            configuration_requirements=[], supported_event_categories=["network"], enabled=True,
            streams={"alerts": suricata_alerts_adapter(eve_path)},
        ),
        AdapterDescriptor(
            adapter_id="zeek", name="Zeek", version="test", capabilities=[],
            configuration_requirements=[], supported_event_categories=["network"], enabled=True,
            streams={
                "conn": zeek_conn_adapter(zeek_dir),
                "dns": zeek_dns_adapter(zeek_dir),
                "http": zeek_http_adapter(zeek_dir),
            },
        ),
    ]


async def _run_pipeline(registry) -> dict:
    async with SessionLocal() as session:
        ingestion = await ingest_all(session, registry)
    async with SessionLocal() as session:
        detections = await run_detection_engine(session)
    async with SessionLocal() as session:
        incidents = await run_incident_correlation(session)
    return {"ingestion": ingestion, "detections": detections, "incidents": incidents}


async def test_suricata_and_zeek_fixtures_produce_a_cross_sensor_incident(tmp_path):
    registry = _sensor_registry(tmp_path)
    result = await _run_pipeline(registry)

    assert result["detections"].detections_created >= 3  # NET-001, NET-002, NET-003
    assert result["incidents"].incidents_created == 1

    transport = ASGITransport(app=sentinel_app)
    async with AsyncClient(transport=transport, base_url="http://test") as api:
        incidents = (await api.get("/api/v1/incidents")).json()
        assert len(incidents) == 1
        incident = incidents[0]
        assert incident["category"] == "network-intrusion"

        detail = (await api.get(f"/api/v1/incidents/{incident['incident_id']}")).json()
        rule_ids = {
            (await api.get(f"/api/v1/detections/{d}")).json()["rule_id"]
            for d in detail["detection_ids"]
        }
        assert {"NET-001", "NET-002", "NET-003"} <= rule_ids


async def test_no_duplicate_events_or_detections_on_replay(tmp_path):
    registry = _sensor_registry(tmp_path)
    first = await _run_pipeline(registry)
    assert first["detections"].detections_created >= 1

    second = await _run_pipeline(registry)
    assert all(r.ingested == 0 for r in second["ingestion"])
    assert second["detections"].detections_created == 0
    assert second["incidents"].incidents_created == 0


async def test_raw_provenance_traces_back_from_incident_to_the_real_sensor_payload(tmp_path):
    registry = _sensor_registry(tmp_path)
    await _run_pipeline(registry)

    transport = ASGITransport(app=sentinel_app)
    async with AsyncClient(transport=transport, base_url="http://test") as api:
        incidents = (await api.get("/api/v1/incidents")).json()
        detail = (await api.get(f"/api/v1/incidents/{incidents[0]['incident_id']}")).json()
        assert detail["event_ids"]

        for event_id in detail["event_ids"]:
            event = (await api.get(f"/api/v1/events/{event_id}")).json()
            assert event["source"] in ("suricata", "zeek")
            assert event["raw_sha256"]
            assert event["raw_payload"]  # the untouched original sensor record


async def test_a_failing_adapter_does_not_stop_the_others(tmp_path):
    """Malformed Suricata JSON in one adapter's file must not prevent Zeek's (or MissionNet's) own
    ingestion in the same cycle - Phase 8 §9/§18's core error-isolation requirement."""
    zeek_dir = _write_zeek_fixtures(tmp_path / "zeek")
    broken_eve = tmp_path / "broken" / "eve.json"
    broken_eve.parent.mkdir(parents=True)
    # A source_event_id KeyError inside the adapter (missing "flow_id") - a genuine adapter bug,
    # not just a malformed JSON line (that case is already unit-tested to skip silently).
    broken_eve.write_text(json.dumps({"event_type": "alert", "timestamp": "not-a-real-timestamp"}))

    registry = [
        AdapterDescriptor(
            adapter_id="suricata", name="Suricata", version="test", capabilities=[],
            configuration_requirements=[], supported_event_categories=["network"], enabled=True,
            streams={"alerts": suricata_alerts_adapter(str(broken_eve))},
        ),
        AdapterDescriptor(
            adapter_id="zeek", name="Zeek", version="test", capabilities=[],
            configuration_requirements=[], supported_event_categories=["network"], enabled=True,
            streams={"conn": zeek_conn_adapter(zeek_dir)},
        ),
    ]

    result = await _run_pipeline(registry)
    by_source = {r.source: r for r in result["ingestion"]}
    assert by_source["suricata"].error is not None
    assert by_source["zeek"].error is None
    assert by_source["zeek"].ingested == 1


async def test_integrations_endpoint_reflects_real_registry_state():
    transport = ASGITransport(app=sentinel_app)
    async with AsyncClient(transport=transport, base_url="http://test") as api:
        integrations = (await api.get("/api/v1/integrations")).json()
    ids = {i["adapter_id"] for i in integrations}
    assert ids == {"missionnet", "suricata", "zeek", "wazuh", "splunk", "falco"}
    missionnet = next(i for i in integrations if i["adapter_id"] == "missionnet")
    assert missionnet["status"] in ("ACTIVE", "DEGRADED")  # never hardcoded ACTIVE


async def test_event_explorer_filters_by_source_rule_and_ip(tmp_path):
    registry = _sensor_registry(tmp_path)
    await _run_pipeline(registry)

    transport = ASGITransport(app=sentinel_app)
    async with AsyncClient(transport=transport, base_url="http://test") as api:
        suricata_only = (await api.get("/api/v1/events", params={"source": "suricata"})).json()
        assert suricata_only and all(e["source"] == "suricata" for e in suricata_only)

        by_rule = (await api.get("/api/v1/events", params={"rule_id": "1000001"})).json()
        assert by_rule and all(e["rule_id"] == "1000001" for e in by_rule)

        by_src_ip = (await api.get("/api/v1/events", params={"src_ip": "172.28.0.3"})).json()
        assert by_src_ip and all(e["src_ip"] == "172.28.0.3" for e in by_src_ip)
