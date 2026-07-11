"""
Pruebas del módulo Servicios. Mismo patrón que los otros 3 módulos:
SQLite en memoria, aislado de Postgres real.

Correr con:
    pytest tests/test_servicios.py -v
"""
import pytest
from fastapi.testclient import TestClient
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.cliente import Cliente
from app.models.reservacion import Reservacion
from app.models.servicio import Servicio  # noqa: F401
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
    from app.core.security import create_access_token

    rol = Rol(nombre="admin", descripcion="Admin de prueba")
    db_session.add(rol)
    db_session.commit()
    db_session.refresh(rol)
    usuario = Usuario(
        nombre="Usuario Test",
        email="test-servicios@ejixhole.com",
        password_hash="no-se-usa-en-estos-tests",
        rol_id=rol.id,
    )
    db_session.add(usuario)
    db_session.commit()
    db_session.refresh(usuario)
    token = create_access_token(subject=usuario.email, rol=rol.nombre)

    return TestClient(app, headers={"Authorization": f"Bearer {token}"})


def _payload(**overrides):
    base = {
        "nombre": "Tour Huasteca",
        "descripcion": "Recorrido por cascadas y ríos",
        "precio": 500.00,
        "duracion_minutos": 120,
        "capacidad_maxima": 10,
        "categoria": "aventura",
    }
    base.update(overrides)
    return base


def test_crear_servicio(client):
    response = client.post("/servicios", json=_payload())

    assert response.status_code == 201
    data = response.json()
    assert data["nombre"] == "Tour Huasteca"
    assert data["precio"] == "500.00"
    assert data["activo"] is True


def test_crear_servicio_precio_negativo_rechazado(client):
    response = client.post("/servicios", json=_payload(precio=-10))
    assert response.status_code == 422


def test_crear_servicio_capacidad_invalida_rechazada(client):
    response = client.post("/servicios", json=_payload(capacidad_maxima=0))
    assert response.status_code == 422


def test_crear_servicio_duracion_invalida_rechazada(client):
    response = client.post("/servicios", json=_payload(duracion_minutos=-5))
    assert response.status_code == 422


def test_obtener_servicio_por_id(client):
    creado = client.post("/servicios", json=_payload()).json()

    response = client.get(f"/servicios/{creado['id']}")

    assert response.status_code == 200
    assert response.json()["nombre"] == "Tour Huasteca"


def test_obtener_servicio_inexistente_da_404(client):
    response = client.get("/servicios/9999")
    assert response.status_code == 404


def test_listar_servicios_solo_activos_por_defecto(client):
    activo = client.post("/servicios", json=_payload(nombre="Activo")).json()
    inactivo = client.post("/servicios", json=_payload(nombre="Inactivo")).json()
    client.delete(f"/servicios/{inactivo['id']}")

    listado = client.get("/servicios").json()

    ids = [s["id"] for s in listado]
    assert activo["id"] in ids
    assert inactivo["id"] not in ids


def test_listar_servicios_incluye_inactivos_si_se_pide(client):
    inactivo = client.post("/servicios", json=_payload(nombre="Inactivo2")).json()
    client.delete(f"/servicios/{inactivo['id']}")

    listado = client.get("/servicios", params={"solo_activos": False}).json()

    ids = [s["id"] for s in listado]
    assert inactivo["id"] in ids


def test_listar_servicios_filtra_por_categoria(client):
    client.post("/servicios", json=_payload(nombre="Aventura A", categoria="aventura"))
    client.post("/servicios", json=_payload(nombre="Relax A", categoria="relax"))

    aventura = client.get("/servicios", params={"categoria": "aventura"}).json()

    assert all(s["categoria"] == "aventura" for s in aventura)
    assert len(aventura) == 1


def test_actualizar_servicio(client):
    creado = client.post("/servicios", json=_payload()).json()

    response = client.put(f"/servicios/{creado['id']}", json={"precio": 650.00})

    assert response.status_code == 200
    assert response.json()["precio"] == "650.00"
    assert response.json()["nombre"] == "Tour Huasteca"  # no se tocó


def test_desactivar_servicio_sin_reservaciones(client):
    creado = client.post("/servicios", json=_payload()).json()

    response = client.delete(f"/servicios/{creado['id']}")

    assert response.status_code == 200
    assert response.json()["activo"] is False


def test_no_se_puede_desactivar_servicio_con_reservacion_activa(client, db_session):
    servicio = client.post("/servicios", json=_payload()).json()

    rol = Rol(nombre="operador", descripcion="Operador")
    db_session.add(rol)
    db_session.commit()
    db_session.refresh(rol)

    usuario = Usuario(
        nombre="Operador Test", email="op@test.com", password_hash="hash-falso", rol_id=rol.id
    )
    cliente = Cliente(nombre="Cliente Servicio Test")
    db_session.add_all([usuario, cliente])
    db_session.commit()
    db_session.refresh(usuario)
    db_session.refresh(cliente)

    reservacion = Reservacion(
        cliente_id=cliente.id,
        servicio_id=servicio["id"],
        usuario_id=usuario.id,
        fecha_visita=date(2026, 8, 15),
        num_personas=2,
        total="1000.00",
        monto_pagado="0",
    )
    db_session.add(reservacion)
    db_session.commit()

    response = client.delete(f"/servicios/{servicio['id']}")

    assert response.status_code == 409


def test_no_se_puede_reducir_capacidad_bajo_reservacion_activa_existente(client, db_session):
    servicio = client.post("/servicios", json=_payload(capacidad_maxima=10)).json()

    rol = Rol(nombre="operador2", descripcion="Operador")
    db_session.add(rol)
    db_session.commit()
    db_session.refresh(rol)

    usuario = Usuario(
        nombre="Operador Test 2", email="op2@test.com", password_hash="hash-falso", rol_id=rol.id
    )
    cliente = Cliente(nombre="Cliente Servicio Test 2")
    db_session.add_all([usuario, cliente])
    db_session.commit()
    db_session.refresh(usuario)
    db_session.refresh(cliente)

    reservacion = Reservacion(
        cliente_id=cliente.id,
        servicio_id=servicio["id"],
        usuario_id=usuario.id,
        fecha_visita=date(2026, 8, 15),
        num_personas=8,
        total="4000.00",
        monto_pagado="0",
    )
    db_session.add(reservacion)
    db_session.commit()

    response = client.put(f"/servicios/{servicio['id']}", json={"capacidad_maxima": 5})

    assert response.status_code == 409


# --- Permisos por rol (mini-entrega) ---------------------------------


def test_operador_no_puede_acceder_a_servicios(db_session):
    from app.core.security import create_access_token

    rol = Rol(nombre="operador_permiso_servicios", descripcion="Operador")
    db_session.add(rol)
    db_session.commit()
    db_session.refresh(rol)
    usuario = Usuario(
        nombre="Operador Permiso", email="operador-permiso-servicios@ejixhole.com",
        password_hash="x", rol_id=rol.id,
    )
    db_session.add(usuario)
    db_session.commit()
    db_session.refresh(usuario)
    token = create_access_token(subject=usuario.email, rol=rol.nombre)

    response = TestClient(app, headers={"Authorization": f"Bearer {token}"}).get("/servicios")
    assert response.status_code == 403


def test_admin_puede_acceder_a_servicios(client):
    response = client.get("/servicios")
    assert response.status_code == 200
