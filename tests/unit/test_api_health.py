from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_system_assurance_reports_external_ai_disabled():
    resp = client.get("/api/v1/system/assurance")
    assert resp.status_code == 200
    body = resp.json()
    assert body["external_ai_api"] == "disabled"
    assert body["inference_location"] == "local"


def test_system_profile():
    resp = client.get("/api/v1/system/profile")
    assert resp.status_code == 200
    assert resp.json()["profile"] == "lite"
