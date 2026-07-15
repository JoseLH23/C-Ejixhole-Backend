"""
Rutas de Usuarios (listar, listar roles, desactivar, editar rol). Solo
admin — mismo criterio que POST /auth/usuarios (crear), que también es
admin-only.

La creación de usuarios se queda en /auth/usuarios (auth_routes.py) a
propósito, no se mueve aquí — evita romper al frontend que ya la
consume ahí y evita duplicar esa lógica en dos lugares.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.schemas.auth import RolOut, UsuarioOut, UsuarioRolUpdate
from app.services.usuario_service import UsuarioService

router = APIRouter(
    prefix="/usuarios",
    tags=["Usuarios"],
    dependencies=[Depends(require_roles("admin"))],
)


@router.get("", response_model=list[UsuarioOut])
def listar_usuarios(limit: int = Query(100, ge=1, le=200), offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
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


@router.patch("/{usuario_id}/rol", response_model=UsuarioOut)
def actualizar_rol_usuario(usuario_id: int, data: UsuarioRolUpdate, db: Session = Depends(get_db)):
    """Cambia el rol de un usuario existente. Misma protección que
    desactivar: nunca deja el sistema sin ningún admin activo (ver
    UsuarioService.actualizar_rol)."""
    service = UsuarioService(db)
    return service.actualizar_rol(usuario_id, data.rol_id)
