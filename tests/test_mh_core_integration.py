from datetime import date, datetime, timezone
from decimal import Decimal
import json

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.service_auth import require_mh_core_readonly
from app.main import app
from app.services.integracion_mh_service import IntegracionMhService

client = TestClient(app)
CLAVE = "mh-core-service-key-for-tests-with-more-than-32-characters"
RUTA = "/api/v1/integrations/mh-core/operational-summary"


def resumen_falso():
    return {
        "generated_at": datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc),
        "business_date": date(2026, 7, 16),
        "source": "ejixhole",
        "api_version": "v1",
        "access": "read_only",
        "scope": "ejixhole:read:operations",
        "metrics": {
            "ingresos_hoy": Decimal("1500.00"),
            "ingresos_mes": Decimal("12000.00"),
            "reservaciones_activas": 4,
            "proximas_7_dias": 3,
            "saldo_pendiente_total": Decimal("500.00"),
            "tasa_cancelacion_mes": 2.5,
            "ocupacion_promedio_mes": 64.0,
            "diferencia_caja_hoy": Decimal("0.00"),
        },
    }


def test_integracion_existe_solo_bajo_api_v1():
    paths = app.openapi()["paths"]

    assert RUTA in paths
    assert "/integrations/mh-core/operational-summary" not in paths
    assert set(paths[RUTA]) == {"get"}


def test_integracion_falla_cerrado_sin_credencial_configurada(monkeypatch):
    monkeypatch.delenv("MH_CORE_SERVICE_KEY", raising=False)

    response = client.get(RUTA)

    assert response.status_code == 503
    assert "no está configurada" in response.json()["detail"]


def test_integracion_rechaza_credencial_incorrecta(monkeypatch):
    monkeypatch.setenv("MH_CORE_SERVICE_KEY", CLAVE)

    response = client.get(RUTA, headers={"X-MH-Service-Key": "incorrecta"})

    assert response.status_code == 401


def test_integracion_rechaza_unicode_sin_error_500(monkeypatch):
    monkeypatch.setenv("MH_CORE_SERVICE_KEY", CLAVE)

    with pytest.raises(HTTPException) as error:
        require_mh_core_readonly(x_mh_service_key="clave-inválida-ñ")

    assert error.value.status_code == 401
    assert error.value.detail == "Credencial de servicio inválida o faltante."


def test_integracion_entrega_solo_metricas_agregadas(monkeypatch):
    monkeypatch.setenv("MH_CORE_SERVICE_KEY", CLAVE)
    monkeypatch.setattr(
        IntegracionMhService,
        "resumen_operativo",
        lambda _self: resumen_falso(),
    )

    response = client.get(RUTA, headers={"X-MH-Service-Key": CLAVE})

    assert response.status_code == 200
    assert response.headers["X-API-Version"] == "v1"
    payload = response.json()
    assert payload["access"] == "read_only"
    assert payload["scope"] == "ejixhole:read:operations"
    assert payload["metrics"]["reservaciones_activas"] == 4

    serializado = json.dumps(payload).lower()
    for campo_personal in ("email", "telefono", "teléfono", "nombre_cliente", "observaciones"):
        assert campo_personal not in serializado


def test_integracion_no_acepta_escrituras(monkeypatch):
    monkeypatch.setenv("MH_CORE_SERVICE_KEY", CLAVE)

    response = client.post(RUTA, headers={"X-MH-Service-Key": CLAVE}, json={})
    assert response.status_code == 405
