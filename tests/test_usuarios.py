"""
Pruebas del módulo Usuarios (listar). SQLite en memoria, mismo patrón
que los demás módulos (ver tests/test_auth.py).

Correr con:
    PYTHONPATH=. pytest tests/test_usuarios.py -v
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
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
def operador_creado(db_session, admin_creado):
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


def _token_de(client, email, password):
    login = client.post("/auth/login", json={"email": email, "password": password})
    return login.json()["access_token"]


# --- GET /usuarios -----------------------------------------------------


def test_listar_usuarios_sin_token_rechazado(client):
    response = client.get("/usuarios")
    assert response.status_code == 401


def test_listar_usuarios_como_no_admin_rechazado(client, operador_creado):
    token = _token_de(client, "operador@ejixhole.com", "clave456")
    response = client.get("/usuarios", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_listar_usuarios_como_admin_devuelve_todos(client, admin_creado, operador_creado):
    token = _token_de(client, "admin@ejixhole.com", "secreta123")
    response = client.get("/usuarios", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    emails = {u["email"] for u in data}
    assert emails == {"admin@ejixhole.com", "operador@ejixhole.com"}
    # Cada usuario trae su rol real, no un placeholder.
    roles = {u["email"]: u["rol"] for u in data}
    assert roles["admin@ejixhole.com"] == "admin"
    assert roles["operador@ejixhole.com"] == "operador"


def test_listar_usuarios_respeta_limit(client, admin_creado, operador_creado):
    token = _token_de(client, "admin@ejixhole.com", "secreta123")
    response = client.get("/usuarios?limit=1", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert len(response.json()) == 1


# --- GET /usuarios/roles ------------------------------------------------


def test_listar_roles_como_admin(client, admin_creado, operador_creado):
    token = _token_de(client, "admin@ejixhole.com", "secreta123")
    response = client.get("/usuarios/roles", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    nombres = {r["nombre"] for r in response.json()}
    assert nombres == {"admin", "operador"}


def test_listar_roles_como_no_admin_rechazado(client, operador_creado):
    token = _token_de(client, "operador@ejixhole.com", "clave456")
    response = client.get("/usuarios/roles", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


# --- DELETE /usuarios/{id} (desactivar) ----------------------------------


def test_desactivar_usuario_como_admin(client, admin_creado, operador_creado):
    token = _token_de(client, "admin@ejixhole.com", "secreta123")
    response = client.delete(
        f"/usuarios/{operador_creado['usuario'].id}", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["activo"] is False


def test_no_se_puede_desactivar_al_unico_admin_activo(client, admin_creado):
    token = _token_de(client, "admin@ejixhole.com", "secreta123")
    response = client.delete(
        f"/usuarios/{admin_creado['usuario'].id}", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 409


def test_se_puede_desactivar_un_admin_si_hay_otro_activo(client, admin_creado, db_session):
    from app.core.security import hash_password

    otro_admin = Usuario(
        nombre="Otro Admin",
        email="otro-admin@ejixhole.com",
        password_hash=hash_password("clave789"),
        rol_id=admin_creado["rol"].id,
    )
    db_session.add(otro_admin)
    db_session.commit()
    db_session.refresh(otro_admin)

    token = _token_de(client, "admin@ejixhole.com", "secreta123")
    response = client.delete(
        f"/usuarios/{otro_admin.id}", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["activo"] is False


def test_desactivar_usuario_inexistente_404(client, admin_creado):
    token = _token_de(client, "admin@ejixhole.com", "secreta123")
    response = client.delete("/usuarios/9999", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404


def test_desactivar_usuario_ya_desactivado_rechazado(client, admin_creado, operador_creado):
    token = _token_de(client, "admin@ejixhole.com", "secreta123")
    headers = {"Authorization": f"Bearer {token}"}

    client.delete(f"/usuarios/{operador_creado['usuario'].id}", headers=headers)
    response = client.delete(f"/usuarios/{operador_creado['usuario'].id}", headers=headers)

    assert response.status_code == 400
