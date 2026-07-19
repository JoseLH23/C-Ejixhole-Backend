"""
Service de Usuarios (listar, roles, estado, rol y contraseña).
Los cambios sensibles invalidan sus sesiones en la misma transacción.
"""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.usuario import Rol, Usuario
from app.repositories.auth_session_repository import AuthSessionRepository
from app.repositories.usuario_repository import UsuarioRepository


class UsuarioService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = UsuarioRepository(db)
        self.sessions = AuthSessionRepository(db)

    def obtener(self, usuario_id: int) -> Usuario:
        usuario = self.repo.obtener_por_id(usuario_id)
        if not usuario:
            raise HTTPException(status_code=404, detail="Usuario no encontrado.")
        return usuario

    def listar(self, limit: int = 100, offset: int = 0) -> list[Usuario]:
        return self.repo.listar(limit=limit, offset=offset)

    def listar_roles(self) -> list[Rol]:
        return self.repo.listar_roles()

    def _confirmar_cambio_sensible(self, usuario: Usuario) -> Usuario:
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        self.db.refresh(usuario)
        return usuario

    def desactivar(self, usuario_id: int) -> Usuario:
        usuario = self.obtener(usuario_id)
        if not usuario.activo:
            raise HTTPException(status_code=400, detail="Este usuario ya está desactivado.")
        if usuario.rol.nombre == "admin" and self.repo.contar_admins_activos() <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No se puede desactivar: es el único administrador activo del sistema.",
            )
        try:
            self.repo.desactivar(usuario, commit=False)
            self.sessions.revocar_usuario(usuario.id, reason="user_deactivated", commit=False)
        except Exception:
            self.db.rollback()
            raise
        return self._confirmar_cambio_sensible(usuario)

    def reactivar(self, usuario_id: int) -> Usuario:
        usuario = self.obtener(usuario_id)
        if usuario.activo:
            raise HTTPException(status_code=400, detail="Este usuario ya está activo.")
        return self.repo.reactivar(usuario)

    def actualizar_rol(self, usuario_id: int, rol_id: int) -> Usuario:
        usuario = self.obtener(usuario_id)
        nuevo_rol = self.repo.obtener_rol_por_id(rol_id)
        if not nuevo_rol:
            raise HTTPException(status_code=404, detail="Rol no encontrado.")
        cambio = usuario.rol_id != rol_id
        if not cambio:
            return usuario
        if (
            usuario.rol.nombre == "admin"
            and usuario.activo
            and self.repo.contar_admins_activos() <= 1
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No se puede cambiar el rol: es el único administrador activo del sistema.",
            )
        try:
            self.repo.actualizar_rol(usuario, rol_id, commit=False)
            self.sessions.revocar_usuario(usuario.id, reason="role_changed", commit=False)
        except Exception:
            self.db.rollback()
            raise
        return self._confirmar_cambio_sensible(usuario)

    def restablecer_password(self, usuario_id: int, nueva_password: str) -> Usuario:
        usuario = self.obtener(usuario_id)
        try:
            self.repo.actualizar_password(
                usuario,
                hash_password(nueva_password),
                commit=False,
            )
            self.sessions.revocar_usuario(usuario.id, reason="password_reset", commit=False)
        except Exception:
            self.db.rollback()
            raise
        return self._confirmar_cambio_sensible(usuario)
