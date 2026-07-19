from fastapi import HTTPException, Request

from app.core.config import settings
from app.core.rate_limiter import RateLimiter

lecturas = RateLimiter(120, 300)
desafios = RateLimiter(30, 300)
envios = RateLimiter(30, 600)


def _ip(request: Request) -> str:
    valores = [item.strip() for item in request.headers.get("x-forwarded-for", "").split(",") if item.strip()]
    if valores:
        return valores[-1]
    return request.client.host if request.client else "unknown"


def _aplicar(request: Request, limiter: RateLimiter, mensaje: str) -> None:
    if settings.ENVIRONMENT == "test":
        return
    clave = _ip(request)
    if limiter.permitido(clave):
        return
    espera = max(1, int(limiter.segundos_para_reintentar(clave)))
    raise HTTPException(
        status_code=429,
        detail=mensaje,
        headers={"Retry-After": str(espera)},
    )


def limitar_lectura(request: Request) -> None:
    _aplicar(request, lecturas, "Demasiadas consultas públicas.")


def limitar_desafio(request: Request) -> None:
    _aplicar(request, desafios, "Demasiadas solicitudes de formulario.")


def limitar_envio(request: Request) -> None:
    _aplicar(request, envios, "Demasiados envíos públicos.")
