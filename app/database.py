"""
Configuración de conexión a PostgreSQL y sesión de SQLAlchemy.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, future=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)

Base = declarative_base()


def get_db():
    """Dependency de FastAPI: entrega una sesión y la cierra siempre."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
