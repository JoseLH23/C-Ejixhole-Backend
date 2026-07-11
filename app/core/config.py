import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    PROJECT_NAME: str = "EjiXhole Experience OS"
    VERSION: str = "0.1.0"

    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://ejixhole_user:changeme@localhost:5432/ejixhole_db",
    )

    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "change-this-in-production")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

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


settings = Settings()