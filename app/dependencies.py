"""
Dependencias de autenticación. Listas para usar, pero todavía NO
aplicadas a ninguna ruta existente (Clientes, Reservaciones, Pagos
siguen sin protección, tal como se acordó). Para proteger una ruta:

    router = APIRouter(..., dependencies=[Depends(get_current_user)])

o para restringir por rol:

    @router.post(..., dependencies=[Depends(require_roles("admin"))])
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database import get_db
from app.models.usuario import Usuario

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> Usuario:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales inválidas o token expirado.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        email = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    if usuario is None or not usuario.activo:
        raise credentials_exception
    return usuario


def require_roles(*roles_permitidos: str):
    def checker(usuario: Usuario = Depends(get_current_user)) -> Usuario:
        if usuario.rol.nombre not in roles_permitidos:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Este rol ({usuario.rol.nombre}) no tiene permiso para esta acción.",
            )
        return usuario

    return checker
