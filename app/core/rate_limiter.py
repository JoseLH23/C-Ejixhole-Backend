"""
Rate limiter real, en memoria, solo librería estándar — sin agregar
ninguna dependencia nueva (slowapi, etc.).

AL-02/AL-03 (auditoría de seguridad 13/jul/2026): POST /auth/login no
tenía ninguna defensa contra fuerza bruta, y las rutas públicas
(/publico/*) no tenían ningún límite contra abuso automatizado (bots
creando reservaciones falsas, consultando disponibilidad en bucle).

Ventana deslizante simple, por IP (a diferencia del rate limiter de
MH-Core, que es global de un solo proceso para un solo usuario — este
backend sí tiene múltiples clientes reales por IP, así que limitar por
IP es lo correcto aquí).

Limitación real y documentada: en memoria de un solo proceso — si
Render llega a correr varios workers, cada uno tendría su propio
contador (no comparten estado). Suficiente para el nivel de tráfico
actual; si eso cambia, esto se movería a Redis.
"""
import threading
import time
from collections import defaultdict

from fastapi import HTTPException, Request


class RateLimiter:
    def __init__(self, max_llamadas: int, ventana_segundos: int):
        self.max_llamadas = max_llamadas
        self.ventana_segundos = ventana_segundos
        self._llamadas: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def permitido(self, clave: str) -> bool:
        ahora = time.time()
        with self._lock:
            recientes = [t for t in self._llamadas[clave] if ahora - t < self.ventana_segundos]
            if len(recientes) >= self.max_llamadas:
                self._llamadas[clave] = recientes
                return False
            recientes.append(ahora)
            self._llamadas[clave] = recientes
            return True

    def segundos_para_reintentar(self, clave: str) -> float:
        with self._lock:
            llamadas = self._llamadas.get(clave, [])
            if not llamadas:
                return 0.0
            return max(0.0, self.ventana_segundos - (time.time() - min(llamadas)))


def _ip_del_cliente(request: Request) -> str:
    # Render/Vercel suelen poner la IP real en X-Forwarded-For.
    adelante = request.headers.get("x-forwarded-for")
    if adelante:
        return adelante.split(",")[0].strip()
    return request.client.host if request.client else "desconocido"


# 5 intentos de login por IP cada 5 minutos — generoso para una
# persona real que se equivoca, suficiente para frenar fuerza bruta.
limitador_login = RateLimiter(max_llamadas=5, ventana_segundos=300)

# 20 solicitudes públicas (cotizar/reservar) por IP cada 5 minutos.
limitador_publico = RateLimiter(max_llamadas=20, ventana_segundos=300)


def limitar_login(request: Request) -> None:
    ip = _ip_del_cliente(request)
    if not limitador_login.permitido(ip):
        espera = limitador_login.segundos_para_reintentar(ip)
        raise HTTPException(
            status_code=429,
            detail=f"Demasiados intentos de inicio de sesión. Intenta de nuevo en ~{espera:.0f} segundos.",
        )


def limitar_publico(request: Request) -> None:
    ip = _ip_del_cliente(request)
    if not limitador_publico.permitido(ip):
        espera = limitador_publico.segundos_para_reintentar(ip)
        raise HTTPException(
            status_code=429,
            detail=f"Demasiadas solicitudes. Intenta de nuevo en ~{espera:.0f} segundos.",
        )
