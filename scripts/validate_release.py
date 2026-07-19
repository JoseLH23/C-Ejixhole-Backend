from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

MANIFEST = Path("release-manifest.json")
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate() -> dict:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    required = {"schema_version", "component", "version", "ecosystem_release", "produces", "requires"}
    missing = sorted(required - set(data))
    if missing:
        raise SystemExit("Faltan campos: " + ", ".join(missing))
    if data["schema_version"] != 1 or data["component"] != "ejixhole-backend":
        raise SystemExit("Manifiesto incompatible con este repositorio")
    if not SEMVER.fullmatch(data["version"]):
        raise SystemExit("La versión no cumple SemVer")
    for name in ("produces", "requires"):
        values = data[name]
        if not isinstance(values, list) or len(values) != len(set(values)):
            raise SystemExit(f"{name} debe ser una lista sin duplicados")
    expected = {"ejixhole.api.v1", "ejixhole.events.v1", "ejixhole.observability.v1"}
    if not expected.issubset(set(data["produces"])):
        raise SystemExit("Faltan contratos obligatorios")
    if os.getenv("GITHUB_REF_TYPE") == "tag":
        tag = os.getenv("GITHUB_REF_NAME", "")
        if tag != f"v{data['version']}":
            raise SystemExit("La etiqueta no coincide con el manifiesto")
    return data


def write_evidence(data: dict, output: Path) -> None:
    files = [Path("release-manifest.json"), Path("requirements.txt")]
    payload = {
        "schema_version": 1,
        "component": data["component"],
        "version": data["version"],
        "ecosystem_release": data["ecosystem_release"],
        "commit": os.getenv("GITHUB_SHA", "local"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "files": {str(path): file_hash(path) for path in files if path.exists()},
        "migration_files": sorted(path.name for path in Path("alembic/versions").glob("*.py")),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    data = validate()
    if args.evidence:
        write_evidence(data, args.evidence)
    print(f"release válido: {data['component']} v{data['version']}")


if __name__ == "__main__":
    main()
