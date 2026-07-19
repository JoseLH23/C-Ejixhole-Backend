import os


def _entero(nombre: str, default: int, minimo: int, maximo: int) -> int:
    valor = int(os.getenv(nombre, str(default)))
    if valor < minimo or valor > maximo:
        raise RuntimeError(f"{nombre} debe estar entre {minimo} y {maximo}")
    return valor


PUBLIC_ANTI_ABUSE_MODE = os.getenv("PUBLIC_ANTI_ABUSE_MODE", "monitor").strip().lower()
if PUBLIC_ANTI_ABUSE_MODE not in {"monitor", "enforce"}:
    raise RuntimeError("PUBLIC_ANTI_ABUSE_MODE debe ser monitor o enforce")

PUBLIC_CHALLENGE_MIN_SECONDS = _entero("PUBLIC_CHALLENGE_MIN_SECONDS", 3, 1, 30)
PUBLIC_CHALLENGE_TTL_SECONDS = _entero("PUBLIC_CHALLENGE_TTL_SECONDS", 7200, 300, 86400)
PUBLIC_IP_HOURLY_LIMIT = _entero("PUBLIC_IP_HOURLY_LIMIT", 10, 1, 200)
PUBLIC_CONTACT_DAILY_LIMIT = _entero("PUBLIC_CONTACT_DAILY_LIMIT", 5, 1, 50)
PUBLIC_CLIENT_HOURLY_LIMIT = _entero("PUBLIC_CLIENT_HOURLY_LIMIT", 8, 1, 100)
