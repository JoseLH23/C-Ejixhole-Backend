import io
import json

import pytest
from fastapi import HTTPException

from app.services.mh_core_dashboard_service import MhCoreDashboardService


class FakeResponse:
    def __init__(self, payload):
        self.body = io.BytesIO(json.dumps(payload).encode("utf-8"))

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.body.read()


def test_rechaza_integracion_sin_api_key(monkeypatch):
    monkeypatch.delenv("MH_CORE_API_KEY", raising=False)
    service = MhCoreDashboardService()

    with pytest.raises(HTTPException) as error:
        service.obtener_dashboard(days=7)

    assert error.value.status_code == 503


def test_envia_clave_solo_desde_backend(monkeypatch):
    monkeypatch.setenv("MH_CORE_API_KEY", "clave-servidor-segura")
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["key"] = request.headers["X-api-key"]
        captured["timeout"] = timeout
        return FakeResponse({"kpis": {"net_revenue": "100.00"}, "alerts": []})

    monkeypatch.setattr("app.services.mh_core_dashboard_service.urlopen", fake_urlopen)
    result = MhCoreDashboardService().obtener_dashboard(days=14)

    assert result["kpis"]["net_revenue"] == "100.00"
    assert captured["url"].endswith("executive-dashboard?days=14")
    assert captured["key"] == "clave-servidor-segura"
