from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app

client = TestClient(app)


def test_liveness_responde_sin_dependencias_externas():
    response = client.get("/health/live", headers={"X-Request-ID": "prueba-health-123"})

    assert response.status_code == 200
    assert response.json()["status"] == "alive"
    assert response.json()["service"] == "EjiXhole Experience OS"
    assert response.headers["X-Request-ID"] == "prueba-health-123"


def test_readiness_confirma_base_de_datos():
    class SesionDisponible:
        def execute(self, _query):
            return 1

    def db_disponible():
        yield SesionDisponible()

    app.dependency_overrides[get_db] = db_disponible
    try:
        response = client.get("/health/ready")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["checks"]["database"] == "up"
    assert payload["checks"]["notifications"] in {"configured", "not_configured"}
    assert response.headers["X-Request-ID"]


def test_readiness_devuelve_503_si_falla_la_base_de_datos():
    class SesionRota:
        def execute(self, _query):
            raise RuntimeError("fallo simulado")

    def db_rota():
        yield SesionRota()

    app.dependency_overrides[get_db] = db_rota
    try:
        response = client.get("/health/ready")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "unavailable"
    assert payload["checks"]["database"] == "down"
    assert "fallo simulado" not in response.text
