"""
Rutas de Auth. Activadas en app/main.py.

POST /auth/login    -> devuelve un JWT (Bearer) válido por
                        JWT_EXPIRE_MINUTES (ver app/core/config.py).
POST /auth/usuarios -> solo un usuario con rol "admin" puede crear
                        usuarios nuevos.

Para crear el PRIMER admin del sistema (cuando la tabla usuarios está
vacía y por lo tanto nadie puede pasar require_roles("admin")), ver
docs/modulos/auth.md.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.schemas.auth import LoginRequest, Token, UsuarioCreate, UsuarioOut
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=Token)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    service = AuthService(db)
    token = service.autenticar(data.email, data.password)
    return Token(access_token=token)


@router.post("/usuarios", response_model=UsuarioOut, dependencies=[Depends(require_roles("admin"))])
def crear_usuario(data: UsuarioCreate, db: Session = Depends(get_db)):
    """Solo un admin puede dar de alta nuevos usuarios del sistema."""
    service = AuthService(db)
    return service.crear_usuario(data.nombre, data.email, data.password, data.rol_id)
