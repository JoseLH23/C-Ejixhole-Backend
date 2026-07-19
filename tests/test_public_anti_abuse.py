from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

from app import models  # noqa: F401
from app.database import Base
from app.models.audit_event import AuditEvent
from app.models.public_submission_attempt import PublicSubmissionAttempt
from app.services.public_form_guard_service import PublicFormGuardService


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
    headers = [
        (b"x-forwarded-for", f"spoofed,{forwarded}".encode()),
        (b"x-public-client", client_id.encode()),
    ]
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/publico/reservaciones",
            "headers": headers,
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


def configurar(monkeypatch, *, mode="monitor", min_seconds=0):
    monkeypatch.setattr("app.services.formulario_publico_service.PUBLIC_ANTI_ABUSE_MODE", mode)
    monkeypatch.setattr("app.core.form_challenge.PUBLIC_CHALLENGE_MIN_SECONDS", min_seconds)


def test_desafio_valido_registra_solo_seudonimos(db, monkeypatch):
    configurar(monkeypatch)
    service = PublicFormGuardService(db)
    challenge = service.create_challenge()

    service.validate_and_record(request_publico(), datos(challenge["token"]))

    attempt = db.query(PublicSubmissionAttempt).one()
    assert attempt.allowed is True
    assert attempt.reason == "ok"
    assert len(attempt.ip_hash) == 64
    assert len(attempt.contact_hash) == 64
    assert "persona@example.test" not in repr(attempt.__dict__)
    assert "4440000000" not in repr(attempt.__dict__)


def test_honeypot_bloquea_en_modo_enforce_y_audita(db, monkeypatch):
    configurar(monkeypatch, mode="enforce")
    service = PublicFormGuardService(db)
    challenge = service.create_challenge()

    with pytest.raises(HTTPException) as exc:
        service.validate_and_record(request_publico(), datos(challenge["token"], website="bot-value"))

    assert exc.value.status_code == 400
    attempt = db.query(PublicSubmissionAttempt).one()
    assert attempt.allowed is False
    assert attempt.reason == "honeypot_filled"
    audit = db.query(AuditEvent).one()
    assert audit.accion == "publico.antiabuso_detectado"
    assert audit.contexto["reason"] == "honeypot_filled"


def test_modo_monitor_no_interrumpe_cliente_anterior_sin_desafio(db, monkeypatch):
    configurar(monkeypatch, mode="monitor")
    PublicFormGuardService(db).validate_and_record(request_publico(), datos())

    attempt = db.query(PublicSubmissionAttempt).one()
    assert attempt.allowed is True
    assert attempt.reason == "challenge_missing"


def test_nonce_no_puede_reutilizarse_en_modo_enforce(db, monkeypatch):
    configurar(monkeypatch, mode="enforce")
    service = PublicFormGuardService(db)
    challenge = service.create_challenge()
    service.validate_and_record(request_publico(), datos(challenge["token"]))

    with pytest.raises(HTTPException) as exc:
        service.validate_and_record(
            request_publico(client_id="otro-browser", forwarded="203.0.113.90"),
            datos(challenge["token"], email="otra@example.test"),
        )

    assert exc.value.status_code == 400
    assert db.query(PublicSubmissionAttempt).filter(
        PublicSubmissionAttempt.reason == "challenge_reused"
    ).count() == 1


def test_liberar_intento_permite_reintento_si_falla_el_negocio(db, monkeypatch):
    configurar(monkeypatch, mode="enforce")
    service = PublicFormGuardService(db)
    challenge = service.create_challenge()
    attempt = service.validate_and_record(request_publico(), datos(challenge["token"]))

    service.release(attempt)
    assert db.query(PublicSubmissionAttempt).count() == 0

    service.validate_and_record(request_publico(), datos(challenge["token"]))
    assert db.query(PublicSubmissionAttempt).count() == 1


def test_limite_ip_es_durable_y_devuelve_ventana_real(db, monkeypatch):
    configurar(monkeypatch, mode="enforce")
    monkeypatch.setattr("app.repositories.public_attempt_repository.PUBLIC_IP_HOURLY_LIMIT", 1)
    service = PublicFormGuardService(db)

    first = service.create_challenge()
    service.validate_and_record(request_publico(), datos(first["token"]))

    second = service.create_challenge()
    with pytest.raises(HTTPException) as exc:
        service.validate_and_record(
            request_publico(client_id="second-browser"),
            datos(second["token"], email="second@example.test"),
        )

    assert exc.value.status_code == 429
    retry_after = int(exc.value.headers["Retry-After"])
    assert 3500 <= retry_after <= 3600


def test_se_usa_ultima_ip_del_proxy(db, monkeypatch):
    configurar(monkeypatch)
    service = PublicFormGuardService(db)
    challenge = service.create_challenge()
    request = request_publico(forwarded="203.0.113.25")

    service.validate_and_record(request, datos(challenge["token"]))

    attempt = db.query(PublicSubmissionAttempt).one()
    assert attempt.ip_hash == service._pseudonym("ip", "203.0.113.25")
