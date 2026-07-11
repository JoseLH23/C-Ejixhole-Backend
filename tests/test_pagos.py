"""
Pruebas del módulo Pagos. Mismo patrón que Reservaciones: SQLite en
memoria, cliente/servicio/usuario insertados directo por ORM.

Correr con:
    pytest tests/test_pagos.py -v
"""
import pytest
from fastapi.testclient import TestClient
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.database import Base, get_db
from app.main import app
from app.models.cliente import Cliente
from app.models.pago import Pago  # noqa: F401
from app.models.reservacion import Reservacion
from app.models.servicio import Servicio
from app.models.usuario import Rol, Usuario


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
    """
    Cliente HTTP autenticado por defecto (las rutas ahora exigen JWT).
    """
    rol = Rol(nombre="admin", descripcion="Admin de prueba")
    db_session.add(rol)
    db_session.commit()
    db_session.refresh(rol)
    usuario = Usuario(
        nombre="Usuario Test",
        email="test-pagos@ejixhole.com",
        password_hash="no-se-usa-en-estos-tests",
        rol_id=rol.id,
    )
    db_session.add(usuario)
    db_session.commit()
    db_session.refresh(usuario)
    token = create_access_token(subject=usuario.email, rol=rol.nombre)

    return TestClient(app, headers={"Authorization": f"Bearer {token}"})


@pytest.fixture()
def reservacion_pendiente(db_session):
    """Cliente + servicio + usuario + una reservación pendiente de $2000 (500 x 4)."""
    rol = Rol(nombre="cajero", descripcion="Cajero")
    db_session.add(rol)
    db_session.commit()
    db_session.refresh(rol)

    usuario = Usuario(
        nombre="Cajero Test",
        email="cajero@test.com",
        password_hash="hash-falso",
        rol_id=rol.id,
    )
    cliente = Cliente(nombre="Cliente Pago Test", telefono="5559998888")
    servicio = Servicio(nombre="Tour Test", precio="500.00", capacidad_maxima=10)
    db_session.add_all([usuario, cliente, servicio])
    db_session.commit()
    db_session.refresh(usuario)
    db_session.refresh(cliente)
    db_session.refresh(servicio)

    reservacion = Reservacion(
        cliente_id=cliente.id,
        servicio_id=servicio.id,
        usuario_id=usuario.id,
        fecha_visita=date(2026, 8, 15),
        num_personas=4,
        total="2000.00",
        monto_pagado="0",
    )
    db_session.add(reservacion)
    db_session.commit()
    db_session.refresh(reservacion)

    return {"usuario": usuario, "cliente": cliente, "servicio": servicio, "reservacion": reservacion}


def _payload(ctx, **overrides):
    base = {
        "reservacion_id": ctx["reservacion"].id,
        "usuario_id": ctx["usuario"].id,
        "monto": 500.00,
        "tipo": "anticipo",
        "metodo_pago": "efectivo",
    }
    base.update(overrides)
    return base


def test_registrar_pago_anticipo(client, reservacion_pendiente):
    response = client.post("/pagos", json=_payload(reservacion_pendiente))

    assert response.status_code == 201
    data = response.json()
    assert data["tipo"] == "anticipo"
    assert data["monto"] == "500.00"


def test_pago_actualiza_monto_pagado_de_la_reservacion(client, reservacion_pendiente):
    client.post("/pagos", json=_payload(reservacion_pendiente))

    reservacion = client.get(f"/reservaciones/{reservacion_pendiente['reservacion'].id}").json()
    assert reservacion["monto_pagado"] == "500.00"
    assert reservacion["saldo_pendiente"] == "1500.00"
    assert reservacion["estado"] == "pendiente"  # aún no cubre el total


def test_pago_completo_confirma_la_reservacion_automaticamente(client, reservacion_pendiente):
    client.post("/pagos", json=_payload(reservacion_pendiente, monto=2000.00, tipo="pago_completo"))

    reservacion = client.get(f"/reservaciones/{reservacion_pendiente['reservacion'].id}").json()
    assert reservacion["estado"] == "confirmada"
    assert reservacion["saldo_pendiente"] == "0.00"


def test_pagos_parciales_acumulan_hasta_confirmar(client, reservacion_pendiente):
    client.post("/pagos", json=_payload(reservacion_pendiente, monto=500.00, tipo="anticipo"))
    client.post("/pagos", json=_payload(reservacion_pendiente, monto=1000.00, tipo="pago_saldo"))

    reservacion_id = reservacion_pendiente["reservacion"].id
    reservacion = client.get(f"/reservaciones/{reservacion_id}").json()
    assert reservacion["monto_pagado"] == "1500.00"
    assert reservacion["estado"] == "pendiente"

    client.post("/pagos", json=_payload(reservacion_pendiente, monto=500.00, tipo="pago_saldo"))
    reservacion = client.get(f"/reservaciones/{reservacion_id}").json()
    assert reservacion["monto_pagado"] == "2000.00"
    assert reservacion["estado"] == "confirmada"


def test_no_se_puede_pagar_mas_del_saldo_pendiente(client, reservacion_pendiente):
    response = client.post(
        "/pagos", json=_payload(reservacion_pendiente, monto=5000.00, tipo="pago_completo")
    )
    assert response.status_code == 400
    assert "saldo pendiente" in response.json()["detail"].lower()


def test_no_se_puede_pagar_reservacion_cancelada(client, reservacion_pendiente, db_session):
    reservacion = reservacion_pendiente["reservacion"]
    reservacion.estado = "cancelada"
    db_session.commit()

    response = client.post("/pagos", json=_payload(reservacion_pendiente))

    assert response.status_code == 400
    assert "cancelada" in response.json()["detail"].lower()


def test_reembolso_resta_monto_pagado(client, reservacion_pendiente):
    client.post("/pagos", json=_payload(reservacion_pendiente, monto=2000.00, tipo="pago_completo"))

    response = client.post(
        "/pagos", json=_payload(reservacion_pendiente, monto=300.00, tipo="reembolso")
    )
    assert response.status_code == 201

    reservacion_id = reservacion_pendiente["reservacion"].id
    reservacion = client.get(f"/reservaciones/{reservacion_id}").json()
    assert reservacion["monto_pagado"] == "1700.00"


def test_no_se_puede_reembolsar_mas_de_lo_pagado(client, reservacion_pendiente):
    client.post("/pagos", json=_payload(reservacion_pendiente, monto=500.00, tipo="anticipo"))

    response = client.post(
        "/pagos", json=_payload(reservacion_pendiente, monto=999.00, tipo="reembolso")
    )

    assert response.status_code == 400
    assert "reembolsar" in response.json()["detail"].lower()


def test_reembolso_permitido_incluso_con_reservacion_cancelada(client, reservacion_pendiente, db_session):
    client.post("/pagos", json=_payload(reservacion_pendiente, monto=500.00, tipo="anticipo"))

    reservacion = reservacion_pendiente["reservacion"]
    reservacion.estado = "cancelada"
    db_session.commit()

    response = client.post(
        "/pagos", json=_payload(reservacion_pendiente, monto=500.00, tipo="reembolso")
    )
    assert response.status_code == 201


def test_registrar_pago_reservacion_inexistente(client, reservacion_pendiente):
    response = client.post("/pagos", json=_payload(reservacion_pendiente, reservacion_id=9999))
    assert response.status_code == 404


def test_listar_pagos_de_una_reservacion_orden_cronologico(client, reservacion_pendiente):
    reservacion_id = reservacion_pendiente["reservacion"].id
    client.post("/pagos", json=_payload(reservacion_pendiente, monto=500.00, tipo="anticipo"))
    client.post("/pagos", json=_payload(reservacion_pendiente, monto=300.00, tipo="pago_saldo"))

    response = client.get(f"/pagos/reservacion/{reservacion_id}")

    assert response.status_code == 200
    pagos = response.json()
    assert len(pagos) == 2
    assert pagos[0]["monto"] == "500.00"
    assert pagos[1]["monto"] == "300.00"


def test_tipo_de_pago_invalido_rechazado_por_schema(client, reservacion_pendiente):
    response = client.post("/pagos", json=_payload(reservacion_pendiente, tipo="tipo_inventado"))
    assert response.status_code == 422


def test_monto_negativo_rechazado_por_schema(client, reservacion_pendiente):
    response = client.post("/pagos", json=_payload(reservacion_pendiente, monto=-100))
    assert response.status_code == 422


# --- Permisos por rol (mini-entrega) ---------------------------------


def test_cajero_puede_listar_pagos(db_session):
    rol = Rol(nombre="cajero", descripcion="Cajero")
    db_session.add(rol)
    db_session.commit()
    db_session.refresh(rol)
    usuario = Usuario(
        nombre="Cajero Permiso", email="cajero-permiso-pagos@ejixhole.com",
        password_hash="x", rol_id=rol.id,
    )
    db_session.add(usuario)
    db_session.commit()
    db_session.refresh(usuario)
    token = create_access_token(subject=usuario.email, rol=rol.nombre)

    response = TestClient(app, headers={"Authorization": f"Bearer {token}"}).get("/pagos")
    assert response.status_code == 200


def test_operador_no_puede_acceder_a_pagos(db_session):
    rol = Rol(nombre="operador", descripcion="Operador")
    db_session.add(rol)
    db_session.commit()
    db_session.refresh(rol)
    usuario = Usuario(
        nombre="Operador Permiso", email="operador-permiso-pagos@ejixhole.com",
        password_hash="x", rol_id=rol.id,
    )
    db_session.add(usuario)
    db_session.commit()
    db_session.refresh(usuario)
    token = create_access_token(subject=usuario.email, rol=rol.nombre)

    response = TestClient(app, headers={"Authorization": f"Bearer {token}"}).get("/pagos")
    assert response.status_code == 403
