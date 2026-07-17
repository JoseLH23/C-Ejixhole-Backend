"""Arranque seguro para Render Free: migra PostgreSQL antes de iniciar la API."""
from __future__ import annotations

import os
import subprocess
import sys


def uvicorn_command(port: str | None = None) -> list[str]:
    resolved_port = (port or os.getenv("PORT", "8000")).strip()
    if not resolved_port.isdigit() or not 1 <= int(resolved_port) <= 65535:
        raise RuntimeError("PORT debe ser un número entre 1 y 65535.")
    return [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        resolved_port,
    ]


def run_migrations() -> None:
    """Aplica todas las migraciones; si falla, el despliegue no arranca."""
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True,
    )


def main() -> None:
    print("==> Aplicando migraciones PostgreSQL...", flush=True)
    run_migrations()
    print("==> Migraciones listas. Iniciando EjiXhole API...", flush=True)
    os.execvpe(sys.executable, uvicorn_command(), os.environ.copy())


if __name__ == "__main__":
    main()
