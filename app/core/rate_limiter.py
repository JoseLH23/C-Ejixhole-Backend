"""
Protección de tasa en memoria para autenticación y portal público.

La lectura pública conserva una cuota amplia por IP. La creación de
reservaciones usa límites adaptativos independientes por IP y por
contacto: cada reincidencia aumenta temporalmente el bloqueo. La huella
del contacto es HMAC; correo y teléfono nunca se guardan en los
contadores.

Limitación conocida: el estado vive por proceso. Si la aplicación pasa
a múltiples workers, estos contadores deben migrarse a un almacén
compartido (por ejemplo, Redis).
"""
import hashlib
import hmac
import math
import threading
import time
from collections import defaultdict
from collections.abc import Callable

from fastapi import HTTPException, Request

from app.core.config import settings


Reloj = Callable[[], float]


class RateLimiter:
    """Ventana deslizante simple, segura entre hilos."""

    def __init__(
        self,
        max_llamadas: int,
        ventana_segundos: int,
        *,
        reloj: Reloj = time.time,
    ):
        self.max_llamadas = max_llamadas
        self.ventana_segundos = ventana_segundos
        self._reloj = reloj
        self._llamadas: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def permitido(self, clave: str) -> bool:
        ahora = self._reloj()
        with self._lock:
            recientes = [
                instante
                for instante in self._llamadas[clave]
                if ahora - instante < self.ventana_segundos
            ]
            if len(recientes) >= self.max_llamadas:
                self._llamadas[clave] = recientes
                return False
            recientes.append(ahora)
            self._llamadas[clave] = recientes
            return True

    def segundos_para_reintentar(self, clave: str) -> float:
        ahora = self._reloj()
        with self._lock:
            llamadas = [
                instante
                for instante in self._llamadas.get(clave, [])
                if ahora - instante < self.ventana_segundos
            ]
            if len(llamadas) < self.max_llamadas:
                return 0.0
            return max(0.0, self.ventana_segundos - (ahora - min(llamadas)))

    def reiniciar(self) -> None:
        with self._lock:
            self._llamadas.clear()


class AdaptiveRateLimiter:
    """Ventana deslizante con bloqueo exponencial para reincidencias."""

    def __init__(
        self,
        max_llamadas: int,
        ventana_segundos: int,
        penalizacion_inicial_segundos: int,
        penalizacion_maxima_segundos: int,
        *,
        reloj: Reloj = time.time,
    ):
        self.max_llamadas = max_llamadas
        self.ventana_segundos = ventana_segundos
        self.penalizacion_inicial_segundos = penalizacion_inicial_segundos
        self.penalizacion_maxima_segundos = penalizacion_maxima_segundos
        self._reloj = reloj
        self._llamadas: dict[str, list[float]] = defaultdict(list)
        self._bloqueado_hasta: dict[str, float] = {}
        self._infracciones: dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()

    def permitido(self, clave: str) -> bool:
        ahora = self._reloj()
        with self._lock:
            bloqueado_hasta = self._bloqueado_hasta.get(clave, 0.0)
            if bloqueado_hasta > ahora:
                return False

            recientes = [
                instante
                for instante in self._llamadas[clave]
                if ahora - instante < self.ventana_segundos
            ]
            if not recientes:
                self._infracciones.pop(clave, None)
                self._bloqueado_hasta.pop(clave, None)

            if len(recientes) >= self.max_llamadas:
                infracciones = self._infracciones[clave] + 1
                self._infracciones[clave] = infracciones
                penalizacion = min(
                    self.penalizacion_inicial_segundos * (2 ** (infracciones - 1)),
                    self.penalizacion_maxima_segundos,
                )
                self._bloqueado_hasta[clave] = ahora + penalizacion
                self._llamadas[clave] = recientes
                return False

            recientes.append(ahora)
            self._llamadas[clave] = recientes
            return True

    def segundos_para_reintentar(self, clave: str) -> float:
        ahora = self._reloj()
        with self._lock:
            bloqueo = max(0.0, self._bloqueado_hasta.get(clave, 0.0) - ahora)
            if bloqueo:
                return bloqueo

            llamadas = [
                instante
                for instante in self._llamadas.get(clave, [])
                if ahora - instante < self.ventana_segundos
            ]
            if len(llamadas) < self.max_llamadas:
                return 0.0
            return max(0.0, self.ventana_segundos - (ahora - min(llamadas)))

    def reiniciar(self) -> None:
        with self._lock:
            self._llamadas.clear()
            self._bloqueado_hasta.clear()
            self._infracciones.clear()


def _ip_del_cliente(request: Request) -> str:
    # Render/Vercel entregan la cadena de proxies en X-Forwarded-For.
    adelante = request.headers.get("x-forwarded-for")
    if adelante:
        return adelante.split(",")[0].strip()
    return request.client.host if request.client else "desconocido"


def huella_contacto(email: str, telefono: str) -> str:
    """Identificador estable sin conservar PII en memoria."""
    email_normalizado = email.strip().casefold()
    telefono_normalizado = "".join(caracter for caracter in telefono if caracter.isdigit())
    mensaje = f"{email_normalizado}|{telefono_normalizado}".encode("utf-8")
    return hmac.new(
        settings.JWT_SECRET_KEY.encode("utf-8"),
        mensaje,
        hashlib.sha256,
    ).hexdigest()


def exigir_limite(limitador, clave: str, detalle: str) -> None:
    if limitador.permitido(clave):
        return
    espera = max(1, math.ceil(limitador.segundos_para_reintentar(clave)))
    raise HTTPException(
        status_code=429,
        detail=detalle,
        headers={"Retry-After": str(espera)},
    )


# Autenticación: 5 intentos por IP cada 5 minutos.
limitador_login = RateLimiter(max_llamadas=5, ventana_segundos=300)

# Lecturas del catálogo, cotización y disponibilidad: cuota amplia.
limitador_publico = RateLimiter(max_llamadas=120, ventana_segundos=300)

# Escrituras: cuotas más estrictas y bloqueo progresivo.
limitador_reservas_ip = AdaptiveRateLimiter(
    max_llamadas=6,
    ventana_segundos=3600,
    penalizacion_inicial_segundos=900,
    penalizacion_maxima_segundos=14400,
)
limitador_reservas_contacto = AdaptiveRateLimiter(
    max_llamadas=3,
    ventana_segundos=86400,
    penalizacion_inicial_segundos=3600,
    penalizacion_maxima_segundos=86400,
)


def limitar_login(request: Request) -> None:
    exigir_limite(
        limitador_login,
        _ip_del_cliente(request),
        "Demasiados intentos de inicio de sesión. Intenta de nuevo más tarde.",
    )


def limitar_publico(request: Request) -> None:
    exigir_limite(
        limitador_publico,
        _ip_del_cliente(request),
        "Demasiadas consultas públicas. Intenta de nuevo más tarde.",
    )


def limitar_reservacion_publica(request: Request, email: str, telefono: str) -> None:
    exigir_limite(
        limitador_reservas_ip,
        _ip_del_cliente(request),
        "Demasiadas solicitudes de reservación desde esta conexión. Intenta de nuevo más tarde.",
    )
    exigir_limite(
        limitador_reservas_contacto,
        huella_contacto(email, telefono),
        "Demasiadas solicitudes para estos datos de contacto. Intenta de nuevo más tarde.",
    )


def reiniciar_limitadores() -> None:
    """Aísla pruebas y permite limpiar el estado del proceso."""
    limitador_login.reiniciar()
    limitador_publico.reiniciar()
    limitador_reservas_ip.reiniciar()
    limitador_reservas_contacto.reiniciar()
