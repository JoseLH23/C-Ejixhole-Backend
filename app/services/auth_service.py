from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.models.usuario import Usuario
from app.repositories.usuario_repository import UsuarioRepository


class AuthService:
    def __init__(self, db: Session):
        self.repo = UsuarioRepository(db)

    def autenticar(self, email: str, password: str) -> str:
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
        return create_access_token(subject=usuario.email, rol=usuario.rol.nombre)

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
