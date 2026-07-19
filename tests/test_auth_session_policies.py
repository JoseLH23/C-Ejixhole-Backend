from datetime import timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import hash_password
from app.models.auth_session import AuthSession
from app.models.usuario import Rol, Usuario
from app.repositories import auth_session_repository as repository_module
from app.repositories.auth_session_repository import AuthSessionRepository
from app.services.auth_service import AuthService
from app.services.usuario_service import UsuarioService


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", future=True)
    Rol.__table__.create(engine)
    Usuario.__table__.create(engine)
    AuthSession.__table__.create(engine)
    session = sessionmaker(bind=engine, future=True)()
    rol = Rol(nombre="operador", descripcion="operador")
    session.add(rol)
    session.flush()
    user = Usuario(
        nombre="Prueba",
        email="policy@example.test",
        password_hash=hash_password("initial-test-value"),
        rol_id=rol.id,
        activo=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    try:
        yield session, user
    finally:
        session.close()
        engine.dispose()


def test_session_limit_revokes_oldest(db, monkeypatch):
    session, user = db
    monkeypatch.setattr(repository_module, "AUTH_SESSION_MAX_PER_USER", 2)
    service = AuthService(session)

    first = service.crear_sesion(user.email, "initial-test-value")
    second = service.crear_sesion(user.email, "initial-test-value")
    third = service.crear_sesion(user.email, "initial-test-value")

    repository = AuthSessionRepository(session)
    assert repository.obtener_vigente(first.jti) is None
    assert repository.obtener_vigente(second.jti) is not None
    assert repository.obtener_vigente(third.jti) is not None


def test_touch_uses_configured_interval(db, monkeypatch):
    session, user = db
    monkeypatch.setattr(repository_module, "AUTH_SESSION_TOUCH_MINUTES", 10)
    result = AuthService(session).crear_sesion(user.email, "initial-test-value")
    repository = AuthSessionRepository(session)
    active = repository.obtener_vigente(result.jti)
    initial = active.last_seen_at
    if initial.tzinfo is None:
        initial = initial.replace(tzinfo=timezone.utc)

    repository.tocar(active, ahora=initial + timedelta(minutes=5))
    unchanged = active.last_seen_at
    if unchanged.tzinfo is None:
        unchanged = unchanged.replace(tzinfo=timezone.utc)
    assert unchanged == initial

    repository.tocar(active, ahora=initial + timedelta(minutes=11))
    updated = active.last_seen_at
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=timezone.utc)
    assert updated == initial + timedelta(minutes=11)


def test_sensitive_change_rolls_back_when_revocation_fails(db, monkeypatch):
    session, user = db
    result = AuthService(session).crear_sesion(user.email, "initial-test-value")
    original_hash = user.password_hash
    service = UsuarioService(session)

    def fail(*args, **kwargs):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(service.sessions, "revocar_usuario", fail)
    with pytest.raises(RuntimeError):
        service.restablecer_password(user.id, "replacement-test-value")

    session.expire_all()
    reloaded = session.query(Usuario).filter(Usuario.id == user.id).one()
    assert reloaded.password_hash == original_hash
    assert AuthSessionRepository(session).obtener_vigente(result.jti) is not None
