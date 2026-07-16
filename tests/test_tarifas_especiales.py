from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.servicio import Servicio
from app.models.tarifa_especial import TarifaEspecial
from app.services.publico_service import PublicoService
from app.services.tarifa_especial_service import TarifaEspecialService


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    session.add(Servicio(nombre="Acceso al parque", precio="100.00", categoria="entrada", reservable=True, activo=True))
    session.commit()
    yield session
    session.close()


def test_tarifa_alta_modifica_cotizacion_y_desglose(db):
    db.add(TarifaEspecial(
        nombre="Temporada alta",
        fecha_inicio=date(2026, 12, 20),
        fecha_fin=date(2027, 1, 5),
        porcentaje_ajuste="25.00",
        aplica_a="entrada",
        prioridad=10,
        activa=True,
    ))
    db.commit()

    noches, total, desglose = PublicoService(db).cotizar(
        "entrada", date(2026, 12, 24), date(2026, 12, 24), 2, None
    )

    assert noches == 0
    assert total == 250
    assert desglose[-1]["concepto"] == "Temporada alta"
    assert desglose[-1]["subtotal"] == 50


def test_promocion_por_dia_semana_solo_aplica_el_dia_configurado(db):
    servicio = TarifaEspecialService(db)
    servicio.crear(
        nombre="Promoción lunes",
        descripcion=None,
        fecha_inicio=date(2026, 7, 1),
        fecha_fin=date(2026, 7, 31),
        porcentaje_ajuste=-10,
        aplica_a="entrada",
        dias_semana=[0],
        prioridad=0,
        unidad_hospedaje_id=None,
        activa=True,
    )

    _, total_lunes, _ = PublicoService(db).cotizar("entrada", date(2026, 7, 6), date(2026, 7, 6), 1, None)
    _, total_martes, _ = PublicoService(db).cotizar("entrada", date(2026, 7, 7), date(2026, 7, 7), 1, None)

    assert total_lunes == 90
    assert total_martes == 100


def test_solo_se_aplica_la_regla_de_mayor_prioridad(db):
    db.add_all([
        TarifaEspecial(nombre="General", fecha_inicio=date(2026, 8, 1), fecha_fin=date(2026, 8, 31), porcentaje_ajuste="10", aplica_a="entrada", prioridad=1, activa=True),
        TarifaEspecial(nombre="Festivo", fecha_inicio=date(2026, 8, 15), fecha_fin=date(2026, 8, 15), porcentaje_ajuste="30", aplica_a="entrada", prioridad=20, activa=True),
    ])
    db.commit()

    _, total, desglose = PublicoService(db).cotizar("entrada", date(2026, 8, 15), date(2026, 8, 15), 1, None)

    assert total == 130
    assert [linea["concepto"] for linea in desglose][-1] == "Festivo"
