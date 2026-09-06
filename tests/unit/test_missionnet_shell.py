from fastapi.testclient import TestClient

from apps.missionnet.main import app

client = TestClient(app)


def test_missionnet_health_is_synthetic():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["classification"] == "SYNTHETIC"
    assert body["status"] == "nominal"
