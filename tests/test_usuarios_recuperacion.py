"""Pruebas de reactivación y restablecimiento de contraseña de usuarios."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password, verify_password
from app.database import Base, get_db
from app.main import app
from app.models.usuario import Rol, Usuario


@pytest.fixture()
def entorno_usuarios():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    rol_admin = Rol(nombre="admin", descripcion="Administrador")
    rol_operador = Rol(nombre="operador", descripcion="Operador")
    session.add_all([rol_admin, rol_operador])
    session.commit()
    session.refresh(rol_admin)
    session.refresh(rol_operador)

    admin = Usuario(
        nombre="Admin Test",
        email="admin-recuperacion@ejixhole.com",
        password_hash=hash_password("secreta123"),
        rol_id=rol_admin.id,
    )
    operador = Usuario(
        nombre="Operador Test",
        email="operador-recuperacion@ejixhole.com",
        password_hash=hash_password("clave456"),
        rol_id=rol_operador.id,
        activo=False,
    )
    operador_activo = Usuario(
        nombre="Operador Activo",
        email="operador-activo@ejixhole.com",
        password_hash=hash_password("clave789"),
        rol_id=rol_operador.id,
        activo=True,
    )
    session.add_all([admin, operador, operador_activo])
    session.commit()
    session.refresh(admin)
    session.refresh(operador)
    session.refresh(operador_activo)
    session.close()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    login = client.post(
        "/auth/login",
        json={"email": "admin-recuperacion@ejixhole.com", "password": "secreta123"},
    )
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    yield {
        "client": client,
        "headers": headers,
        "session_factory": TestingSessionLocal,
        "operador_id": operador.id,
        "operador_activo_id": operador_activo.id,
    }

    app.dependency_overrides.clear()
    engine.dispose()


def test_reactivar_usuario_permite_iniciar_sesion(entorno_usuarios):
    client = entorno_usuarios["client"]
    response = client.patch(
        f"/usuarios/{entorno_usuarios['operador_id']}/reactivar",
        headers=entorno_usuarios["headers"],
    )

    assert response.status_code == 200
    assert response.json()["activo"] is True

    login = client.post(
        "/auth/login",
        json={"email": "operador-recuperacion@ejixhole.com", "password": "clave456"},
    )
    assert login.status_code == 200


def test_reactivar_usuario_activo_rechazado(entorno_usuarios):
    response = entorno_usuarios["client"].patch(
        f"/usuarios/{entorno_usuarios['operador_activo_id']}/reactivar",
        headers=entorno_usuarios["headers"],
    )
    assert response.status_code == 400


def test_reactivar_usuario_inexistente_404(entorno_usuarios):
    response = entorno_usuarios["client"].patch(
        "/usuarios/9999/reactivar",
        headers=entorno_usuarios["headers"],
    )
    assert response.status_code == 404


def test_reactivar_requiere_admin(entorno_usuarios):
    client = entorno_usuarios["client"]
    login = client.post(
        "/auth/login",
        json={"email": "operador-activo@ejixhole.com", "password": "clave789"},
    )
    token = login.json()["access_token"]

    response = client.patch(
        f"/usuarios/{entorno_usuarios['operador_id']}/reactivar",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_restablecer_password_invalida_la_anterior(entorno_usuarios):
    client = entorno_usuarios["client"]
    usuario_id = entorno_usuarios["operador_activo_id"]

    response = client.patch(
        f"/usuarios/{usuario_id}/password",
        json={"nueva_password": "NuevaClave2026"},
        headers=entorno_usuarios["headers"],
    )

    assert response.status_code == 200
    assert "password" not in response.json()

    login_anterior = client.post(
        "/auth/login",
        json={"email": "operador-activo@ejixhole.com", "password": "clave789"},
    )
    assert login_anterior.status_code == 401

    login_nuevo = client.post(
        "/auth/login",
        json={"email": "operador-activo@ejixhole.com", "password": "NuevaClave2026"},
    )
    assert login_nuevo.status_code == 200

    session = entorno_usuarios["session_factory"]()
    try:
        usuario = session.get(Usuario, usuario_id)
        assert verify_password("NuevaClave2026", usuario.password_hash)
        assert usuario.password_hash != "NuevaClave2026"
    finally:
        session.close()


def test_restablecer_password_corta_rechazada(entorno_usuarios):
    response = entorno_usuarios["client"].patch(
        f"/usuarios/{entorno_usuarios['operador_activo_id']}/password",
        json={"nueva_password": "corta"},
        headers=entorno_usuarios["headers"],
    )
    assert response.status_code == 422


def test_restablecer_password_inexistente_404(entorno_usuarios):
    response = entorno_usuarios["client"].patch(
        "/usuarios/9999/password",
        json={"nueva_password": "NuevaClave2026"},
        headers=entorno_usuarios["headers"],
    )
    assert response.status_code == 404
