"""Pruebas del publicador confiable EjiXhole -> MH-Core."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json

import app.models  # noqa: F401: registra todos los modelos
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.outbox_event import OutboxEvent
from app.services.outbox_publisher_service import (
    OutboxPublisher,
    OutboxPublisherConfig,
)


NOW = datetime(2026, 7, 16, 15, 0, tzinfo=timezone.utc)
SECRET = "publisher-secret-for-tests-with-more-than-32-characters"


class FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None, *, contract="v1"):
        self.status_code = status_code
        self._payload = payload
        self.headers = {"X-MH-Event-Contract": contract} if contract else {}
        self.text = json.dumps(payload or {"detail": "error"})

    def json(self):
        if self._payload is None:
            raise ValueError("sin json")
        return self._payload


class AcceptingSession:
    def __init__(self, *, duplicate: bool = False):
        self.calls = []
        self.duplicate = duplicate

    def post(self, url, *, data, headers, timeout):
        envelope = json.loads(data)
        self.calls.append(
            {"url": url, "data": data, "headers": headers, "timeout": timeout}
        )
        return FakeResponse(
            202,
            {
                "event_id": envelope["event_id"],
                "accepted": True,
                "duplicate": self.duplicate,
            },
        )


class FixedSession:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def post(self, url, *, data, headers, timeout):
        self.calls.append(
            {"url": url, "data": data, "headers": headers, "timeout": timeout}
        )
        if self.error:
            raise self.error
        return self.response


def setup_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Session = sessionmaker(
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        bind=engine,
    )
    Base.metadata.create_all(bind=engine)
    return engine, Session


def config(**changes):
    values = {
        "events_url": "https://mh-core.example.test/integrations/ejixhole/events",
        "signing_secret": SECRET,
        "batch_size": 10,
        "max_attempts": 3,
        "lease_seconds": 30,
        "initial_backoff_seconds": 10,
        "max_backoff_seconds": 60,
        "request_timeout_seconds": 5,
        "poll_interval_seconds": 1,
    }
    values.update(changes)
    return OutboxPublisherConfig(**values)


def add_event(Session, **changes):
    values = {
        "event_key": "reservation.created:101",
        "event_type": "reservation.created",
        "aggregate_type": "reservation",
        "aggregate_id": "101",
        "schema_version": 1,
        "payload": {
            "reservation_id": 101,
            "service_id": 1,
            "unit_id": None,
            "reservation_type": "entrada",
            "arrival_date": "2026-08-20",
            "departure_date": "2026-08-20",
            "people": 2,
            "origin": "portal",
            "total": "200.00",
            "status": "pendiente",
        },
        "status": "pending",
        "attempts": 0,
        "available_at": NOW,
        "occurred_at": NOW,
    }
    values.update(changes)
    db = Session()
    event = OutboxEvent(**values)
    db.add(event)
    db.commit()
    db.refresh(event)
    event_id = event.id
    db.close()
    return event_id


def get_event(Session, event_id):
    db = Session()
    try:
        event = db.query(OutboxEvent).filter(OutboxEvent.id == event_id).one()
        db.expunge(event)
        return event
    finally:
        db.close()


def publisher(Session, http_session, **config_changes):
    return OutboxPublisher(
        config(**config_changes),
        session_factory=Session,
        http_session=http_session,
        worker_id="worker-test",
        now=lambda: NOW,
        sleeper=lambda _: None,
    )


def test_publica_json_canonico_firmado_y_marca_evento():
    engine, Session = setup_db()
    event_id = add_event(Session)
    http = AcceptingSession()

    stats = publisher(Session, http).publish_once()

    assert stats.claimed == 1
    assert stats.published == 1
    call = http.calls[0]
    body = call["data"]
    headers = call["headers"]
    expected_signature = hmac.new(
        SECRET.encode("utf-8"),
        headers["X-MH-Event-Timestamp"].encode("ascii") + b"." + body,
        hashlib.sha256,
    ).hexdigest()
    assert headers["X-MH-Event-Signature"] == f"sha256={expected_signature}"
    assert headers["X-MH-Event-Id"] == event_id

    envelope = json.loads(body)
    assert envelope["source"] == "ejixhole"
    assert envelope["aggregate"] == {"type": "reservation", "id": "101"}
    serialized = json.dumps(envelope).lower()
    for personal_field in ("email", "telefono", "nombre", "notas", "referencia"):
        assert personal_field not in serialized

    stored = get_event(Session, event_id)
    assert stored.status == "published"
    assert stored.attempts == 1
    assert stored.published_at is not None
    assert stored.locked_by is None
    engine.dispose()


def test_respuesta_duplicada_de_mh_core_cuenta_como_exito():
    engine, Session = setup_db()
    event_id = add_event(Session)

    stats = publisher(Session, AcceptingSession(duplicate=True)).publish_once()

    assert stats.published == 1
    assert get_event(Session, event_id).status == "published"
    engine.dispose()


def test_error_503_programa_reintento_con_backoff():
    engine, Session = setup_db()
    event_id = add_event(Session)
    response = FakeResponse(503, {"detail": "temporal"}, contract=None)

    stats = publisher(Session, FixedSession(response=response)).publish_once()

    stored = get_event(Session, event_id)
    assert stats.retried == 1
    assert stored.status == "failed"
    assert stored.attempts == 1
    # SQLite elimina la zona horaria al persistir DateTime; PostgreSQL conserva
    # TIMESTAMPTZ. Normalizamos únicamente el valor del doble de prueba.
    available_at = stored.available_at
    if available_at.tzinfo is None:
        available_at = available_at.replace(tzinfo=timezone.utc)
    assert available_at == NOW + timedelta(seconds=10)
    assert stored.last_http_status == 503
    engine.dispose()


def test_error_401_va_directo_a_dead_letter():
    engine, Session = setup_db()
    event_id = add_event(Session)
    response = FakeResponse(401, {"detail": "firma inválida"}, contract=None)

    stats = publisher(Session, FixedSession(response=response)).publish_once()

    stored = get_event(Session, event_id)
    assert stats.dead_letter == 1
    assert stored.status == "dead_letter"
    assert stored.attempts == 1
    assert stored.dead_lettered_at is not None
    engine.dispose()


def test_agota_intentos_y_envia_a_dead_letter():
    engine, Session = setup_db()
    event_id = add_event(Session, status="failed", attempts=2)
    response = FakeResponse(503, {"detail": "temporal"}, contract=None)

    stats = publisher(Session, FixedSession(response=response)).publish_once()

    stored = get_event(Session, event_id)
    assert stats.dead_letter == 1
    assert stored.status == "dead_letter"
    assert stored.attempts == 3
    engine.dispose()


def test_error_de_red_no_filtra_secret_y_reintenta():
    engine, Session = setup_db()
    event_id = add_event(Session)

    stats = publisher(
        Session,
        FixedSession(error=requests.Timeout(f"detalle {SECRET}")),
    ).publish_once()

    stored = get_event(Session, event_id)
    assert stats.retried == 1
    assert stored.status == "failed"
    assert SECRET not in (stored.last_error or "")
    assert stored.last_error == "Error de red: Timeout"
    engine.dispose()


def test_dos_workers_no_reclaman_el_mismo_evento():
    engine, Session = setup_db()
    event_id = add_event(Session)
    first = OutboxPublisher(
        config(),
        session_factory=Session,
        http_session=AcceptingSession(),
        worker_id="worker-a",
        now=lambda: NOW,
    )
    second = OutboxPublisher(
        config(),
        session_factory=Session,
        http_session=AcceptingSession(),
        worker_id="worker-b",
        now=lambda: NOW,
    )

    assert first.claim_batch() == [event_id]
    assert second.claim_batch() == []
    assert get_event(Session, event_id).locked_by == "worker-a"
    engine.dispose()


def test_lease_vencido_se_recupera_y_cuenta_intento():
    engine, Session = setup_db()
    event_id = add_event(
        Session,
        status="processing",
        locked_by="worker-muerto",
        locked_at=NOW - timedelta(seconds=31),
    )
    current = publisher(Session, AcceptingSession())

    assert current.claim_batch() == [event_id]

    stored = get_event(Session, event_id)
    assert stored.status == "processing"
    assert stored.locked_by == "worker-test"
    assert stored.attempts == 1
    engine.dispose()
