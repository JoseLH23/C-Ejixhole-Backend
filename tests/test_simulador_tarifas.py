from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.servicio import Servicio
from app.models.tarifa_especial import TarifaEspecial
from app.services.tarifa_especial_service import TarifaEspecialService


def crear_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    db.add(Servicio(nombre="Acceso al parque", precio="100.00", categoria="entrada", reservable=True, activo=True))
    db.commit()
    return db


def test_simulador_compara_precio_sin_guardar_candidata():
    db = crear_db()
    servicio = db.query(Servicio).one()
    resultado = TarifaEspecialService(db).simular(
        servicio_id=servicio.id,
        tipo_reservacion="entrada",
        fecha_llegada=date(2026, 12, 24),
        fecha_salida=date(2026, 12, 24),
        num_personas=2,
        unidad_hospedaje_id=None,
        candidata={
            "nombre": "Navidad prueba",
            "descripcion": None,
            "fecha_inicio": date(2026, 12, 20),
            "fecha_fin": date(2026, 12, 26),
            "porcentaje_ajuste": 25,
            "aplica_a": "entrada",
            "dias_semana": None,
            "prioridad": 20,
            "unidad_hospedaje_id": None,
            "activa": True,
        },
    )
    assert resultado["total_base"] == 200
    assert resultado["total_con_candidata"] == 250
    assert resultado["regla_ganadora"] == "Navidad prueba"
    assert db.query(TarifaEspecial).count() == 0


def test_simulador_detecta_conflicto_y_respeta_prioridad():
    db = crear_db()
    servicio = db.query(Servicio).one()
    db.add(TarifaEspecial(
        nombre="Festivo publicado",
        fecha_inicio=date(2026, 8, 15),
        fecha_fin=date(2026, 8, 15),
        porcentaje_ajuste="30",
        aplica_a="entrada",
        prioridad=50,
        activa=True,
    ))
    db.commit()
    resultado = TarifaEspecialService(db).simular(
        servicio_id=servicio.id,
        tipo_reservacion="entrada",
        fecha_llegada=date(2026, 8, 15),
        fecha_salida=date(2026, 8, 15),
        num_personas=1,
        unidad_hospedaje_id=None,
        candidata={
            "nombre": "Borrador",
            "descripcion": None,
            "fecha_inicio": date(2026, 8, 15),
            "fecha_fin": date(2026, 8, 15),
            "porcentaje_ajuste": -10,
            "aplica_a": "entrada",
            "dias_semana": None,
            "prioridad": 10,
            "unidad_hospedaje_id": None,
            "activa": True,
        },
    )
    assert resultado["total_actual"] == 130
    assert resultado["total_con_candidata"] == 130
    assert resultado["regla_ganadora"] == "Festivo publicado"
    assert resultado["conflictos"] == ["Festivo publicado"]
