from __future__ import annotations

import json
from io import BytesIO
from urllib.error import HTTPError

from app.services.mh_core_marketing_service import MhCoreMarketingService


class _FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def _configure(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("MH_CORE_URL", "http://mh-core.test")
    monkeypatch.setenv("MH_CORE_EJIXHOLE_KEY", "ejixhole-outbound-key-test")
    monkeypatch.setenv("MH_CORE_MARKETING_TIMEOUT_SECONDS", "5")
    monkeypatch.setattr("app.services.mh_core_marketing_service.time.sleep", lambda _: None)


def test_reintenta_502_temporal_y_recupera_conexion(monkeypatch):
    _configure(monkeypatch)
    calls = 0

    def fake_urlopen(request, timeout):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise HTTPError(
                request.full_url,
                502,
                "Bad Gateway",
                {},
                BytesIO(b"proxy despertando"),
            )
        return _FakeResponse(
            {
                "configured": True,
                "available": True,
                "knowledge_version": "2026.07.3",
                "documents": 11,
            }
        )

    monkeypatch.setattr("app.services.mh_core_marketing_service.urlopen", fake_urlopen)

    result = MhCoreMarketingService().obtener_estado()

    assert calls == 2
    assert result["available"] is True
    assert result["knowledge_version"] == "2026.07.3"


def test_no_reintenta_error_de_autenticacion(monkeypatch):
    _configure(monkeypatch)
    calls = 0

    def fake_urlopen(request, timeout):
        nonlocal calls
        calls += 1
        raise HTTPError(
            request.full_url,
            401,
            "Unauthorized",
            {},
            BytesIO(b"unauthorized"),
        )

    monkeypatch.setattr("app.services.mh_core_marketing_service.urlopen", fake_urlopen)

    result = MhCoreMarketingService().obtener_estado()

    assert calls == 1
    assert result["available"] is False
    assert result["message"] == "La conexión privada con Marketing no está autorizada."
