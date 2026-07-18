from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


def parse_database_url(value: str) -> tuple[dict[str, str], str, str]:
    parsed = urlparse(value)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ValueError("DATABASE_URL debe usar postgresql:// o postgres://")
    database = unquote(parsed.path.lstrip("/"))
    if not database:
        raise ValueError("DATABASE_URL no contiene nombre de base de datos")

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
    return environment, database, parsed.hostname or "localhost"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def command_version(command: str) -> str:
    result = subprocess.run([command, "--version"], check=True, capture_output=True, text=True)
    return result.stdout.strip()


def create_backup(database_url: str, output_dir: Path, prefix: str) -> tuple[Path, Path]:
    environment, database, host = parse_database_url(database_url)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_path = output_dir / f"{prefix}-{timestamp}.dump"
    temporary_path = backup_path.with_suffix(".dump.tmp")
    manifest_path = backup_path.with_suffix(".manifest.json")

    try:
        subprocess.run(
            [
                "pg_dump",
                "--format=custom",
                "--no-owner",
                "--no-privileges",
                "--file",
                str(temporary_path),
            ],
            check=True,
            env=environment,
        )
        temporary_path.replace(backup_path)
    finally:
        temporary_path.unlink(missing_ok=True)

    manifest = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "database": database,
        "host": host,
        "format": "postgresql-custom",
        "backup_file": backup_path.name,
        "size_bytes": backup_path.stat().st_size,
        "sha256": sha256_file(backup_path),
        "pg_dump_version": command_version("pg_dump"),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return backup_path, manifest_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Crear un respaldo verificable de PostgreSQL.")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--output-dir", type=Path, default=Path("backups"))
    parser.add_argument("--prefix", default="ejixhole")
    args = parser.parse_args()

    if not args.database_url:
        parser.error("Define DATABASE_URL o usa --database-url")

    try:
        backup, manifest = create_backup(args.database_url, args.output_dir, args.prefix)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f"No se pudo crear el respaldo: {exc}", file=sys.stderr)
        return 1

    print(f"Respaldo creado: {backup}")
    print(f"Manifiesto creado: {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
