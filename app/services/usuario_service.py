"""
Service de Usuarios (listar). La creación (`crear_usuario`) sigue
viviendo en AuthService — no se duplica aquí, se reutiliza tal cual.
Este service solo agrega la operación de lectura que faltaba.
"""
from sqlalchemy.orm import Session

from app.models.usuario import Usuario
from app.repositories.usuario_repository import UsuarioRepository


class UsuarioService:
    def __init__(self, db: Session):
        self.repo = UsuarioRepository(db)

    def listar(self, limit: int = 100, offset: int = 0) -> list[Usuario]:
        return self.repo.listar(limit=limit, offset=offset)
