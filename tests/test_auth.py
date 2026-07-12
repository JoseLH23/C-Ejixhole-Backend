"""
Pruebas del módulo Auth. SQLite en memoria, mismo patrón que los
otros módulos.

Correr con:
    pytest tests/test_auth.py -v
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token, hash_password
from app.database import Base, get_db
from app.main import app
from app.models.usuario import Rol, Usuario  # noqa: F401


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
    return TestClient(app)


@pytest.fixture()
def admin_creado(db_session):
    """Un rol admin + un usuario admin con contraseña conocida ('secreta123')."""
    rol = Rol(nombre="admin", descripcion="Administrador")
    db_session.add(rol)
    db_session.commit()
    db_session.refresh(rol)

    usuario = Usuario(
        nombre="Admin Test",
        email="admin@ejixhole.com",
        password_hash=hash_password("secreta123"),
        rol_id=rol.id,
    )
    db_session.add(usuario)
    db_session.commit()
    db_session.refresh(usuario)

    return {"usuario": usuario, "rol": rol}


@pytest.fixture()
def operador_creado(db_session):
    rol = Rol(nombre="operador", descripcion="Operador")
    db_session.add(rol)
    db_session.commit()
    db_session.refresh(rol)

    usuario = Usuario(
        nombre="Operador Test",
        email="operador@ejixhole.com",
        password_hash=hash_password("clave456"),
        rol_id=rol.id,
    )
    db_session.add(usuario)
    db_session.commit()
    db_session.refresh(usuario)

    return {"usuario": usuario, "rol": rol}


# --- Login ---------------------------------------------------------


def test_login_exitoso(client, admin_creado):
    response = client.post(
        "/auth/login", json={"email": "admin@ejixhole.com", "password": "secreta123"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_password_incorrecta(client, admin_creado):
    response = client.post(
        "/auth/login", json={"email": "admin@ejixhole.com", "password": "incorrecta"}
    )
    assert response.status_code == 401


def test_login_email_inexistente(client, admin_creado):
    response = client.post(
        "/auth/login", json={"email": "no-existe@ejixhole.com", "password": "cualquiera"}
    )
    assert response.status_code == 401


def test_login_usuario_desactivado(client, admin_creado, db_session):
    admin_creado["usuario"].activo = False
    db_session.commit()

    response = client.post(
        "/auth/login", json={"email": "admin@ejixhole.com", "password": "secreta123"}
    )
    assert response.status_code == 403


# --- Creación de usuarios (solo admin) ------------------------------


def test_crear_usuario_requiere_token(client, admin_creado):
    response = client.post(
        "/auth/usuarios",
        json={
            "nombre": "Nuevo",
            "email": "nuevo@ejixhole.com",
            "password": "clave789",
            "rol_id": admin_creado["rol"].id,
        },
    )
    assert response.status_code == 401  # sin Authorization header


def test_crear_usuario_como_admin(client, admin_creado):
    login = client.post(
        "/auth/login", json={"email": "admin@ejixhole.com", "password": "secreta123"}
    )
    token = login.json()["access_token"]

    response = client.post(
        "/auth/usuarios",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "nombre": "Nuevo",
            "email": "nuevo@ejixhole.com",
            "password": "clave789",
            "rol_id": admin_creado["rol"].id,
        },
    )
    assert response.status_code == 200
    assert response.json()["email"] == "nuevo@ejixhole.com"


def test_crear_usuario_como_no_admin_rechazado(client, operador_creado):
    login = client.post(
        "/auth/login", json={"email": "operador@ejixhole.com", "password": "clave456"}
    )
    token = login.json()["access_token"]

    response = client.post(
        "/auth/usuarios",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "nombre": "Otro",
            "email": "otro@ejixhole.com",
            "password": "clave000",
            "rol_id": operador_creado["rol"].id,
        },
    )
    assert response.status_code == 403


def test_crear_usuario_email_duplicado(client, admin_creado):
    login = client.post(
        "/auth/login", json={"email": "admin@ejixhole.com", "password": "secreta123"}
    )
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    client.post(
        "/auth/usuarios",
        headers=headers,
        json={
            "nombre": "Dup",
            "email": "dup@ejixhole.com",
            "password": "clave111",
            "rol_id": admin_creado["rol"].id,
        },
    )
    response = client.post(
        "/auth/usuarios",
        headers=headers,
        json={
            "nombre": "Dup2",
            "email": "dup@ejixhole.com",
            "password": "clave222",
            "rol_id": admin_creado["rol"].id,
        },
    )
    assert response.status_code == 400


# --- GET /auth/me ----------------------------------------------------


def test_me_sin_token_rechazado(client):
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_me_con_token_valido_devuelve_perfil_real(client, admin_creado):
    login = client.post(
        "/auth/login", json={"email": "admin@ejixhole.com", "password": "secreta123"}
    )
    token = login.json()["access_token"]

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["nombre"] == "Admin Test"
    assert data["email"] == "admin@ejixhole.com"
    assert data["rol"] == "admin"
    assert data["activo"] is True


def test_me_refleja_el_rol_correcto_de_otro_usuario(client, operador_creado):
    login = client.post(
        "/auth/login", json={"email": "operador@ejixhole.com", "password": "clave456"}
    )
    token = login.json()["access_token"]

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["rol"] == "operador"


def test_me_con_usuario_desactivado_rechazado(client, admin_creado, db_session):
    token = create_access_token(subject=admin_creado["usuario"].email, rol="admin")

    admin_creado["usuario"].activo = False
    db_session.commit()

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


# --- Protección de rutas de negocio ---------------------------------


def test_clientes_sin_token_rechazado(client):
    response = client.get("/clientes")
    assert response.status_code == 401


def test_clientes_con_token_invalido_rechazado(client):
    response = client.get("/clientes", headers={"Authorization": "Bearer token-invalido"})
    assert response.status_code == 401


def test_clientes_con_token_valido_permitido(client, admin_creado):
    token = create_access_token(subject=admin_creado["usuario"].email, rol="admin")
    response = client.get("/clientes", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200


def test_servicios_sin_token_rechazado(client):
    response = client.get("/servicios")
    assert response.status_code == 401


def test_reservaciones_sin_token_rechazado(client):
    response = client.get("/reservaciones")
    assert response.status_code == 401


def test_pagos_sin_token_rechazado(client):
    response = client.get("/pagos")
    assert response.status_code == 401


def test_token_de_usuario_desactivado_es_rechazado(client, admin_creado, db_session):
    token = create_access_token(subject=admin_creado["usuario"].email, rol="admin")

    admin_creado["usuario"].activo = False
    db_session.commit()

    response = client.get("/clientes", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
