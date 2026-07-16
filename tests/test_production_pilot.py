import json

import pytest

from scripts.production_pilot import (
    CONFIRMACION_REAL,
    HttpClient,
    PilotConfig,
    PilotError,
    _config_desde_entorno,
    _escribir_reporte,
    ejecutar_piloto_real,
    verificar_despliegues,
)


class ClienteFalso:
    def json(self, method, url, **_kwargs):
        if url.endswith("/health/ready"):
            return {
                "status": "ready",
                "checks": {"database": "up", "notifications": "configured"},
            }
        if url.endswith("/publico/servicios"):
            return [{"nombre": "Acceso", "precio": "50.00"}]
        raise AssertionError(f"Solicitud inesperada: {method} {url}")

    def request(self, method, url, **_kwargs):
        assert method == "GET"
        assert url in {"https://portal.test/", "https://admin.test/"}
        return 200, b'<html><div id="root"></div></html>', {}


def config(ejecutar_real=False, email="", password=""):
    return PilotConfig(
        backend_url="https://backend.test",
        portal_url="https://portal.test/",
        admin_url="https://admin.test/",
        ejecutar_real=ejecutar_real,
        admin_email=email,
        admin_password=password,
        run_id="prueba-1",
    )


def test_modo_predeterminado_no_ejecuta_piloto_real(monkeypatch):
    monkeypatch.delenv("PILOT_CONFIRMATION", raising=False)
    resultado = _config_desde_entorno()

    assert resultado.ejecutar_real is False


def test_confirmacion_debe_coincidir_exactamente(monkeypatch):
    monkeypatch.setenv("PILOT_CONFIRMATION", CONFIRMACION_REAL)
    resultado = _config_desde_entorno()

    assert resultado.ejecutar_real is True


def test_readiness_valida_las_tres_piezas_publicas():
    resultados = verificar_despliegues(config(), ClienteFalso())

    assert len(resultados) == 4
    assert any("PostgreSQL" in item for item in resultados)
    assert any("Portal público" in item for item in resultados)
    assert any("Panel administrativo" in item for item in resultados)


def test_piloto_real_se_bloquea_sin_credenciales():
    with pytest.raises(PilotError, match="PILOT_ADMIN_EMAIL"):
        ejecutar_piloto_real(config(ejecutar_real=True), HttpClient())


def test_reporte_no_expone_credenciales_y_registra_ids():
    reporte = _escribir_reporte(
        ["Backend listo"],
        {
            "reservacion_id": 123,
            "caja_sesion_id": 45,
            "fecha_visita": "2026-08-01",
        },
    )

    assert "#123" in reporte
    assert "#45" in reporte
    assert "password" not in reporte.lower()
    assert "admin@" not in reporte.lower()


def test_json_del_cliente_acepta_respuesta_204(monkeypatch):
    cliente = HttpClient()
    monkeypatch.setattr(cliente, "request", lambda *_args, **_kwargs: (204, b"", {}))

    assert cliente.json("POST", "https://backend.test/auth/logout", expected=(204,)) is None
