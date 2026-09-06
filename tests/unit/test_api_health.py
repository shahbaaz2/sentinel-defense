from fastapi.testclient import TestClient

from apps.api.config import settings
from apps.api.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_system_assurance_reports_external_ai_disabled():
    """Phase 5: external_ai_api is unconditionally DISABLED (no cloud LLM API ever exists in this
    project). ai_analyst_status reflects whatever SENTINEL_AI_ENABLED actually is on this machine -
    see tests/integration/test_coverage_and_assurance.py for why this isn't hardcoded to a single
    value."""
    resp = client.get("/api/v1/system/assurance")
    assert resp.status_code == 200
    body = resp.json()
    assert body["external_ai_api"] == "DISABLED"
    assert body["inference_location"] == "local"
    if settings.ai_enabled:
        assert body["ai_analyst_status"] in ("OPERATIONAL", "LOADING", "DEGRADED")
    else:
        assert body["ai_analyst_status"] == "NOT ENABLED"
    assert body["integrations"]["wazuh"] == "NOT_CONFIGURED"
    assert body["integrations"]["missionnet"] == "ACTIVE"


def test_system_profile():
    resp = client.get("/api/v1/system/profile")
    assert resp.status_code == 200
    assert resp.json()["profile"] == "lite"
