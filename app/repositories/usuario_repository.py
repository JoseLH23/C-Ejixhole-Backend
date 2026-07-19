from typing import Optional

from sqlalchemy.orm import Session

from app.models.usuario import Rol, Usuario


class UsuarioRepository:
    def __init__(self, db: Session):
        self.db = db

    def obtener_por_email(self, email: str) -> Optional[Usuario]:
        return self.db.query(Usuario).filter(Usuario.email == email).first()

    def obtener_por_id(self, usuario_id: int) -> Optional[Usuario]:
        return self.db.query(Usuario).filter(Usuario.id == usuario_id).first()

    def obtener_rol_por_id(self, rol_id: int) -> Optional[Rol]:
        return self.db.query(Rol).filter(Rol.id == rol_id).first()

    def crear(self, usuario: Usuario) -> Usuario:
        self.db.add(usuario)
        self.db.commit()
        self.db.refresh(usuario)
        return usuario

    def listar(self, limit: int = 100, offset: int = 0) -> list[Usuario]:
        return (
            self.db.query(Usuario)
            .order_by(Usuario.nombre)
            .offset(offset)
            .limit(limit)
            .all()
        )

    def listar_roles(self) -> list[Rol]:
        return self.db.query(Rol).order_by(Rol.nombre).all()

    def contar_admins_activos(self) -> int:
        return (
            self.db.query(Usuario)
            .join(Rol, Usuario.rol_id == Rol.id)
            .filter(Rol.nombre == "admin", Usuario.activo.is_(True))
            .count()
        )

    def _guardar(self, usuario: Usuario, *, commit: bool) -> Usuario:
        if commit:
            self.db.commit()
            self.db.refresh(usuario)
        else:
            self.db.flush()
        return usuario

    def desactivar(self, usuario: Usuario, *, commit: bool = True) -> Usuario:
        usuario.activo = False
        return self._guardar(usuario, commit=commit)

    def reactivar(self, usuario: Usuario, *, commit: bool = True) -> Usuario:
        usuario.activo = True
        return self._guardar(usuario, commit=commit)

    def actualizar_rol(self, usuario: Usuario, rol_id: int, *, commit: bool = True) -> Usuario:
        usuario.rol_id = rol_id
        return self._guardar(usuario, commit=commit)

    def actualizar_password(
        self,
        usuario: Usuario,
        password_hash: str,
        *,
        commit: bool = True,
    ) -> Usuario:
        usuario.password_hash = password_hash
        return self._guardar(usuario, commit=commit)
