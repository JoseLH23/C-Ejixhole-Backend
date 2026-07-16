"""Pruebas de la sesión web mediante cookies HttpOnly y protección CSRF."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.security import hash_password
from app.database import Base, get_db
from app.main import app
from app.models.usuario import Rol, Usuario


@pytest.fixture()
def entorno_cookie():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    session = Session()
    rol = Rol(nombre="admin", descripcion="Administrador")
    session.add(rol)
    session.commit()
    session.refresh(rol)
    rol_id = rol.id
    session.add(
        Usuario(
            nombre="Admin Cookie",
            email="cookie@ejixhole.com",
            password_hash=hash_password("secreta123"),
            rol_id=rol_id,
            activo=True,
        )
    )
    session.commit()
    session.close()

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        yield client, rol_id
    finally:
        client.close()
        app.dependency_overrides.clear()


def _login(client: TestClient):
    return client.post(
        "/auth/login",
        json={"email": "cookie@ejixhole.com", "password": "secreta123"},
    )


def test_login_crea_cookie_httponly_y_cookie_csrf(entorno_cookie):
    client, _ = entorno_cookie
    response = _login(client)

    assert response.status_code == 200
    cookies = response.headers.get_list("set-cookie")
    sesion = next(c for c in cookies if c.startswith(f"{settings.AUTH_COOKIE_NAME}="))
    csrf = next(c for c in cookies if c.startswith(f"{settings.CSRF_COOKIE_NAME}="))

    assert "HttpOnly" in sesion
    assert "SameSite=lax" in sesion
    assert "HttpOnly" not in csrf
    assert client.cookies.get(settings.AUTH_COOKIE_NAME)
    assert client.cookies.get(settings.CSRF_COOKIE_NAME)


def test_cookie_autentica_sin_authorization_header(entorno_cookie):
    client, _ = entorno_cookie
    _login(client)

    response = client.get("/auth/me")

    assert response.status_code == 200
    assert response.json()["email"] == "cookie@ejixhole.com"
    assert response.headers["Cache-Control"] == "no-store"


def test_operacion_con_cookie_exige_csrf(entorno_cookie):
    client, rol_id = entorno_cookie
    _login(client)

    payload = {
        "nombre": "Nuevo protegido",
        "email": "nuevo-cookie@ejixhole.com",
        "password": "clave789",
        "rol_id": rol_id,
    }

    sin_csrf = client.post("/auth/usuarios", json=payload)
    assert sin_csrf.status_code == 403
    assert "CSRF" in sin_csrf.json()["detail"]

    csrf = client.cookies.get(settings.CSRF_COOKIE_NAME)
    con_csrf = client.post(
        "/auth/usuarios",
        json=payload,
        headers={"X-CSRF-Token": csrf},
    )
    assert con_csrf.status_code == 200


def test_logout_borra_la_sesion(entorno_cookie):
    client, _ = entorno_cookie
    _login(client)
    csrf = client.cookies.get(settings.CSRF_COOKIE_NAME)

    response = client.post("/auth/logout", headers={"X-CSRF-Token": csrf})

    assert response.status_code == 204
    assert client.cookies.get(settings.AUTH_COOKIE_NAME) is None
    assert client.cookies.get(settings.CSRF_COOKIE_NAME) is None
    assert client.get("/auth/me").status_code == 401
