from __future__ import annotations

from fastapi import HTTPException

from app.services.mh_core_marketing_service import MhCoreMarketingService


def _service(monkeypatch) -> MhCoreMarketingService:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("MH_CORE_URL", "http://mh-core.test")
    monkeypatch.setenv("MH_CORE_EJIXHOLE_KEY", "ejixhole-outbound-key-test")
    monkeypatch.setenv("MH_CORE_MARKETING_TIMEOUT_SECONDS", "75")
    return MhCoreMarketingService()


def test_status_transitorio_devuelve_warming_up_y_despierta(monkeypatch):
    service = _service(monkeypatch)
    calls = {"wake": 0, "status": 0}

    def fake_wake():
        calls["wake"] += 1

    def fake_request(method, path, *, payload=None, total_timeout=None):
        calls["status"] += 1
        assert method == "GET"
        assert path == "/mindhigh/marketing/status"
        assert total_timeout == 4.0
        raise HTTPException(status_code=502, detail="MH-Core respondió con estado 502.")

    monkeypatch.setattr(service, "_despertar_servicio", fake_wake)
    monkeypatch.setattr(service, "_request", fake_request)

    result = service.obtener_estado()

    assert calls == {"wake": 1, "status": 1}
    assert result["configured"] is True
    assert result["available"] is False
    assert result["warming_up"] is True
    assert "actualizará automáticamente" in result["message"]


def test_error_de_autorizacion_no_se_disfraza_como_arranque(monkeypatch):
    service = _service(monkeypatch)
    monkeypatch.setattr(service, "_despertar_servicio", lambda: None)

    def fake_request(method, path, *, payload=None, total_timeout=None):
        raise HTTPException(
            status_code=503,
            detail="La conexión privada con Marketing no está autorizada.",
        )

    monkeypatch.setattr(service, "_request", fake_request)

    result = service.obtener_estado()

    assert result["warming_up"] is False
    assert result["message"] == "La conexión privada con Marketing no está autorizada."


def test_error_permanente_de_servidor_no_se_disfraza_como_arranque(monkeypatch):
    service = _service(monkeypatch)
    monkeypatch.setattr(service, "_despertar_servicio", lambda: None)

    def fake_request(method, path, *, payload=None, total_timeout=None):
        raise HTTPException(status_code=502, detail="MH-Core respondió con estado 500.")

    monkeypatch.setattr(service, "_request", fake_request)

    result = service.obtener_estado()

    assert result["warming_up"] is False
    assert result["message"] == "MH-Core respondió con estado 500."


def test_respuesta_corrupta_no_se_disfraza_como_arranque(monkeypatch):
    service = _service(monkeypatch)
    monkeypatch.setattr(service, "_despertar_servicio", lambda: None)

    def fake_request(method, path, *, payload=None, total_timeout=None):
        raise HTTPException(status_code=502, detail="MH-Core devolvió una respuesta inesperada.")

    monkeypatch.setattr(service, "_request", fake_request)

    result = service.obtener_estado()

    assert result["warming_up"] is False
    assert result["message"] == "MH-Core devolvió una respuesta inesperada."


def test_status_disponible_cierra_estado_de_arranque(monkeypatch):
    service = _service(monkeypatch)
    monkeypatch.setattr(service, "_despertar_servicio", lambda: None)
    monkeypatch.setattr(
        service,
        "_request",
        lambda method, path, **kwargs: {
            "configured": True,
            "available": True,
            "knowledge_version": "2026.07.3",
            "documents": 11,
        },
    )

    result = service.obtener_estado()

    assert result["available"] is True
    assert result["warming_up"] is False
    assert result["documents"] == 11
    assert result["knowledge_version"] == "2026.07.3"


def test_sin_credencial_no_intenta_despertar(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("MH_CORE_URL", "http://mh-core.test")
    monkeypatch.delenv("MH_CORE_EJIXHOLE_KEY", raising=False)
    monkeypatch.delenv("MH_CORE_API_KEY", raising=False)
    service = MhCoreMarketingService()
    called = {"wake": False}
    monkeypatch.setattr(
        service,
        "_despertar_servicio",
        lambda: called.__setitem__("wake", True),
    )

    result = service.obtener_estado()

    assert called["wake"] is False
    assert result["configured"] is False
    assert result["warming_up"] is False
