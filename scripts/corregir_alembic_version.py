"""
Corrige el registro de Alembic en la base de datos real: cambia el
nombre viejo (con el typo) por el correcto, sin tocar ninguna otra
tabla ni ningún dato real. Usa la misma DATABASE_URL que ya usa la
app (de tu .env) — no hace falta psql ni ninguna herramienta nueva.
"""
from sqlalchemy import create_engine, text

from app.core.config import settings

VIEJO = "0005_no_traslape_hospedaje"
NUEVO = "0005_no_traslape_unidad_hospedaje"

engine = create_engine(settings.DATABASE_URL)

with engine.begin() as conn:
    actual = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    print(f"Valor actual en alembic_version: {actual!r}")

    if actual != VIEJO:
        print(f"No es el valor esperado ({VIEJO!r}) — no se cambia nada, revisa manualmente.")
    else:
        # La columna version_num de Alembic viene por defecto como
        # VARCHAR(32) — el nombre correcto (34 caracteres) no cabe.
        # Se amplía primero; es una operación segura, solo cambia el
        # tamaño máximo permitido del campo, no toca ningún dato.
        conn.execute(text("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64)"))
        conn.execute(
            text("UPDATE alembic_version SET version_num = :nuevo WHERE version_num = :viejo"),
            {"nuevo": NUEVO, "viejo": VIEJO},
        )
        print(f"Corregido: {VIEJO!r} -> {NUEVO!r}")
