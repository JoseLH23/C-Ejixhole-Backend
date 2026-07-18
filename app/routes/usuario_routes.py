"""Rutas de administración de usuarios, exclusivas para rol admin."""
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.models.usuario import Usuario
from app.schemas.auth import RolOut, UsuarioOut, UsuarioPasswordReset, UsuarioRolUpdate
from app.services.audit_service import AuditService, snapshot
from app.services.usuario_service import UsuarioService

router = APIRouter(
    prefix="/usuarios",
    tags=["Usuarios"],
    dependencies=[Depends(require_roles("admin"))],
)

_USUARIO_CAMPOS = ("id", "nombre", "email", "rol_id", "activo", "fecha_creacion", "fecha_actualizacion")


@router.get("", response_model=list[UsuarioOut])
def listar_usuarios(
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    return UsuarioService(db).listar(limit=limit, offset=offset)


@router.get("/roles", response_model=list[RolOut])
def listar_roles(db: Session = Depends(get_db)):
    return UsuarioService(db).listar_roles()


@router.delete("/{usuario_id}", response_model=UsuarioOut)
def desactivar_usuario(
    usuario_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: Usuario = Depends(require_roles("admin")),
):
    service = UsuarioService(db)
    antes = snapshot(service.obtener(usuario_id), _USUARIO_CAMPOS)
    usuario = service.desactivar(usuario_id)
    AuditService(db).registrar(
        actor=actor,
        accion="usuario.desactivado",
        entidad_tipo="usuario",
        entidad_id=usuario.id,
        request=request,
        antes=antes,
        despues=snapshot(usuario, _USUARIO_CAMPOS),
    )
    return usuario


@router.patch("/{usuario_id}/reactivar", response_model=UsuarioOut)
def reactivar_usuario(
    usuario_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: Usuario = Depends(require_roles("admin")),
):
    service = UsuarioService(db)
    antes = snapshot(service.obtener(usuario_id), _USUARIO_CAMPOS)
    usuario = service.reactivar(usuario_id)
    AuditService(db).registrar(
        actor=actor,
        accion="usuario.reactivado",
        entidad_tipo="usuario",
        entidad_id=usuario.id,
        request=request,
        antes=antes,
        despues=snapshot(usuario, _USUARIO_CAMPOS),
    )
    return usuario


@router.patch("/{usuario_id}/rol", response_model=UsuarioOut)
def actualizar_rol_usuario(
    usuario_id: int,
    data: UsuarioRolUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: Usuario = Depends(require_roles("admin")),
):
    service = UsuarioService(db)
    antes = snapshot(service.obtener(usuario_id), _USUARIO_CAMPOS)
    usuario = service.actualizar_rol(usuario_id, data.rol_id)
    AuditService(db).registrar(
        actor=actor,
        accion="usuario.rol_actualizado",
        entidad_tipo="usuario",
        entidad_id=usuario.id,
        request=request,
        antes=antes,
        despues=snapshot(usuario, _USUARIO_CAMPOS),
    )
    return usuario


@router.patch("/{usuario_id}/password", response_model=UsuarioOut)
def restablecer_password_usuario(
    usuario_id: int,
    data: UsuarioPasswordReset,
    request: Request,
    db: Session = Depends(get_db),
    actor: Usuario = Depends(require_roles("admin")),
):
    usuario = UsuarioService(db).restablecer_password(usuario_id, data.nueva_password)
    AuditService(db).registrar(
        actor=actor,
        accion="usuario.password_restablecido",
        entidad_tipo="usuario",
        entidad_id=usuario.id,
        request=request,
        contexto={"password_incluido": False},
    )
    return usuario
