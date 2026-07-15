from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.evento_calendario import EventoCalendario
from app.services.bloqueo_operativo_service import BloqueoOperativoService


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def agregar_bloqueo(db_session, inicio="2026-08-15", fin="2026-08-17"):
    evento = EventoCalendario(
        titulo="Cierre por mantenimiento",
        tipo="bloqueo",
        fecha_inicio=date.fromisoformat(inicio),
        fecha_fin=date.fromisoformat(fin),
    )
    db_session.add(evento)
    db_session.commit()


def test_entrada_en_dia_bloqueado_es_rechazada(db_session):
    agregar_bloqueo(db_session)
    service = BloqueoOperativoService(db_session)

    with pytest.raises(HTTPException) as error:
        service.validar_disponibilidad(
            date(2026, 8, 16),
            date(2026, 8, 16),
            "entrada",
        )

    assert error.value.status_code == 409
    assert "Cierre por mantenimiento" in error.value.detail


def test_estancia_que_traslapa_bloqueo_es_rechazada(db_session):
    agregar_bloqueo(db_session)
    service = BloqueoOperativoService(db_session)

    with pytest.raises(HTTPException) as error:
        service.validar_disponibilidad(
            date(2026, 8, 14),
            date(2026, 8, 16),
            "camping",
        )

    assert error.value.status_code == 409


def test_checkout_el_dia_que_inicia_bloqueo_sigue_permitido(db_session):
    agregar_bloqueo(db_session, inicio="2026-08-15", fin="2026-08-15")
    service = BloqueoOperativoService(db_session)

    service.validar_disponibilidad(
        date(2026, 8, 14),
        date(2026, 8, 15),
        "hospedaje",
    )


def test_eventos_no_bloqueo_no_afectan_reservaciones(db_session):
    db_session.add(
        EventoCalendario(
            titulo="Publicar campaña",
            tipo="campana",
            fecha_inicio=date(2026, 8, 15),
            fecha_fin=date(2026, 8, 17),
        )
    )
    db_session.commit()

    assert BloqueoOperativoService(db_session).hay_disponibilidad(
        date(2026, 8, 16),
        date(2026, 8, 16),
        "entrada",
    )
