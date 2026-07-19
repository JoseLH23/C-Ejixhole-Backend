from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models.usuario import Usuario
from app.repositories.auth_session_repository import AuthSessionRepository
from app.repositories.usuario_repository import UsuarioRepository


@dataclass(frozen=True)
class AuthenticatedSession:
    access_token: str
    usuario: Usuario
    session_id: int
    jti: str
    expires_at: datetime


class AuthService:
    def __init__(self, db: Session):
        self.repo = UsuarioRepository(db)
        self.sessions = AuthSessionRepository(db)

    def _validar_usuario(self, email: str, password: str) -> Usuario:
        usuario = self.repo.obtener_por_email(email)
        if not usuario or not verify_password(password, usuario.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email o contraseña incorrectos.",
            )
        if not usuario.activo:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Este usuario está desactivado.",
            )
        return usuario

    def crear_sesion(self, email: str, password: str) -> AuthenticatedSession:
        usuario = self._validar_usuario(email, password)
        issued_at = datetime.now(timezone.utc)
        expires_at = issued_at + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
        jti = str(uuid4())
        session = self.sessions.crear(
            jti=jti,
            usuario_id=usuario.id,
            issued_at=issued_at,
            expires_at=expires_at,
        )
        token = create_access_token(
            subject=usuario.email,
            rol=usuario.rol.nombre,
            jti=jti,
            issued_at=issued_at,
            expires_at=expires_at,
        )
        return AuthenticatedSession(
            access_token=token,
            usuario=usuario,
            session_id=session.id,
            jti=jti,
            expires_at=expires_at,
        )

    def autenticar(self, email: str, password: str) -> str:
        """Compatibilidad para consumidores existentes."""
        return self.crear_sesion(email, password).access_token

    def revocar_sesion(self, session_id: int, *, reason: str = "logout"):
        return self.sessions.revocar(session_id, reason=reason)

    def revocar_sesiones_usuario(self, usuario_id: int, *, reason: str) -> int:
        return self.sessions.revocar_usuario(usuario_id, reason=reason)

    def crear_usuario(self, nombre: str, email: str, password: str, rol_id: int) -> Usuario:
        if self.repo.obtener_por_email(email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe un usuario con ese email.",
            )
        usuario = Usuario(
            nombre=nombre,
            email=email,
            password_hash=hash_password(password),
            rol_id=rol_id,
        )
        return self.repo.crear(usuario)
