"""
Rutas de Usuarios (listar, listar roles, desactivar). Solo admin —
mismo criterio que POST /auth/usuarios (crear), que también es
admin-only.

La creación de usuarios se queda en /auth/usuarios (auth_routes.py) a
propósito, no se mueve aquí — evita romper al frontend que ya la
consume ahí y evita duplicar esa lógica en dos lugares.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.schemas.auth import RolOut, UsuarioOut
from app.services.usuario_service import UsuarioService

router = APIRouter(
    prefix="/usuarios",
    tags=["Usuarios"],
    dependencies=[Depends(require_roles("admin"))],
)


@router.get("", response_model=list[UsuarioOut])
def listar_usuarios(limit: int = 100, offset: int = 0, db: Session = Depends(get_db)):
    service = UsuarioService(db)
    return service.listar(limit=limit, offset=offset)


@router.get("/roles", response_model=list[RolOut])
def listar_roles(db: Session = Depends(get_db)):
    """Para poblar el selector de rol real al crear un usuario — no
    se hardcodea la lista de roles en el frontend."""
    service = UsuarioService(db)
    return service.listar_roles()


@router.delete("/{usuario_id}", response_model=UsuarioOut)
def desactivar_usuario(usuario_id: int, db: Session = Depends(get_db)):
    """Soft delete: marca activo=False. Nunca deja el sistema sin
    ningún admin activo (ver UsuarioService.desactivar)."""
    service = UsuarioService(db)
    return service.desactivar(usuario_id)
