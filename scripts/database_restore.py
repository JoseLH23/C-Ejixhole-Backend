from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


def parse_database_url(value: str) -> tuple[dict[str, str], str]:
    parsed = urlparse(value)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ValueError("La URL destino debe usar postgresql:// o postgres://")
    database = unquote(parsed.path.lstrip("/"))
    if not database:
        raise ValueError("La URL destino no contiene nombre de base de datos")

    query = parse_qs(parsed.query)
    environment = os.environ.copy()
    environment.update(
        {
            "PGHOST": parsed.hostname or "localhost",
            "PGPORT": str(parsed.port or 5432),
            "PGUSER": unquote(parsed.username or ""),
            "PGDATABASE": database,
        }
    )
    if parsed.password:
        environment["PGPASSWORD"] = unquote(parsed.password)
    if query.get("sslmode"):
        environment["PGSSLMODE"] = query["sslmode"][0]
    return environment, database


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_and_verify_manifest(backup_path: Path, manifest_path: Path) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise ValueError("Versión de manifiesto no soportada")
    if manifest.get("backup_file") != backup_path.name:
        raise ValueError("El manifiesto no corresponde al archivo de respaldo")
    expected = manifest.get("sha256")
    actual = sha256_file(backup_path)
    if expected != actual:
        raise ValueError("El checksum SHA-256 del respaldo no coincide")
    if manifest.get("size_bytes") != backup_path.stat().st_size:
        raise ValueError("El tamaño del respaldo no coincide con el manifiesto")
    return manifest


def restore_backup(
    backup_path: Path,
    manifest_path: Path,
    target_database_url: str,
    confirm_database_name: str,
    allow_production: bool,
) -> str:
    load_and_verify_manifest(backup_path, manifest_path)
    environment, database = parse_database_url(target_database_url)
    if database != confirm_database_name:
        raise ValueError("--confirm-database-name no coincide con la base destino")
    if not allow_production and any(word in database.lower() for word in ("prod", "production")):
        raise ValueError("La restauración sobre un nombre productivo requiere --allow-production")

    subprocess.run(
        [
            "pg_restore",
            "--clean",
            "--if-exists",
            "--no-owner",
            "--no-privileges",
            "--exit-on-error",
            str(backup_path),
        ],
        check=True,
        env=environment,
    )
    result = subprocess.run(
        ["psql", "--tuples-only", "--no-align", "--command", "SELECT version_num FROM alembic_version LIMIT 1"],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    version = result.stdout.strip()
    if not version:
        raise ValueError("La base restaurada no contiene versión Alembic")
    return version


def main() -> int:
    parser = argparse.ArgumentParser(description="Restaurar un respaldo PostgreSQL verificado.")
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--target-database-url", default=os.environ.get("RESTORE_DATABASE_URL"))
    parser.add_argument("--confirm-database-name", required=True)
    parser.add_argument("--allow-production", action="store_true")
    args = parser.parse_args()

    if not args.target_database_url:
        parser.error("Define RESTORE_DATABASE_URL o usa --target-database-url")
    manifest = args.manifest or args.backup.with_suffix(".manifest.json")

    try:
        version = restore_backup(
            args.backup,
            manifest,
            args.target_database_url,
            args.confirm_database_name,
            args.allow_production,
        )
    except (ValueError, OSError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        print(f"No se pudo restaurar el respaldo: {exc}", file=sys.stderr)
        return 1

    print(f"Restauración verificada. Alembic: {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
