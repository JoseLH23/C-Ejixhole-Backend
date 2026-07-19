from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from jose.exceptions import JWTClaimsError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.security import create_access_token, decode_access_token, hash_password
from app.core.session_config import JWT_AUDIENCE, JWT_ISSUER
from app.database import Base, get_db
from app.main import app
from app.models.auth_session import AuthSession
from app.models.usuario import Rol, Usuario
from app.repositories.auth_session_repository import AuthSessionRepository
from app.services.auth_service import AuthService
from app.services.usuario_service import UsuarioService


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", future=True)
    Rol.__table__.create(engine)
    Usuario.__table__.create(engine)
    AuthSession.__table__.create(engine)
    Session = sessionmaker(bind=engine, future=True)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def crear_usuario(db, *, email="operador@example.test", rol="operador") -> Usuario:
    rol_model = Rol(nombre=rol, descripcion=rol)
    db.add(rol_model)
    db.flush()
    usuario = Usuario(
        nombre="Usuario de prueba",
        email=email,
        password_hash=hash_password("password-test-value"),
        rol_id=rol_model.id,
        activo=True,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def test_login_persiste_sesion_y_emite_claims_empresariales(db):
    usuario = crear_usuario(db)
    result = AuthService(db).crear_sesion(usuario.email, "password-test-value")
    payload = decode_access_token(result.access_token)
    assert payload["sub"] == usuario.email
    assert payload["rol"] == "operador"
    assert payload["jti"] == result.jti
    assert payload["iss"] == JWT_ISSUER
    assert payload["aud"] == JWT_AUDIENCE
    assert AuthSessionRepository(db).obtener_vigente(result.jti).id == result.session_id


def test_sesion_revocada_deja_de_ser_vigente(db):
    usuario = crear_usuario(db)
    result = AuthService(db).crear_sesion(usuario.email, "password-test-value")
    AuthService(db).revocar_sesion(result.session_id, reason="logout")
    assert AuthSessionRepository(db).obtener_vigente(result.jti) is None


def test_desactivar_usuario_revoca_todas_sus_sesiones(db):
    usuario = crear_usuario(db)
    result = AuthService(db).crear_sesion(usuario.email, "password-test-value")
    UsuarioService(db).desactivar(usuario.id)
    assert AuthSessionRepository(db).obtener_vigente(result.jti) is None


def test_restablacer_password_revoca_sesiones_previas(db):
    usuario = crear_usuario(db)
    result = AuthService(db).crear_sesion(usuario.email, "password-test-value")
    UsuarioService(db).restablecer_password(usuario.id, "new-password-test-value")
    assert AuthSessionRepository(db).obtener_vigente(result.jti) is None


def test_bearer_directo_sigue_funcionando_en_sqlite_de_pruebas():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Session = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)
    session = Session()
    rol = Rol(nombre="admin", descripcion="admin")
    session.add(rol)
    session.flush()
    usuario = Usuario(
        nombre="Admin fixture",
        email="fixture@example.test",
        password_hash="no-usado",
        rol_id=rol.id,
        activo=True,
    )
    session.add(usuario)
    session.commit()

    def override_db():
        db_local = Session()
        try:
            yield db_local
        finally:
            db_local.close()

    app.dependency_overrides[get_db] = override_db
    try:
        token = create_access_token(subject=usuario.email, rol="admin")
        response = TestClient(app).get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json()["email"] == usuario.email
    finally:
        app.dependency_overrides.clear()
        session.close()
        engine.dispose()


def test_decode_rechaza_audiencia_distinta():
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": "usuario@example.test",
            "rol": "admin",
            "jti": "00000000-0000-4000-8000-000000000001",
            "iss": JWT_ISSUER,
            "aud": "audiencia-no-autorizada",
            "iat": now,
            "nbf": now,
            "exp": now + timedelta(minutes=5),
        },
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    with pytest.raises(JWTClaimsError):
        decode_access_token(token)
