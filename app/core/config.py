import os
from dotenv import load_dotenv

load_dotenv()


def _obtener_jwt_secret_obligatorio() -> str:
    """
    CR-01 (auditoría de seguridad, 13/jul/2026): antes esto tenía un
    default público y predecible ("change-this-in-production"). Si la
    variable de entorno faltaba, la app arrancaba igual con esa clave
    conocida — cualquiera podía firmar tokens válidos con rol admin.

    Ahora: sin JWT_SECRET_KEY real (32+ caracteres), la app NO arranca
    — falla rápido y con un mensaje claro, en vez de arrancar
    silenciosamente insegura.
    """
    clave = os.getenv("JWT_SECRET_KEY", "")
    if not clave or clave == "change-this-in-production":
        raise RuntimeError(
            "JWT_SECRET_KEY no está configurada (o sigue en el valor por defecto inseguro). "
            "Genera una real con: python -c \"import secrets; print(secrets.token_urlsafe(48))\" "
            "y ponla en tu .env / variables de entorno de Render antes de arrancar."
        )
    if len(clave) < 32:
        raise RuntimeError(
            f"JWT_SECRET_KEY es demasiado corta ({len(clave)} caracteres) — se requieren al menos 32."
        )
    return clave


def _env_bool(nombre: str, default: bool) -> bool:
    valor = os.getenv(nombre)
    if valor is None:
        return default
    return valor.strip().lower() in {"1", "true", "yes", "si", "sí", "on"}


def _cookie_samesite() -> str:
    valor = os.getenv("AUTH_COOKIE_SAMESITE", "lax").strip().lower()
    if valor not in {"lax", "strict", "none"}:
        raise RuntimeError("AUTH_COOKIE_SAMESITE debe ser lax, strict o none.")
    return valor


class Settings:
    PROJECT_NAME: str = "EjiXhole Experience OS"
    VERSION: str = "0.1.0"

    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://ejixhole_user:changeme@localhost:5432/ejixhole_db",
    )

    JWT_SECRET_KEY: str = _obtener_jwt_secret_obligatorio()
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

    # ME-02 (auditoría de seguridad 13/jul/2026): default seguro
    # "production" — si no se configura explícitamente, se asume el
    # entorno más restrictivo (docs ocultos), no el más expuesto.
    # Para ver /docs en desarrollo local: ENVIRONMENT=development en tu .env
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "production")

    # AL-06: la sesión administrativa vive en una cookie HttpOnly. En
    # producción se marca Secure; desarrollo y E2E usan HTTP local.
    AUTH_COOKIE_NAME: str = os.getenv("AUTH_COOKIE_NAME", "ejixhole_session")
    CSRF_COOKIE_NAME: str = os.getenv("CSRF_COOKIE_NAME", "ejixhole_csrf")
    AUTH_COOKIE_SECURE: bool = _env_bool(
        "AUTH_COOKIE_SECURE", ENVIRONMENT == "production"
    )
    AUTH_COOKIE_SAMESITE: str = _cookie_samesite()
    AUTH_COOKIE_DOMAIN: str | None = os.getenv("AUTH_COOKIE_DOMAIN", "").strip() or None

    # Default restrictivo: los pagos/reembolsos en efectivo solo se aceptan
    # con una caja abierta. La variable existe únicamente para aislar pruebas
    # unitarias antiguas que validan cálculos de pagos sin montar Caja.
    REQUIRE_OPEN_CASH_FOR_CASH_PAYMENTS: bool = _env_bool(
        "REQUIRE_OPEN_CASH_FOR_CASH_PAYMENTS", True
    )

    # Notificación por correo de reservaciones nuevas del portal
    # público. Todo queda vacío por defecto a propósito: si no se
    # configura, el sistema sigue funcionando (la reservación se crea
    # y se ve en el Dashboard igual) — solo no se manda el correo. Ver
    # app/services/notificacion_service.py.
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")

    # A dónde llegan los avisos de reservación nueva (normalmente tu correo).
    NOTIFICACIONES_EMAIL_DESTINO: str = os.getenv("NOTIFICACIONES_EMAIL_DESTINO", "")

    RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "")
    RESEND_FROM_EMAIL: str = os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev")


settings = Settings()
