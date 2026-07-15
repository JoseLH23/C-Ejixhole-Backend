"""Pruebas del contrato CORS usado por los dos frontends.

Estas pruebas reproducen el preflight que hace un navegador antes de
crear reservaciones o pagos con el header Idempotency-Key.
"""

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _preflight(origin: str, path: str) -> object:
    return client.options(
        path,
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,idempotency-key",
        },
    )


def test_portal_publico_permite_idempotency_key():
    response = _preflight(
        "https://ejixhole-reservas.vercel.app",
        "/publico/reservaciones",
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "https://ejixhole-reservas.vercel.app"
    )
    headers_permitidos = response.headers["access-control-allow-headers"].lower()
    assert "idempotency-key" in headers_permitidos
    assert "content-type" in headers_permitidos


def test_frontend_interno_permite_idempotency_key():
    response = _preflight(
        "https://ejixhole-frontend.vercel.app",
        "/pagos",
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "https://ejixhole-frontend.vercel.app"
    )
    assert "idempotency-key" in response.headers[
        "access-control-allow-headers"
    ].lower()


def test_origen_no_autorizado_es_rechazado():
    response = _preflight(
        "https://sitio-no-autorizado.example",
        "/publico/reservaciones",
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
