"""
Service de Usuarios (listar, listar roles, desactivar). La creación
(`crear_usuario`) sigue viviendo en AuthService — no se duplica aquí,
se reutiliza tal cual.
"""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.usuario import Rol, Usuario
from app.repositories.usuario_repository import UsuarioRepository


class UsuarioService:
    def __init__(self, db: Session):
        self.repo = UsuarioRepository(db)

    def listar(self, limit: int = 100, offset: int = 0) -> list[Usuario]:
        return self.repo.listar(limit=limit, offset=offset)

    def listar_roles(self) -> list[Rol]:
        return self.repo.listar_roles()

    def desactivar(self, usuario_id: int) -> Usuario:
        usuario = self.repo.obtener_por_id(usuario_id)
        if not usuario:
            raise HTTPException(status_code=404, detail="Usuario no encontrado.")

        if not usuario.activo:
            raise HTTPException(status_code=400, detail="Este usuario ya está desactivado.")

        # Regla de negocio real (pedida explícitamente en el plan del
        # proyecto): nunca te puedes quedar sin ningún admin activo,
        # o nadie podría volver a crear/desactivar usuarios.
        if usuario.rol.nombre == "admin" and self.repo.contar_admins_activos() <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No se puede desactivar: es el único administrador activo del sistema.",
            )

        return self.repo.desactivar(usuario)
