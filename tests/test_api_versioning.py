from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


RUTAS_REPRESENTATIVAS = (
    "/auth/login",
    "/clientes",
    "/reservaciones",
    "/pagos",
    "/caja",
    "/publico/servicios",
    "/usuarios",
    "/tarifas-especiales",
)


def test_todos_los_contratos_principales_existen_en_v1_y_legacy():
    paths = {route.path for route in app.routes}

    for legacy in RUTAS_REPRESENTATIVAS:
        assert legacy in paths
        assert f"/api/v1{legacy}" in paths


def test_ruta_v1_declara_version_sin_deprecacion():
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.headers["X-API-Version"] == "v1"
    assert "Deprecation" not in response.headers
    assert "successor-version" not in response.headers.get("Link", "")


def test_ruta_legacy_sigue_funcionando_y_anuncia_sucesora():
    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.headers["X-API-Version"] == "legacy"
    assert response.headers["Deprecation"] == "true"
    assert response.headers["Link"] == '</api/v1/auth/me>; rel="successor-version"'


def test_health_permanece_fuera_del_versionado_de_negocio():
    response = client.get("/health/live")

    assert response.status_code == 200
    assert "X-API-Version" not in response.headers
    assert "Deprecation" not in response.headers


def test_openapi_marca_solo_las_rutas_legacy_como_deprecadas():
    schema = app.openapi()

    assert schema["paths"]["/auth/me"]["get"]["deprecated"] is True
    assert not schema["paths"]["/api/v1/auth/me"]["get"].get("deprecated", False)


def test_status_publica_el_prefijo_actual():
    response = client.get("/status")

    assert response.status_code == 200
    assert response.json()["api_version"] == "v1"
    assert response.json()["api_prefix"] == "/api/v1"
