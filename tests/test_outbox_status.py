"""Pruebas del diagnóstico administrativo del canal EjiXhole -> MH-Core."""
from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.security import create_access_token
from app.database import Base, get_db
from app.main import app
from app.models.outbox_event import OutboxEvent
from app.models.usuario import Rol, Usuario


SIGNING_SECRET = "s" * 48


@pytest.fixture()
def context(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    db = Session()

    role = Rol(nombre="admin", descripcion="Administrador")
    db.add(role)
    db.flush()
    user = Usuario(
        nombre="Admin Outbox",
        email="admin-outbox@example.com",
        password_hash="hash-no-usado",
        rol_id=role.id,
        activo=True,
    )
    db.add(user)
    db.flush()
    event = OutboxEvent(
        event_key="reservation.created:700",
        event_type="reservation.created",
        aggregate_type="reservation",
        aggregate_id="700",
        schema_version=1,
        payload={"reservation_id": 700},
        status="published",
        attempts=1,
        available_at=datetime.now(timezone.utc),
        occurred_at=datetime.now(timezone.utc),
        published_at=datetime.now(timezone.utc),
        last_http_status=202,
    )
    db.add(event)
    db.commit()

    def override_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    monkeypatch.setenv(
        "MH_CORE_EVENTS_URL",
        "https://mh-core.example.test/integrations/ejixhole/events",
    )
    monkeypatch.setenv("MH_CORE_EVENT_SIGNING_SECRET", SIGNING_SECRET)
    token = create_access_token(subject=user.email, rol="admin")
    client = TestClient(app, headers={"Authorization": f"Bearer {token}"})

    try:
        yield client, event.id
    finally:
        client.close()
        db.close()
        app.dependency_overrides.clear()
        engine.dispose()


def test_status_es_v1_y_requiere_admin(context):
    _, _ = context
    response = TestClient(app).get("/api/v1/integrations/mh-core/outbox/status")

    assert response.status_code == 401


def test_status_no_expone_payload_ni_valor_del_secret(context):
    client, event_id = context

    response = client.get("/api/v1/integrations/mh-core/outbox/status")

    assert response.status_code == 200
    assert response.headers["X-API-Version"] == "v1"
    payload = response.json()
    assert payload["configured"] is True
    assert payload["signing_secret_configured"] is True
    assert payload["total_events"] == 1
    assert payload["by_status"]["published"] == 1
    assert payload["pending_delivery"] == 0
    assert payload["latest_published"]["event_id"] == event_id
    serialized = response.text.lower()
    assert "payload" not in serialized
    assert SIGNING_SECRET not in response.text


def test_url_invalida_no_reporta_canal_configurado(context, monkeypatch):
    client, _ = context
    monkeypatch.setenv("MH_CORE_EVENTS_URL", "https://")

    response = client.get("/api/v1/integrations/mh-core/outbox/status")

    assert response.status_code == 200
    assert response.json()["events_url_configured"] is False
    assert response.json()["configured"] is False


def test_evento_publicado_puede_confirmarse_por_uuid(context):
    client, event_id = context

    response = client.get(
        f"/api/v1/integrations/mh-core/outbox/events/{event_id}"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "published"
    assert response.json()["last_http_status"] == 202
    UUID(response.json()["event_id"])


def test_evento_inexistente_devuelve_404(context):
    client, _ = context

    response = client.get(
        "/api/v1/integrations/mh-core/outbox/events/00000000-0000-4000-8000-000000000000"
    )

    assert response.status_code == 404
