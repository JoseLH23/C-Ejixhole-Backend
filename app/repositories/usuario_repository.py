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

    def desactivar(self, usuario: Usuario) -> Usuario:
        usuario.activo = False
        self.db.commit()
        self.db.refresh(usuario)
        return usuario

    def reactivar(self, usuario: Usuario) -> Usuario:
        usuario.activo = True
        self.db.commit()
        self.db.refresh(usuario)
        return usuario

    def actualizar_rol(self, usuario: Usuario, rol_id: int) -> Usuario:
        usuario.rol_id = rol_id
        self.db.commit()
        self.db.refresh(usuario)
        return usuario

    def actualizar_password(self, usuario: Usuario, password_hash: str) -> Usuario:
        usuario.password_hash = password_hash
        self.db.commit()
        self.db.refresh(usuario)
        return usuario
