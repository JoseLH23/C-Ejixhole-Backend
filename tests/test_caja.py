"""
Pruebas del módulo Caja. Mismo patrón que los demás módulos: SQLite en
memoria, cliente autenticado por defecto vía el fixture `client`.

Correr con:
    pytest tests/test_caja.py -v
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.database import Base, get_db
from app.main import app
from app.models.caja import CajaMovimiento, CajaSesion  # noqa: F401
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
    """Cliente HTTP autenticado por defecto (las rutas exigen JWT)."""
    rol = Rol(nombre="admin", descripcion="Admin de prueba")
    db_session.add(rol)
    db_session.commit()
    db_session.refresh(rol)
    usuario = Usuario(
        nombre="Usuario Test",
        email="test-caja@ejixhole.com",
        password_hash="no-se-usa-en-estos-tests",
        rol_id=rol.id,
    )
    db_session.add(usuario)
    db_session.commit()
    db_session.refresh(usuario)
    token = create_access_token(subject=usuario.email, rol=rol.nombre)

    return TestClient(app, headers={"Authorization": f"Bearer {token}"})


@pytest.fixture()
def usuario_cajero(db_session):
    """Un usuario de negocio (distinto al de autenticación) para abrir cajas."""
    rol = Rol(nombre="cajero_test", descripcion="Cajero")
    db_session.add(rol)
    db_session.commit()
    db_session.refresh(rol)

    usuario = Usuario(
        nombre="Cajero Uno",
        email="cajero1@ejixhole.com",
        password_hash="hash-falso",
        rol_id=rol.id,
    )
    db_session.add(usuario)
    db_session.commit()
    db_session.refresh(usuario)
    return usuario


def test_abrir_caja(client, usuario_cajero):
    response = client.post(
        "/caja/abrir", json={"usuario_id": usuario_cajero.id, "monto_apertura": 500.00}
    )

    assert response.status_code == 201
    data = response.json()
    assert data["estado"] == "abierta"
    assert data["monto_apertura"] == "500.00"
    assert data["saldo_actual"] == "500.00"


def test_no_se_puede_abrir_dos_cajas_para_el_mismo_usuario(client, usuario_cajero):
    primera = client.post(
        "/caja/abrir", json={"usuario_id": usuario_cajero.id, "monto_apertura": 100.00}
    )
    assert primera.status_code == 201

    segunda = client.post(
        "/caja/abrir", json={"usuario_id": usuario_cajero.id, "monto_apertura": 200.00}
    )
    assert segunda.status_code == 409


def test_se_puede_abrir_nueva_caja_tras_cerrar_la_anterior(client, usuario_cajero):
    primera = client.post(
        "/caja/abrir", json={"usuario_id": usuario_cajero.id, "monto_apertura": 100.00}
    ).json()

    cierre = client.post(f"/caja/{primera['id']}/cerrar", json={"monto_cierre_real": 100.00})
    assert cierre.status_code == 200

    segunda = client.post(
        "/caja/abrir", json={"usuario_id": usuario_cajero.id, "monto_apertura": 200.00}
    )
    assert segunda.status_code == 201


def test_registrar_ingreso(client, usuario_cajero):
    sesion = client.post(
        "/caja/abrir", json={"usuario_id": usuario_cajero.id, "monto_apertura": 100.00}
    ).json()

    response = client.post(
        f"/caja/{sesion['id']}/movimientos",
        json={
            "usuario_id": usuario_cajero.id,
            "tipo": "ingreso",
            "monto": 250.00,
            "concepto": "Pago de anticipo en efectivo",
        },
    )

    assert response.status_code == 201
    assert response.json()["tipo"] == "ingreso"

    actualizada = client.get(f"/caja/{sesion['id']}").json()
    assert actualizada["saldo_actual"] == "350.00"


def test_registrar_egreso(client, usuario_cajero):
    sesion = client.post(
        "/caja/abrir", json={"usuario_id": usuario_cajero.id, "monto_apertura": 500.00}
    ).json()

    response = client.post(
        f"/caja/{sesion['id']}/movimientos",
        json={
            "usuario_id": usuario_cajero.id,
            "tipo": "egreso",
            "monto": 150.00,
            "concepto": "Compra de material de limpieza",
        },
    )

    assert response.status_code == 201

    actualizada = client.get(f"/caja/{sesion['id']}").json()
    assert actualizada["saldo_actual"] == "350.00"


def test_saldo_se_calcula_automaticamente_con_varios_movimientos(client, usuario_cajero):
    sesion = client.post(
        "/caja/abrir", json={"usuario_id": usuario_cajero.id, "monto_apertura": 1000.00}
    ).json()

    client.post(
        f"/caja/{sesion['id']}/movimientos",
        json={"usuario_id": usuario_cajero.id, "tipo": "ingreso", "monto": 500.00, "concepto": "Pago 1"},
    )
    client.post(
        f"/caja/{sesion['id']}/movimientos",
        json={"usuario_id": usuario_cajero.id, "tipo": "egreso", "monto": 200.00, "concepto": "Gasto 1"},
    )
    client.post(
        f"/caja/{sesion['id']}/movimientos",
        json={"usuario_id": usuario_cajero.id, "tipo": "ingreso", "monto": 300.00, "concepto": "Pago 2"},
    )

    actualizada = client.get(f"/caja/{sesion['id']}").json()
    # 1000.00 + 500.00 - 200.00 + 300.00 = 1600.00
    assert actualizada["saldo_actual"] == "1600.00"


def test_no_se_puede_registrar_movimiento_en_caja_cerrada(client, usuario_cajero):
    sesion = client.post(
        "/caja/abrir", json={"usuario_id": usuario_cajero.id, "monto_apertura": 100.00}
    ).json()
    client.post(f"/caja/{sesion['id']}/cerrar", json={"monto_cierre_real": 100.00})

    response = client.post(
        f"/caja/{sesion['id']}/movimientos",
        json={"usuario_id": usuario_cajero.id, "tipo": "ingreso", "monto": 50.00, "concepto": "Tarde"},
    )

    assert response.status_code == 400


def test_cerrar_caja_sin_diferencia(client, usuario_cajero):
    sesion = client.post(
        "/caja/abrir", json={"usuario_id": usuario_cajero.id, "monto_apertura": 200.00}
    ).json()
    client.post(
        f"/caja/{sesion['id']}/movimientos",
        json={"usuario_id": usuario_cajero.id, "tipo": "ingreso", "monto": 100.00, "concepto": "Pago"},
    )

    response = client.post(f"/caja/{sesion['id']}/cerrar", json={"monto_cierre_real": 300.00})

    assert response.status_code == 200
    data = response.json()
    assert data["estado"] == "cerrada"
    assert data["monto_cierre_esperado"] == "300.00"
    assert data["diferencia"] == "0.00"


def test_cerrar_caja_con_faltante(client, usuario_cajero):
    sesion = client.post(
        "/caja/abrir", json={"usuario_id": usuario_cajero.id, "monto_apertura": 200.00}
    ).json()

    response = client.post(f"/caja/{sesion['id']}/cerrar", json={"monto_cierre_real": 180.00})

    assert response.status_code == 200
    assert response.json()["diferencia"] == "-20.00"


def test_no_se_puede_cerrar_una_caja_ya_cerrada(client, usuario_cajero):
    sesion = client.post(
        "/caja/abrir", json={"usuario_id": usuario_cajero.id, "monto_apertura": 100.00}
    ).json()
    client.post(f"/caja/{sesion['id']}/cerrar", json={"monto_cierre_real": 100.00})

    response = client.post(f"/caja/{sesion['id']}/cerrar", json={"monto_cierre_real": 100.00})

    assert response.status_code == 400


def test_obtener_sesion_inexistente_da_404(client):
    response = client.get("/caja/9999")
    assert response.status_code == 404


def test_listar_movimientos_de_una_sesion(client, usuario_cajero):
    sesion = client.post(
        "/caja/abrir", json={"usuario_id": usuario_cajero.id, "monto_apertura": 100.00}
    ).json()
    client.post(
        f"/caja/{sesion['id']}/movimientos",
        json={"usuario_id": usuario_cajero.id, "tipo": "ingreso", "monto": 50.00, "concepto": "A"},
    )
    client.post(
        f"/caja/{sesion['id']}/movimientos",
        json={"usuario_id": usuario_cajero.id, "tipo": "egreso", "monto": 20.00, "concepto": "B"},
    )

    response = client.get(f"/caja/{sesion['id']}/movimientos")

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_corte_dia(client, usuario_cajero):
    sesion = client.post(
        "/caja/abrir", json={"usuario_id": usuario_cajero.id, "monto_apertura": 500.00}
    ).json()
    client.post(
        f"/caja/{sesion['id']}/movimientos",
        json={"usuario_id": usuario_cajero.id, "tipo": "ingreso", "monto": 300.00, "concepto": "Pago"},
    )
    client.post(
        f"/caja/{sesion['id']}/movimientos",
        json={"usuario_id": usuario_cajero.id, "tipo": "egreso", "monto": 100.00, "concepto": "Gasto"},
    )

    response = client.get("/caja/corte-dia")

    assert response.status_code == 200
    data = response.json()
    assert data["num_sesiones"] == 1
    assert data["total_ingresos"] == "300.00"
    assert data["total_egresos"] == "100.00"
    assert data["saldo_neto"] == "200.00"


def test_corte_dia_sin_sesiones_da_ceros(client):
    response = client.get("/caja/corte-dia")

    assert response.status_code == 200
    data = response.json()
    assert data["num_sesiones"] == 0
    assert data["total_ingresos"] == "0"
    assert data["total_egresos"] == "0"
    assert data["saldo_neto"] == "0"


def test_monto_apertura_negativo_rechazado_por_schema(client, usuario_cajero):
    response = client.post(
        "/caja/abrir", json={"usuario_id": usuario_cajero.id, "monto_apertura": -50.00}
    )
    assert response.status_code == 422


def test_tipo_movimiento_invalido_rechazado_por_schema(client, usuario_cajero):
    sesion = client.post(
        "/caja/abrir", json={"usuario_id": usuario_cajero.id, "monto_apertura": 100.00}
    ).json()

    response = client.post(
        f"/caja/{sesion['id']}/movimientos",
        json={"usuario_id": usuario_cajero.id, "tipo": "invalido", "monto": 10.00, "concepto": "X"},
    )
    assert response.status_code == 422


def test_rutas_caja_requieren_autenticacion():
    """Sin el fixture `client` autenticado: TestClient(app) puro, sin token."""
    response = TestClient(app).get("/caja")
    assert response.status_code == 401


# --- Permisos por rol (mini-entrega) ---------------------------------


def test_operador_puede_acceder_a_caja(db_session):
    rol = Rol(nombre="operador", descripcion="Operador")
    db_session.add(rol)
    db_session.commit()
    db_session.refresh(rol)
    usuario = Usuario(
        nombre="Operador Permiso", email="operador-permiso-caja@ejixhole.com",
        password_hash="x", rol_id=rol.id,
    )
    db_session.add(usuario)
    db_session.commit()
    db_session.refresh(usuario)
    token = create_access_token(subject=usuario.email, rol=rol.nombre)

    response = TestClient(app, headers={"Authorization": f"Bearer {token}"}).get("/caja")
    assert response.status_code == 200


def test_cajero_puede_acceder_a_caja(db_session):
    rol = Rol(nombre="cajero", descripcion="Cajero")
    db_session.add(rol)
    db_session.commit()
    db_session.refresh(rol)
    usuario = Usuario(
        nombre="Cajero Permiso", email="cajero-permiso-caja@ejixhole.com",
        password_hash="x", rol_id=rol.id,
    )
    db_session.add(usuario)
    db_session.commit()
    db_session.refresh(usuario)
    token = create_access_token(subject=usuario.email, rol=rol.nombre)

    response = TestClient(app, headers={"Authorization": f"Bearer {token}"}).get("/caja")
    assert response.status_code == 200


def test_rol_desconocido_no_puede_acceder_a_caja(db_session):
    """admin/operador/cajero son los 3 permitidos — cualquier otro rol debe rechazarse."""
    rol = Rol(nombre="invitado", descripcion="Sin permisos de caja")
    db_session.add(rol)
    db_session.commit()
    db_session.refresh(rol)
    usuario = Usuario(
        nombre="Invitado", email="invitado-caja@ejixhole.com",
        password_hash="x", rol_id=rol.id,
    )
    db_session.add(usuario)
    db_session.commit()
    db_session.refresh(usuario)
    token = create_access_token(subject=usuario.email, rol=rol.nombre)

    response = TestClient(app, headers={"Authorization": f"Bearer {token}"}).get("/caja")
    assert response.status_code == 403
