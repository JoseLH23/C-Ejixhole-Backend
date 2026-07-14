"""
Configuración de conexión a PostgreSQL y sesión de SQLAlchemy.

ME-05 (auditoría de seguridad 13/jul/2026): antes solo tenía
pool_pre_ping/future — sin límites de pool, timeout de conexión ni
reciclado, un pico de tráfico podía agotar el pool en silencio, y
conexiones que Neon cierra por inactividad podían quedar "muertas" en
el pool hasta el siguiente uso. Todo configurable por variable de
entorno, con valores por defecto conservadores (Neon/Render en el
plan actual no soportan cientos de conexiones simultáneas).
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    future=True,
    pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
    pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "30")),
    # Neon (y la mayoría de Postgres administrados) cierran conexiones
    # inactivas por su cuenta — reciclar antes de eso evita usar una
    # conexión que el servidor ya cerró silenciosamente.
    pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "1800")),
    connect_args={"connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT", "10"))},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)

Base = declarative_base()


def get_db():
    """Dependency de FastAPI: entrega una sesión y la cierra siempre."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
