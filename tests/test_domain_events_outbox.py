"""Pruebas de eventos de dominio y bandeja de salida transaccional."""
from datetime import date
from decimal import Decimal
import json
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401: registra todos los modelos en Base.metadata
from app.database import Base
from app.models.cliente import Cliente
from app.models.outbox_event import OutboxEvent
from app.models.servicio import Servicio
from app.models.usuario import Rol, Usuario
from app.services.flujo_visita_service import FlujoVisitaService
from app.services.outbox_service import OutboxService
from app.services.pago_service import PagoService
from app.services.reservacion_service import ReservacionService


@pytest.fixture()
def db_context():
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

    db = Session()
    rol = Rol(nombre="admin", descripcion="Administrador")
    db.add(rol)
    db.flush()
    usuario = Usuario(
        nombre="Admin Eventos",
        email="eventos@example.com",
        password_hash="hash-no-usado",
        rol_id=rol.id,
        activo=True,
    )
    cliente = Cliente(
        nombre="Persona que no debe salir en eventos",
        telefono="4440009999",
        email="privado@example.com",
    )
    servicio = Servicio(
        nombre="Acceso al parque",
        categoria="entrada",
        precio=Decimal("100.00"),
        capacidad_maxima=20,
        reservable=True,
        activo=True,
    )
    db.add_all([usuario, cliente, servicio])
    db.commit()

    try:
        yield db, Session, usuario, cliente, servicio
    finally:
        db.close()
        engine.dispose()


def _crear_reservacion(db, cliente, servicio, usuario, *, dia: int):
    fecha = date(2026, 8, dia)
    return ReservacionService(db).crear(
        cliente_id=cliente.id,
        servicio_id=servicio.id,
        usuario_id=usuario.id,
        tipo_reservacion="entrada",
        fecha_llegada=fecha,
        fecha_salida=fecha,
        unidad_hospedaje_id=None,
        num_personas=1,
        origen="recepcion",
        notas="Esta nota privada tampoco debe viajar.",
    )


def test_ciclo_operativo_guarda_eventos_pendientes_sin_datos_personales(db_context):
    db, _, usuario, cliente, servicio = db_context
    reservacion = _crear_reservacion(db, cliente, servicio, usuario, dia=20)

    pago = PagoService(db).registrar_pago(
        reservacion_id=reservacion.id,
        usuario_id=usuario.id,
        monto=Decimal("100.00"),
        tipo="pago_saldo",
        metodo_pago="tarjeta",
        referencia="terminal-e2e",
        notas=None,
    )
    assert pago.id is not None

    FlujoVisitaService(db).check_in(reservacion.id, usuario.id)
    FlujoVisitaService(db).check_out(reservacion.id, usuario.id)

    cancelada = _crear_reservacion(db, cliente, servicio, usuario, dia=21)
    ReservacionService(db).cambiar_estado(cancelada.id, "cancelada")

    eventos = db.query(OutboxEvent).order_by(OutboxEvent.created_at, OutboxEvent.event_type).all()
    tipos = [evento.event_type for evento in eventos]

    assert tipos.count("reservation.created") == 2
    assert tipos.count("reservation.confirmed") == 1
    assert tipos.count("payment.recorded") == 1
    assert tipos.count("reservation.cancelled") == 1
    assert tipos.count("visit.completed") == 1
    assert all(evento.status == "pending" for evento in eventos)
    assert all(evento.attempts == 0 for evento in eventos)
    assert len({evento.event_key for evento in eventos}) == len(eventos)
    assert all(uuid.UUID(evento.id) for evento in eventos)

    serializado = json.dumps([evento.payload for evento in eventos], ensure_ascii=False).lower()
    for dato_privado in (
        cliente.nombre.lower(),
        cliente.email.lower(),
        cliente.telefono,
        "nota privada",
        "terminal-e2e",
    ):
        assert dato_privado not in serializado


def test_reservacion_y_evento_se_revierten_juntos_si_falla_outbox(db_context, monkeypatch):
    db, Session, usuario, cliente, servicio = db_context

    def falla_outbox(*_args, **_kwargs):
        raise RuntimeError("outbox no disponible")

    monkeypatch.setattr(OutboxService, "record", staticmethod(falla_outbox))

    with pytest.raises(RuntimeError, match="outbox no disponible"):
        _crear_reservacion(db, cliente, servicio, usuario, dia=22)

    db.rollback()
    verificacion = Session()
    try:
        from app.models.reservacion import Reservacion

        assert verificacion.query(Reservacion).count() == 0
        assert verificacion.query(OutboxEvent).count() == 0
    finally:
        verificacion.close()
