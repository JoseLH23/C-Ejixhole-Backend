from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.database import Base, get_db
from app.main import app
from app.models.usuario import Rol, Usuario
from app.services.mh_core_marketing_service import MhCoreMarketingService


CAMPAIGN = {
    "name": "Escapada familiar",
    "objective": "impulsar_reservas",
    "audience": "familias que buscan convivir en la naturaleza",
    "main_emotion": "tranquilidad y conexión",
    "offer_focus": "experiencia_general",
    "season": "verano",
    "knowledge_version": "2026.07.3",
    "knowledge_document_ids": ["brand", "marketing_strategy", "offer", "agent_rules"],
    "knowledge_citations": [
        "mhk://ejixhole/brand/2026.07.3",
        "mhk://ejixhole/marketing-strategy/2026.07.3",
        "mhk://ejixhole/offer/2026.07.3",
        "mhk://ejixhole/agent-rules/2026.07.3",
    ],
    "requires_human_approval": True,
    "dynamic_facts_used": [],
    "contents": [
        {
            "channel": "facebook",
            "headline": "Una escapada diferente",
            "body": "Descubre EjiXhole y conecta con la naturaleza.",
            "call_to_action": "Consulta la información vigente y solicita tu reservación en el portal oficial.",
            "hashtags": ["#EjiXhole", "#Naturaleza"],
        }
    ],
}


def _brief() -> dict:
    return {
        "name": "Escapada familiar",
        "objective": "impulsar_reservas",
        "audience": "familias que buscan convivir en la naturaleza",
        "main_emotion": "tranquilidad y conexión",
        "offer_focus": "experiencia_general",
        "season": "verano",
        "channels": ["facebook"],
        "call_to_action": "Consulta la información vigente y solicita tu reservación en el portal oficial.",
    }


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    session = TestingSessionLocal()
    yield session
    session.close()
    app.dependency_overrides.clear()


def _client_for_role(db_session, role_name: str) -> TestClient:
    role = Rol(nombre=role_name, descripcion=f"Rol {role_name}")
    db_session.add(role)
    db_session.commit()
    db_session.refresh(role)
    user = Usuario(
        nombre=f"Usuario {role_name}",
        email=f"{role_name}-marketing@ejixhole.com",
        password_hash="hash-no-usado",
        rol_id=role.id,
    )
    db_session.add(user)
    db_session.commit()
    token = create_access_token(subject=user.email, rol=role_name)
    return TestClient(app, headers={"Authorization": f"Bearer {token}"})


def test_marketing_requiere_autenticacion():
    response = TestClient(app).get("/api/v1/marketing/status")
    assert response.status_code == 401


def test_marketing_requiere_admin(db_session):
    client = _client_for_role(db_session, "operador")
    response = client.get("/api/v1/marketing/status")
    assert response.status_code == 403


def test_status_muestra_conexion_pendiente_sin_romper_panel(db_session, monkeypatch):
    client = _client_for_role(db_session, "admin")
    monkeypatch.setattr(
        MhCoreMarketingService,
        "obtener_estado",
        lambda self: {
            "configured": False,
            "available": False,
            "knowledge_version": None,
            "documents": 0,
            "message": "El módulo está preparado, pero MH-Core todavía no está configurado.",
        },
    )

    response = client.get("/api/v1/marketing/status")

    assert response.status_code == 200
    assert response.json()["configured"] is False
    assert response.json()["available"] is False


def test_admin_genera_borrador_citable(db_session, monkeypatch):
    client = _client_for_role(db_session, "admin")
    captured: dict = {}

    def fake_create(self, brief: dict):
        captured.update(brief)
        return CAMPAIGN

    monkeypatch.setattr(MhCoreMarketingService, "crear_borrador", fake_create)

    response = client.post("/api/v1/marketing/campaigns/draft", json=_brief())

    assert response.status_code == 200
    assert captured["channels"] == ["facebook"]
    assert response.json()["requires_human_approval"] is True
    assert len(response.json()["knowledge_citations"]) == 4


def test_brief_rechaza_canal_desconocido(db_session):
    client = _client_for_role(db_session, "admin")
    payload = _brief()
    payload["channels"] = ["tiktok_no_autorizado"]

    response = client.post("/api/v1/marketing/campaigns/draft", json=payload)

    assert response.status_code == 422


class _FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_cliente_envia_identidad_y_json_a_mh_core(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("MH_CORE_URL", "http://mh-core.test")
    monkeypatch.setenv("MH_CORE_SERVICE_KEY", "service-key-test")
    captured: dict = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return _FakeResponse(CAMPAIGN)

    monkeypatch.setattr("app.services.mh_core_marketing_service.urlopen", fake_urlopen)

    result = MhCoreMarketingService().crear_borrador(_brief())

    headers = {key.lower(): value for key, value in captured["headers"].items()}
    assert captured["url"] == "http://mh-core.test/mindhigh/marketing/campaigns/draft"
    assert headers["x-service-id"] == "ejixhole-backend"
    assert headers["x-api-key"] == "service-key-test"
    assert captured["payload"]["objective"] == "impulsar_reservas"
    assert result["knowledge_version"] == "2026.07.3"
