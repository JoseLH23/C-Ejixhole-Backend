"""
Dependencias de autenticación. Ya aplicadas a Clientes, Reservaciones,
Pagos, Caja, Servicios, Reportes, Usuarios y Dashboard — solo
`publico_routes.py` es intencionalmente público (portal de
reservaciones). Para proteger una ruta nueva:

    router = APIRouter(..., dependencies=[Depends(get_current_user)])

o para restringir por rol:

    @router.post(..., dependencies=[Depends(require_roles("admin"))])
"""
from hmac import compare_digest

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_access_token
from app.database import get_db
from app.models.usuario import Usuario

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)
_METODOS_SEGUROS = {"GET", "HEAD", "OPTIONS"}


def _credenciales_invalidas() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales inválidas o sesión expirada.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _token_de_request(request: Request, bearer_token: str | None) -> str:
    # Bearer se conserva para scripts internos y compatibilidad de API,
    # pero el panel web ya no lo guarda ni lo expone a JavaScript.
    if bearer_token:
        return bearer_token

    cookie_token = request.cookies.get(settings.AUTH_COOKIE_NAME)
    if not cookie_token:
        raise _credenciales_invalidas()

    # Las cookies viajan automáticamente: toda operación que modifica datos
    # exige double-submit CSRF. GET/HEAD/OPTIONS siguen siendo de solo lectura.
    if request.method.upper() not in _METODOS_SEGUROS:
        csrf_cookie = request.cookies.get(settings.CSRF_COOKIE_NAME)
        csrf_header = request.headers.get("X-CSRF-Token")
        if (
            not csrf_cookie
            or not csrf_header
            or not compare_digest(csrf_cookie, csrf_header)
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Validación CSRF inválida o ausente.",
            )

    return cookie_token


def get_current_user(
    request: Request,
    token_bearer: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    credentials_exception = _credenciales_invalidas()
    token = _token_de_request(request, token_bearer)

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
