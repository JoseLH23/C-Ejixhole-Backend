"""Rutas de autenticación y sesión administrativa."""
from secrets import token_urlsafe

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rate_limiter import limitar_login
from app.database import get_db
from app.dependencies import get_current_user, require_roles
from app.models.usuario import Usuario
from app.schemas.auth import LoginRequest, Token, UsuarioCreate, UsuarioOut
from app.services.audit_service import AuditService, snapshot
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])
_USUARIO_CAMPOS = ("id", "nombre", "email", "rol_id", "activo", "fecha_creacion", "fecha_actualizacion")


def _opciones_cookie(*, httponly: bool) -> dict:
    return {
        "httponly": httponly,
        "secure": settings.AUTH_COOKIE_SECURE,
        "samesite": settings.AUTH_COOKIE_SAMESITE,
        "path": "/",
        "domain": settings.AUTH_COOKIE_DOMAIN,
    }


def _guardar_sesion(response: Response, token: str) -> None:
    max_age = settings.JWT_EXPIRE_MINUTES * 60
    csrf_token = token_urlsafe(32)
    response.set_cookie(key=settings.AUTH_COOKIE_NAME, value=token, max_age=max_age, **_opciones_cookie(httponly=True))
    response.set_cookie(key=settings.CSRF_COOKIE_NAME, value=csrf_token, max_age=max_age, **_opciones_cookie(httponly=False))
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


def _borrar_sesion(response: Response) -> None:
    response.delete_cookie(key=settings.AUTH_COOKIE_NAME, **_opciones_cookie(httponly=True))
    response.delete_cookie(key=settings.CSRF_COOKIE_NAME, **_opciones_cookie(httponly=False))
    response.headers["Cache-Control"] = "no-store"


@router.post("/login", response_model=Token, dependencies=[Depends(limitar_login)])
def login(data: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    result = AuthService(db).crear_sesion(data.email, data.password)
    _guardar_sesion(response, result.access_token)
    AuditService(db).registrar(
        actor=result.usuario,
        accion="auth.login",
        entidad_tipo="auth_session",
        entidad_id=result.session_id,
        request=request,
        despues={"expires_at": result.expires_at, "estado": "activa"},
    )
    return Token(access_token=result.access_token, session_managed=True)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    session_id = getattr(request.state, "auth_session_id", None)
    if session_id is not None:
        AuthService(db).revocar_sesion(session_id, reason="logout")
        AuditService(db).registrar(
            actor=usuario,
            accion="auth.logout",
            entidad_tipo="auth_session",
            entidad_id=session_id,
            request=request,
            despues={"estado": "revocada"},
        )
    _borrar_sesion(response)
    return None


@router.get("/me", response_model=UsuarioOut)
def obtener_perfil_actual(response: Response, usuario: Usuario = Depends(get_current_user)):
    response.headers["Cache-Control"] = "no-store"
    return usuario


@router.post("/usuarios", response_model=UsuarioOut)
def crear_usuario(
    data: UsuarioCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: Usuario = Depends(require_roles("admin")),
):
    usuario = AuthService(db).crear_usuario(data.nombre, data.email, data.password, data.rol_id)
    AuditService(db).registrar(
        actor=actor,
        accion="usuario.creado",
        entidad_tipo="usuario",
        entidad_id=usuario.id,
        request=request,
        despues=snapshot(usuario, _USUARIO_CAMPOS),
    )
    return usuario
