import os


def _entero(nombre: str, default: int, minimo: int, maximo: int) -> int:
    valor = int(os.getenv(nombre, str(default)))
    if valor < minimo or valor > maximo:
        raise RuntimeError(f"{nombre} debe estar entre {minimo} y {maximo}")
    return valor


MODO_PROTECCION_PUBLICA = os.getenv("PUBLIC_ANTI_ABUSE_MODE", "monitor").strip().lower()
if MODO_PROTECCION_PUBLICA not in {"monitor", "enforce"}:
    raise RuntimeError("PUBLIC_ANTI_ABUSE_MODE debe ser monitor o enforce")

ESPERA_MINIMA_SEGUNDOS = _entero("PUBLIC_CHALLENGE_MIN_SECONDS", 3, 1, 30)
VIGENCIA_DESAFIO_SEGUNDOS = _entero("PUBLIC_CHALLENGE_TTL_SECONDS", 7200, 300, 86400)
LIMITE_IP_HORA = _entero("PUBLIC_IP_HOURLY_LIMIT", 6, 1, 200)
LIMITE_CONTACTO_DIA = _entero("PUBLIC_CONTACT_DAILY_LIMIT", 3, 1, 50)
LIMITE_CLIENTE_HORA = _entero("PUBLIC_CLIENT_HOURLY_LIMIT", 8, 1, 100)
