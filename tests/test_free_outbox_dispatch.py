"""Pruebas del disparador gratuito y seguro del outbox."""
from dataclasses import dataclass

from fastapi.testclient import TestClient

from app.main import app


ROUTE = "/api/v1/integrations/mh-core/outbox/publish"
KEY = "dispatch-key-for-tests-with-more-than-32-characters"


@dataclass(frozen=True)
class FakeStats:
    claimed: int = 2
    published: int = 1
    retried: int = 1
    dead_letter: int = 0
    skipped: int = 0


class FakePublisher:
    def publish_once(self):
        return FakeStats()


def test_dispatch_falla_cerrado_si_no_esta_configurado(monkeypatch):
    monkeypatch.delenv("OUTBOX_DISPATCH_KEY", raising=False)
    response = TestClient(app).post(ROUTE)
    assert response.status_code == 503


def test_dispatch_rechaza_clave_incorrecta(monkeypatch):
    monkeypatch.setenv("OUTBOX_DISPATCH_KEY", KEY)
    response = TestClient(app).post(
        ROUTE,
        headers={"X-Outbox-Dispatch-Key": "incorrecta"},
    )
    assert response.status_code == 401


def test_dispatch_publica_un_solo_lote(monkeypatch):
    monkeypatch.setenv("OUTBOX_DISPATCH_KEY", KEY)
    monkeypatch.setattr(
        "app.routes.integracion_routes.OutboxPublisher",
        FakePublisher,
    )

    response = TestClient(app).post(
        ROUTE,
        headers={"X-Outbox-Dispatch-Key": KEY},
    )

    assert response.status_code == 200
    assert response.json() == {
        "claimed": 2,
        "published": 1,
        "retried": 1,
        "dead_letter": 0,
        "skipped": 0,
    }


def test_dispatch_no_existe_fuera_de_api_v1():
    paths = app.openapi()["paths"]
    assert ROUTE in paths
    assert "/integrations/mh-core/outbox/publish" not in paths
