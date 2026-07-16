from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.evento_calendario import EventoCalendario
from app.models.unidad_hospedaje import UnidadHospedaje
from app.services.bloqueo_operativo_service import BloqueoOperativoService
from app.services.evento_calendario_service import EventoCalendarioService


@pytest.fixture()
def db():
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


@pytest.fixture()
def unidades(db):
    primera = UnidadHospedaje(
        nombre="Cabaña 1",
        tipo_unidad="cabana",
        capacidad_maxima=4,
        precio_por_noche=1000,
        activa=True,
    )
    segunda = UnidadHospedaje(
        nombre="Habitación 1",
        tipo_unidad="habitacion",
        capacidad_maxima=4,
        precio_por_noche=700,
        activa=True,
    )
    db.add_all([primera, segunda])
    db.commit()
    return primera, segunda


def test_bloqueo_de_unidad_no_cierra_las_demas(db, unidades):
    primera, segunda = unidades
    EventoCalendarioService(db).crear(
        titulo="Mantenimiento de cabaña",
        tipo="bloqueo",
        fecha_inicio=date(2026, 8, 10),
        fecha_fin=date(2026, 8, 12),
        notas=None,
        unidad_hospedaje_id=primera.id,
    )

    service = BloqueoOperativoService(db)
    assert not service.hay_disponibilidad(
        date(2026, 8, 10), date(2026, 8, 13), "hospedaje", primera.id
    )
    assert service.hay_disponibilidad(
        date(2026, 8, 10), date(2026, 8, 13), "hospedaje", segunda.id
    )
    assert service.hay_disponibilidad(
        date(2026, 8, 10), date(2026, 8, 13), "camping", None
    )


def test_bloqueo_global_cierra_todas_las_unidades(db, unidades):
    primera, segunda = unidades
    EventoCalendarioService(db).crear(
        titulo="Cierre general",
        tipo="bloqueo",
        fecha_inicio=date(2026, 9, 1),
        fecha_fin=date(2026, 9, 2),
        notas=None,
        unidad_hospedaje_id=None,
    )

    service = BloqueoOperativoService(db)
    for unidad in (primera, segunda):
        assert not service.hay_disponibilidad(
            date(2026, 9, 1), date(2026, 9, 3), "hospedaje", unidad.id
        )
    assert not service.hay_disponibilidad(
        date(2026, 9, 1), date(2026, 9, 3), "camping", None
    )


def test_unidad_solo_se_permite_en_evento_tipo_bloqueo(db, unidades):
    primera, _ = unidades
    with pytest.raises(HTTPException) as error:
        EventoCalendarioService(db).crear(
            titulo="Recordatorio",
            tipo="recordatorio",
            fecha_inicio=date(2026, 8, 10),
            fecha_fin=date(2026, 8, 10),
            notas=None,
            unidad_hospedaje_id=primera.id,
        )
    assert error.value.status_code == 422


def test_listado_publico_excluye_bloqueos_por_unidad(db, unidades):
    primera, _ = unidades
    db.add_all(
        [
            EventoCalendario(
                titulo="Global",
                tipo="bloqueo",
                fecha_inicio=date(2026, 8, 1),
                fecha_fin=date(2026, 8, 1),
            ),
            EventoCalendario(
                titulo="Solo cabaña",
                tipo="bloqueo",
                fecha_inicio=date(2026, 8, 2),
                fecha_fin=date(2026, 8, 2),
                unidad_hospedaje_id=primera.id,
            ),
        ]
    )
    db.commit()

    bloqueos = BloqueoOperativoService(db).listar_bloqueos(
        date(2026, 8, 1), date(2026, 8, 31)
    )
    assert [bloqueo.titulo for bloqueo in bloqueos] == ["Global"]
