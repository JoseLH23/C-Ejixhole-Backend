"""
AL-04 (auditoría de seguridad 13/jul/2026): pruebas reales de doble
envío — confirman que reenviar la MISMA Idempotency-Key nunca crea un
segundo registro real, que reintentar con una key NUEVA sí funciona
normal, y que reusar una key con datos DISTINTOS se rechaza.
"""
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.cliente import Cliente
from app.models.reservacion import Reservacion
from app.models.servicio import Servicio
from app.models.unidad_hospedaje import UnidadHospedaje
from app.models.usuario import Rol, Usuario


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
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
    from app.core.security import create_access_token

    rol = Rol(nombre="admin", descripcion="Admin de prueba")
    db_session.add(rol)
    db_session.commit()
    db_session.refresh(rol)
    usuario = Usuario(
        nombre="Usuario Idempotencia", email="idempotencia@ejixhole.com",
        password_hash="no-se-usa", rol_id=rol.id,
    )
    db_session.add(usuario)
    db_session.commit()
    db_session.refresh(usuario)
    token = create_access_token(subject=usuario.email, rol=rol.nombre)

    cliente_http = TestClient(app, headers={"Authorization": f"Bearer {token}"})
    cliente_http.usuario_id = usuario.id
    return cliente_http


@pytest.fixture()
def datos_reservacion(db_session):
    cliente = Cliente(nombre="Cliente Idempotencia", telefono="5550009999")
    servicio = Servicio(nombre="Acceso al parque", precio="50.00", capacidad_maxima=10, categoria="entrada", reservable=True)
    db_session.add_all([cliente, servicio])
    db_session.commit()
    db_session.refresh(cliente)
    db_session.refresh(servicio)
    return {"cliente": cliente, "servicio": servicio}


def _payload_reservacion(datos, **overrides):
    base = {
        "cliente_id": datos["cliente"].id,
        "servicio_id": datos["servicio"].id,
        "tipo_reservacion": "entrada",
        "fecha_llegada": "2026-09-01",
        "fecha_salida": "2026-09-01",
        "num_personas": 2,
        "origen": "recepcion",
    }
    base.update(overrides)
    return base


# --- POST /reservaciones (interna) -----------------------------------


def test_doble_clic_con_misma_key_crea_una_sola_reservacion(client, datos_reservacion, db_session):
    headers = {"Idempotency-Key": "clic-doble-001"}
    payload = _payload_reservacion(datos_reservacion)

    r1 = client.post("/reservaciones", json=payload, headers=headers)
    r2 = client.post("/reservaciones", json=payload, headers=headers)

    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]  # la MISMA reservación, no una segunda
    assert db_session.query(Reservacion).count() == 1


def test_reintento_con_key_nueva_si_crea_una_reservacion_distinta(client, datos_reservacion, db_session):
    payload = _payload_reservacion(datos_reservacion)

    r1 = client.post("/reservaciones", json=payload, headers={"Idempotency-Key": "clave-a"})
    r2 = client.post("/reservaciones", json=payload, headers={"Idempotency-Key": "clave-b"})

    assert r1.json()["id"] != r2.json()["id"]
    assert db_session.query(Reservacion).count() == 2


def test_sin_header_se_comporta_exactamente_igual_que_antes(client, datos_reservacion, db_session):
    """Confirma AL-04 no rompe nada: sin Idempotency-Key, cada POST
    sigue creando su propia reservación, tal como hacía antes de esta
    fase — el doble envío accidental sin header sigue siendo posible
    (comportamiento sin cambios), es responsabilidad del cliente
    mandar la key si quiere protección."""
    payload = _payload_reservacion(datos_reservacion)

    r1 = client.post("/reservaciones", json=payload)
    r2 = client.post("/reservaciones", json=payload)

    assert r1.status_code == 201 and r2.status_code == 201
    assert r1.json()["id"] != r2.json()["id"]
    assert db_session.query(Reservacion).count() == 2


def test_misma_key_con_datos_distintos_es_rechazada(client, datos_reservacion):
    r1 = client.post(
        "/reservaciones", json=_payload_reservacion(datos_reservacion, num_personas=2),
        headers={"Idempotency-Key": "clave-reusada"},
    )
    r2 = client.post(
        "/reservaciones", json=_payload_reservacion(datos_reservacion, num_personas=5),
        headers={"Idempotency-Key": "clave-reusada"},
    )

    assert r1.status_code == 201
    assert r2.status_code == 409


# --- POST /publico/reservaciones (la más urgente según la auditoría) ------


def test_doble_clic_publico_crea_una_sola_solicitud(client, db_session):
    servicio_entrada = Servicio(nombre="Acceso al parque", precio="50.00", categoria="entrada", reservable=True)
    unidad = UnidadHospedaje(nombre="Cabaña Idempotencia", capacidad_maxima=4, precio_por_noche="800.00")
    db_session.add_all([servicio_entrada, unidad])
    db_session.commit()

    payload = {
        "nombre_completo": "Visitante Doble Clic",
        "email": "doble@example.com",
        "telefono": "4449998888",
        "tipo_reservacion": "entrada",
        "fecha_llegada": "2026-09-10",
        "fecha_salida": "2026-09-10",
        "num_personas": 2,
    }
    headers = {"Idempotency-Key": "portal-doble-clic-001"}

    r1 = client.post("/publico/reservaciones", json=payload, headers=headers)
    r2 = client.post("/publico/reservaciones", json=payload, headers=headers)

    assert r1.status_code == 201 and r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]
    assert db_session.query(Reservacion).count() == 1


# --- POST /pagos --------------------------------------------------------


def test_doble_clic_en_pago_no_cobra_dos_veces(client, datos_reservacion, db_session):
    reservacion = Reservacion(
        cliente_id=datos_reservacion["cliente"].id,
        servicio_id=datos_reservacion["servicio"].id,
        usuario_id=client.usuario_id,
        fecha_visita=date(2026, 9, 1),
        num_personas=2,
        total="100.00",
        monto_pagado="0",
    )
    db_session.add(reservacion)
    db_session.commit()
    db_session.refresh(reservacion)

    payload = {"reservacion_id": reservacion.id, "monto": 100.00, "tipo": "pago_completo", "metodo_pago": "efectivo"}
    headers = {"Idempotency-Key": "pago-doble-clic-001"}

    r1 = client.post("/pagos", json=payload, headers=headers)
    r2 = client.post("/pagos", json=payload, headers=headers)

    assert r1.status_code == 201 and r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]

    db_session.refresh(reservacion)
    assert str(reservacion.monto_pagado) == "100.00"  # NO 200.00 — no se cobró dos veces


# --- POST /caja/abrir y /caja/{id}/movimientos ------------------------


def test_doble_clic_al_abrir_caja_no_crea_dos_sesiones(client, db_session):
    headers = {"Idempotency-Key": "abrir-caja-001"}
    payload = {"monto_apertura": 500}

    r1 = client.post("/caja/abrir", json=payload, headers=headers)
    r2 = client.post("/caja/abrir", json=payload, headers=headers)

    assert r1.status_code == 201 and r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]


def test_doble_clic_en_movimiento_de_caja_no_lo_duplica(client, db_session):
    sesion = client.post("/caja/abrir", json={"monto_apertura": 500}).json()
    headers = {"Idempotency-Key": "movimiento-doble-001"}
    payload = {"tipo": "ingreso", "monto": 200, "concepto": "Venta de snacks"}

    r1 = client.post(f"/caja/{sesion['id']}/movimientos", json=payload, headers=headers)
    r2 = client.post(f"/caja/{sesion['id']}/movimientos", json=payload, headers=headers)

    assert r1.status_code == 201 and r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]

    movimientos = client.get(f"/caja/{sesion['id']}/movimientos").json()
    assert len(movimientos) == 1
