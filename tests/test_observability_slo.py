from fastapi.testclient import TestClient

from app.core.metrics import HttpMetricsRegistry, SloTargets
from app.core.observability import _safe_path
from app.main import app


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


def test_observabilidad_no_conserva_identificadores_de_alta_cardinalidad():
    assert _safe_path("/api/v1/reservaciones/123/check-in") == "/api/v1/reservaciones/{id}/check-in"
    assert _safe_path("/events/550e8400-e29b-41d4-a716-446655440000") == "/events/{uuid}"


def test_resumen_de_observabilidad_requiere_administrador():
    response = client.get("/api/v1/observabilidad/resumen")
    assert response.status_code == 401


def test_observabilidad_no_se_publica_en_rutas_legacy():
    paths = set(app.openapi()["paths"])
    assert "/api/v1/observabilidad/resumen" in paths
    assert "/observabilidad/resumen" not in paths
