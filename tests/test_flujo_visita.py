"""Prueba integrada: reservación -> caja/pago -> check-in -> check-out."""
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.database import Base, get_db
from app.main import app
from app.models.caja import CajaMovimiento, CajaSesion
from app.models.cliente import Cliente
from app.models.reservacion import Reservacion
from app.models.servicio import Servicio
from app.models.usuario import Rol, Usuario


@pytest.fixture()
def contexto():
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
    db = TestingSessionLocal()

    rol = Rol(nombre="admin", descripcion="Administrador")
    db.add(rol)
    db.commit()
    db.refresh(rol)
    usuario = Usuario(
        nombre="Admin Flujo",
        email="admin-flujo@ejixhole.com",
        password_hash="hash-no-usado",
        rol_id=rol.id,
    )
    cliente = Cliente(nombre="Visitante Flujo", telefono="4440001111")
    servicio = Servicio(
        nombre="Acceso al parque",
        categoria="entrada",
        precio="100.00",
        capacidad_maxima=10,
        reservable=True,
    )
    db.add_all([usuario, cliente, servicio])
    db.commit()
    db.refresh(usuario)
    db.refresh(cliente)
    db.refresh(servicio)

    reservacion = Reservacion(
        cliente_id=cliente.id,
        servicio_id=servicio.id,
        usuario_id=usuario.id,
        fecha_visita=date(2026, 8, 15),
        fecha_llegada=date(2026, 8, 15),
        fecha_salida=date(2026, 8, 15),
        num_personas=1,
        tipo_reservacion="entrada",
        estado="confirmada",
        total="100.00",
        monto_pagado="0.00",
    )
    db.add(reservacion)
    db.commit()
    db.refresh(reservacion)

    token = create_access_token(subject=usuario.email, rol=rol.nombre)
    client = TestClient(app, headers={"Authorization": f"Bearer {token}"})

    yield {
        "db": db,
        "client": client,
        "usuario": usuario,
        "reservacion": reservacion,
    }

    db.close()
    app.dependency_overrides.clear()


def test_flujo_completo_registra_pago_en_caja_y_completa_visita(contexto):
    client = contexto["client"]
    db = contexto["db"]
    usuario = contexto["usuario"]
    reservacion = contexto["reservacion"]

    caja = CajaSesion(usuario_id=usuario.id, monto_apertura="500.00", estado="abierta")
    db.add(caja)
    db.commit()
    db.refresh(caja)

    checkin = client.post(f"/reservaciones/{reservacion.id}/check-in")
    assert checkin.status_code == 200
    assert checkin.json()["estado"] == "en_curso"
    assert checkin.json()["fecha_checkin"] is not None

    sin_pago = client.post(f"/reservaciones/{reservacion.id}/check-out")
    assert sin_pago.status_code == 409
    assert "saldo" in sin_pago.json()["detail"].lower()

    pago = client.post(
        "/pagos",
        json={
            "reservacion_id": reservacion.id,
            "monto": "100.00",
            "tipo": "pago_saldo",
            "metodo_pago": "efectivo",
        },
        headers={"Idempotency-Key": "flujo-visita-pago-001"},
    )
    assert pago.status_code == 201

    movimiento = db.query(CajaMovimiento).filter(CajaMovimiento.pago_id == pago.json()["id"]).one()
    assert movimiento.caja_sesion_id == caja.id
    assert movimiento.tipo == "ingreso"
    assert str(movimiento.monto) == "100.00"

    checkout = client.post(f"/reservaciones/{reservacion.id}/check-out")
    assert checkout.status_code == 200
    assert checkout.json()["estado"] == "completada"
    assert checkout.json()["pago_completo"] is True
    assert checkout.json()["fecha_checkout"] is not None


def test_no_se_puede_saltar_directamente_a_completada(contexto):
    reservacion = contexto["reservacion"]
    response = contexto["client"].patch(
        f"/reservaciones/{reservacion.id}/estado",
        json={"nuevo_estado": "completada"},
    )
    assert response.status_code == 409
    assert "check" in response.json()["detail"].lower()


def test_pago_efectivo_exige_caja_abierta(contexto):
    reservacion = contexto["reservacion"]
    response = contexto["client"].post(
        "/pagos",
        json={
            "reservacion_id": reservacion.id,
            "monto": "50.00",
            "tipo": "anticipo",
            "metodo_pago": "efectivo",
        },
        headers={"Idempotency-Key": "flujo-sin-caja-001"},
    )
    assert response.status_code == 409
    assert "caja" in response.json()["detail"].lower()
