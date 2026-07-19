from fastapi.testclient import TestClient

from app.core.metrics import HttpMetricsRegistry, SloTargets
from app.core.observability import _safe_path
from app.main import app
from app.routes import observability_routes


client = TestClient(app)


def test_metricas_calculan_disponibilidad_error_y_percentiles():
    registry = HttpMetricsRegistry(sample_limit=10)
    for status_code, duration in [(200, 100), (200, 200), (503, 1400), (201, 300)]:
        registry.begin()
        registry.finish(status_code, duration)

    snapshot = registry.snapshot(SloTargets())

    assert snapshot["requests"]["total"] == 4
    assert snapshot["requests"]["server_errors"] == 1
    assert snapshot["slo"]["availability_percent"] == 75.0
    assert snapshot["slo"]["status"] == "degraded"
    assert snapshot["latency_ms"]["p95"] == 1400
    assert snapshot["slo"]["measurement"] == "rolling_request_window"


def test_disponibilidad_y_latencia_usan_la_misma_ventana():
    registry = HttpMetricsRegistry(sample_limit=2)
    for status_code, duration in [(503, 5000), (200, 100), (201, 200)]:
        registry.begin()
        registry.finish(status_code, duration)

    snapshot = registry.snapshot(SloTargets())

    assert snapshot["requests"]["lifetime_total"] == 3
    assert snapshot["requests"]["total"] == 2
    assert snapshot["requests"]["server_errors"] == 0
    assert snapshot["latency_ms"]["max"] == 200
    assert snapshot["window"]["samples"] == 2
    assert snapshot["slo"]["availability_percent"] == 100.0


def test_observabilidad_no_conserva_identificadores_de_alta_cardinalidad():
    assert _safe_path("/api/v1/reservaciones/123/check-in") == "/api/v1/reservaciones/{id}/check-in"
    assert _safe_path("/events/550e8400-e29b-41d4-a716-446655440000") == "/events/{uuid}"


def test_resumen_de_observabilidad_requiere_administrador():
    response = client.get("/api/v1/observabilidad/resumen")
    assert response.status_code == 401


def test_resumen_sigue_disponible_si_postgresql_falla(monkeypatch):
    class DatabaseUnavailable:
        def connect(self):
            raise RuntimeError("database unavailable")

    app.dependency_overrides[observability_routes.require_diagnostic_admin] = lambda: {
        "sub": "diagnostico",
        "rol": "admin",
    }
    monkeypatch.setattr(observability_routes, "engine", DatabaseUnavailable())
    try:
        response = client.get("/api/v1/observabilidad/resumen")
    finally:
        app.dependency_overrides.pop(observability_routes.require_diagnostic_admin, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["checks"]["database"] is False
    assert payload["dependencies"]["database"]["status"] == "down"


def test_observabilidad_no_se_publica_en_rutas_legacy():
    paths = set(app.openapi()["paths"])
    assert "/api/v1/observabilidad/resumen" in paths
    assert "/observabilidad/resumen" not in paths
