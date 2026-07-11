"""
Pruebas del módulo Clientes.

Usan SQLite en memoria (no tu Postgres real) para que corran rápido y
aisladas. Esto es válido para Clientes porque su tabla no depende de
características específicas de Postgres (los índices únicos parciales
solo existen en reservaciones y caja_sesiones, no aquí).

Correr con:
    pytest tests/test_clientes.py -v
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.database import Base, get_db
from app.main import app
from app.models.cliente import Cliente  # noqa: F401  (registra la tabla en Base.metadata)
from app.models.usuario import Rol, Usuario


@pytest.fixture()
def client():
    """
    Cliente HTTP autenticado por defecto: las rutas ahora exigen JWT
    (ver app/dependencies.py), asi que este fixture crea un usuario de
    prueba y manda su token en cada request automaticamente. Ningun
    test individual necesita saber esto.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    setup_session = TestingSessionLocal()
    rol = Rol(nombre="admin", descripcion="Admin de prueba")
    setup_session.add(rol)
    setup_session.commit()
    setup_session.refresh(rol)
    usuario = Usuario(
        nombre="Usuario Test",
        email="test@ejixhole.com",
        password_hash="no-se-usa-en-estos-tests",
        rol_id=rol.id,
    )
    setup_session.add(usuario)
    setup_session.commit()
    setup_session.refresh(usuario)
    token = create_access_token(subject=usuario.email, rol=rol.nombre)
    setup_session.close()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app, headers={"Authorization": f"Bearer {token}"})
    app.dependency_overrides.clear()


def _cliente_autenticado_con_rol(rol_nombre):
    """Helper: arma un TestClient autenticado con el rol indicado, en su
    propia base SQLite aislada. Usado por las pruebas de permisos."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    rol = Rol(nombre=rol_nombre, descripcion=f"{rol_nombre} de prueba")
    session.add(rol)
    session.commit()
    session.refresh(rol)
    usuario = Usuario(
        nombre=f"Usuario {rol_nombre}",
        email=f"{rol_nombre}@ejixhole.com",
        password_hash="no-se-usa-en-estos-tests",
        rol_id=rol.id,
    )
    session.add(usuario)
    session.commit()
    session.refresh(usuario)
    token = create_access_token(subject=usuario.email, rol=rol.nombre)
    session.close()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app, headers={"Authorization": f"Bearer {token}"})


@pytest.fixture()
def client_operador():
    yield _cliente_autenticado_con_rol("operador")
    app.dependency_overrides.clear()


@pytest.fixture()
def client_rol_no_permitido():
    """Rol cajero: NO está en la lista de roles permitidos para Clientes."""
    yield _cliente_autenticado_con_rol("cajero")
    app.dependency_overrides.clear()


def test_crear_cliente(client):
    response = client.post(
        "/clientes",
        json={"nombre": "Juan", "apellido": "Pérez", "telefono": "4441234567", "email": "juan@test.com"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["cliente_creado"]["nombre"] == "Juan"
    assert data["posibles_duplicados"] == []


def test_crear_cliente_detecta_duplicado_por_telefono(client):
    client.post("/clientes", json={"nombre": "Ana", "telefono": "4440000000"})

    response = client.post("/clientes", json={"nombre": "Ana Otra", "telefono": "4440000000"})

    assert response.status_code == 201
    data = response.json()
    assert len(data["posibles_duplicados"]) == 1
    assert data["posibles_duplicados"][0]["nombre"] == "Ana"


def test_crear_cliente_detecta_duplicado_por_email(client):
    client.post("/clientes", json={"nombre": "Luis", "email": "luis@test.com"})

    response = client.post("/clientes", json={"nombre": "Luis Otro", "email": "luis@test.com"})

    data = response.json()
    assert len(data["posibles_duplicados"]) == 1


def test_obtener_cliente_por_id(client):
    creado = client.post("/clientes", json={"nombre": "Sofía"}).json()["cliente_creado"]

    response = client.get(f"/clientes/{creado['id']}")

    assert response.status_code == 200
    assert response.json()["nombre"] == "Sofía"


def test_obtener_cliente_inexistente_da_404(client):
    response = client.get("/clientes/9999")
    assert response.status_code == 404


def test_listar_clientes(client):
    client.post("/clientes", json={"nombre": "Cliente A"})
    client.post("/clientes", json={"nombre": "Cliente B"})

    response = client.get("/clientes")

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_actualizar_cliente(client):
    creado = client.post("/clientes", json={"nombre": "Pedro", "telefono": "111"}).json()["cliente_creado"]

    response = client.put(f"/clientes/{creado['id']}", json={"telefono": "222"})

    assert response.status_code == 200
    assert response.json()["telefono"] == "222"
    assert response.json()["nombre"] == "Pedro"  # no se tocó


def test_actualizar_cliente_rechaza_duplicado(client):
    client.post("/clientes", json={"nombre": "Original", "telefono": "999"})
    otro = client.post("/clientes", json={"nombre": "Otro", "telefono": "111"}).json()["cliente_creado"]

    response = client.put(f"/clientes/{otro['id']}", json={"telefono": "999"})

    assert response.status_code == 409


def test_desactivar_cliente_sin_reservaciones(client):
    creado = client.post("/clientes", json={"nombre": "Desactivable"}).json()["cliente_creado"]

    response = client.delete(f"/clientes/{creado['id']}")

    assert response.status_code == 200
    assert response.json()["activo"] is False

    # ya no aparece en el listado por defecto (solo_activos=True)
    listado = client.get("/clientes").json()
    assert all(c["id"] != creado["id"] for c in listado)


# --- Permisos por rol (mini-entrega) ---------------------------------


def test_operador_puede_listar_clientes(client_operador):
    response = client_operador.get("/clientes")
    assert response.status_code == 200


def test_cajero_no_puede_acceder_a_clientes(client_rol_no_permitido):
    response = client_rol_no_permitido.get("/clientes")
    assert response.status_code == 403


def test_sin_token_da_401():
    response = TestClient(app).get("/clientes")
    assert response.status_code == 401
