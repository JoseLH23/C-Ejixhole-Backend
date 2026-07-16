import json

import pytest

from scripts import production_pilot
from scripts.production_pilot import (
    ReadinessConfig,
    ReadinessError,
    _config_desde_entorno,
    _escribir_reporte,
    verificar_despliegues,
)


def config() -> ReadinessConfig:
    return ReadinessConfig(
        backend_url="https://backend.test",
        portal_url="https://portal.test/",
        admin_url="https://admin.test/",
    )


def test_config_predeterminada_solo_contiene_urls(monkeypatch):
    monkeypatch.delenv("BACKEND_URL", raising=False)
    monkeypatch.delenv("PORTAL_URL", raising=False)
    monkeypatch.delenv("ADMIN_URL", raising=False)

    resultado = _config_desde_entorno()

    assert resultado.backend_url.startswith("https://")
    assert not hasattr(resultado, "admin_password")
    assert not hasattr(resultado, "ejecutar_real")


def test_readiness_valida_las_piezas_publicas(monkeypatch):
    def json_falso(url):
        if url.endswith("/health/ready"):
            return {
                "status": "ready",
                "checks": {"database": "up", "notifications": "configured"},
            }
        if url.endswith("/publico/servicios"):
            return [{"nombre": "Acceso", "precio": "50.00"}]
        if "/publico/fechas-bloqueadas?" in url:
            return []
        raise AssertionError(f"URL inesperada: {url}")

    monkeypatch.setattr(production_pilot, "_json", json_falso)
    monkeypatch.setattr(
        production_pilot,
        "_verificar_shell",
        lambda nombre, _url: f"{nombre} disponible",
    )

    resultados = verificar_despliegues(config())

    assert len(resultados) == 5
    assert any("PostgreSQL" in item for item in resultados)
    assert any("Portal público" in item for item in resultados)
    assert any("Panel administrativo" in item for item in resultados)


def test_readiness_rechaza_correo_no_configurado(monkeypatch):
    monkeypatch.setattr(
        production_pilot,
        "_json",
        lambda _url: {
            "status": "ready",
            "checks": {"database": "up", "notifications": "not_configured"},
        },
    )

    with pytest.raises(ReadinessError, match="notificaciones"):
        verificar_despliegues(config())


def test_shell_react_requiere_root(monkeypatch):
    monkeypatch.setattr(
        production_pilot,
        "_request",
        lambda *_args, **_kwargs: (200, b"<html><body>sin app</body></html>"),
    )

    with pytest.raises(ReadinessError, match="contenedor React"):
        production_pilot._verificar_shell("Panel", "https://admin.test/")


def test_reporte_declara_que_no_modifico_produccion():
    reporte = _escribir_reporte(["Backend listo"])

    assert "Backend listo" in reporte
    assert "no creó ni modificó datos de producción" in reporte
    assert "password" not in reporte.lower()
