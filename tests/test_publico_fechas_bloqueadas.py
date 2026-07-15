from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.evento_calendario import EventoCalendario


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


@pytest.fixture()
def client(db_session):
    return TestClient(app)


def test_lista_solo_bloqueos_y_oculta_detalles_internos(client, db_session):
    db_session.add_all(
        [
            EventoCalendario(
                titulo="Cierre por mantenimiento mayor",
                tipo="bloqueo",
                fecha_inicio=date(2026, 8, 15),
                fecha_fin=date(2026, 8, 17),
                notas="Detalle interno que no debe salir",
            ),
            EventoCalendario(
                titulo="Publicar campaña",
                tipo="campana",
                fecha_inicio=date(2026, 8, 16),
                fecha_fin=date(2026, 8, 16),
            ),
        ]
    )
    db_session.commit()

    response = client.get(
        "/publico/fechas-bloqueadas",
        params={"desde": "2026-08-01", "hasta": "2026-08-31"},
    )

    assert response.status_code == 200
    assert response.json() == [
        {"fecha_inicio": "2026-08-15", "fecha_fin": "2026-08-17"}
    ]
    assert "titulo" not in response.text
    assert "notas" not in response.text


def test_incluye_bloqueo_que_inicia_antes_del_rango(client, db_session):
    db_session.add(
        EventoCalendario(
            titulo="Cierre largo",
            tipo="bloqueo",
            fecha_inicio=date(2026, 7, 28),
            fecha_fin=date(2026, 8, 2),
        )
    )
    db_session.commit()

    response = client.get(
        "/publico/fechas-bloqueadas",
        params={"desde": "2026-08-01", "hasta": "2026-08-31"},
    )

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_rechaza_rango_invertido(client):
    response = client.get(
        "/publico/fechas-bloqueadas",
        params={"desde": "2026-09-01", "hasta": "2026-08-01"},
    )
    assert response.status_code == 400


def test_limita_consulta_a_un_ano(client):
    response = client.get(
        "/publico/fechas-bloqueadas",
        params={"desde": "2026-01-01", "hasta": "2027-01-03"},
    )
    assert response.status_code == 400
