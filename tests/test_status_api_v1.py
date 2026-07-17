from fastapi.testclient import TestClient

from app.main import app


def test_status_disponible_bajo_api_v1():
    response = TestClient(app).get("/api/v1/status")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "online"
    assert body["api_version"] == "v1"
