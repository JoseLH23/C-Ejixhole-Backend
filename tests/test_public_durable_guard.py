from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

from app.database import Base
from app.models.audit_event import AuditEvent
from app.models.intento_publico import IntentoPublico
from app.services.formulario_guard_service import FormularioGuardService


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def request_publico(*, client_id="browser-test", forwarded="198.51.100.40") -> Request:
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/publico/reservaciones",
            "headers": [
                (b"x-forwarded-for", f"spoofed,{forwarded}".encode()),
                (b"x-public-client", client_id.encode()),
            ],
            "client": ("127.0.0.1", 1234),
        }
    )
    request.state.request_id = f"request-{client_id}-{forwarded}"
    return request


def datos(token=None, website="", email="persona@example.test"):
    return SimpleNamespace(
        email=email,
        telefono="4440000000",
        form_challenge=token,
        website=website,
    )


def configurar(monkeypatch, *, modo="monitor", espera=0):
    monkeypatch.setattr("app.services.formulario_guard_service.MODO_PROTECCION_PUBLICA", modo)
    monkeypatch.setattr("app.core.desafio_formulario.ESPERA_MINIMA_SEGUNDOS", espera)


def test_desafio_valido_guarda_solo_huellas(db, monkeypatch):
    configurar(monkeypatch)
    service = FormularioGuardService(db)
    challenge = service.crear_desafio()
    service.reservar(request_publico(), datos(challenge["token"]))

    intento = db.query(IntentoPublico).one()
    assert intento.allowed is True
    assert intento.reason == "ok"
    assert len(intento.ip_hash) == 64
    assert len(intento.contact_hash) == 64
    assert "persona@example.test" not in repr(intento.__dict__)
    assert "4440000000" not in repr(intento.__dict__)


def test_honeypot_bloquea_y_audita_sin_pii(db, monkeypatch):
    configurar(monkeypatch, modo="enforce")
    service = FormularioGuardService(db)
    challenge = service.crear_desafio()

    with pytest.raises(HTTPException) as error:
        service.reservar(request_publico(), datos(challenge["token"], website="bot-value"))

    assert error.value.status_code == 400
    intento = db.query(IntentoPublico).one()
    assert intento.allowed is False
    assert intento.reason == "honeypot_filled"
    audit = db.query(AuditEvent).one()
    assert audit.contexto["reason"] == "honeypot_filled"
    assert "persona@example.test" not in repr(audit.contexto)


def test_monitor_conserva_compatibilidad_sin_desafio(db, monkeypatch):
    configurar(monkeypatch, modo="monitor")
    FormularioGuardService(db).reservar(request_publico(), datos())
    intento = db.query(IntentoPublico).one()
    assert intento.allowed is True
    assert intento.reason == "challenge_missing"


def test_nonce_es_de_un_solo_uso(db, monkeypatch):
    configurar(monkeypatch, modo="enforce")
    service = FormularioGuardService(db)
    challenge = service.crear_desafio()
    service.reservar(request_publico(), datos(challenge["token"]))

    with pytest.raises(HTTPException) as error:
        service.reservar(
            request_publico(client_id="otro", forwarded="203.0.113.90"),
            datos(challenge["token"], email="otra@example.test"),
        )

    assert error.value.status_code == 400
    assert db.query(IntentoPublico).filter(IntentoPublico.reason == "challenge_reused").count() == 1


def test_liberar_permita_reintento_si_falla_negocio(db, monkeypatch):
    configurar(monkeypatch, modo="enforce")
    service = FormularioGuardService(db)
    challenge = service.crear_desafio()
    intento = service.reservar(request_publico(), datos(challenge["token"]))
    service.liberar(intento)

    assert db.query(IntentoPublico).count() == 0
    service.reservar(request_publico(), datos(challenge["token"]))
    assert db.query(IntentoPublico).count() == 1


def test_cuota_durable_devuelve_ventana_real(db, monkeypatch):
    configurar(monkeypatch, modo="enforce")
    monkeypatch.setattr("app.repositories.intento_publico_repository.LIMITE_IP_HORA", 1)
    service = FormularioGuardService(db)
    first = service.crear_desafio()
    service.reservar(request_publico(), datos(first["token"]))

    second = service.crear_desafio()
    with pytest.raises(HTTPException) as error:
        service.reservar(
            request_publico(client_id="second"),
            datos(second["token"], email="second@example.test"),
        )

    assert error.value.status_code == 429
    assert 3500 <= int(error.value.headers["Retry-After"]) <= 3600


def test_usa_ip_agregada_por_el_proxy(db, monkeypatch):
    configurar(monkeypatch)
    service = FormularioGuardService(db)
    challenge = service.crear_desafio()
    service.reservar(request_publico(forwarded="203.0.113.25"), datos(challenge["token"]))
    intento = db.query(IntentoPublico).one()
    assert intento.ip_hash == service._seudonimo("ip", "203.0.113.25")
