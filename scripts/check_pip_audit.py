from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPORT = Path("pip-audit.json")


def dependencies(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        value = payload.get("dependencies", [])
        return value if isinstance(value, list) else []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def main() -> int:
    try:
        payload = json.loads(REPORT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"No se pudo leer el reporte de pip-audit: {exc}")
        return 1

    actionable: list[str] = []
    without_fix: list[str] = []

    for dependency in dependencies(payload):
        name = str(dependency.get("name", "desconocido"))
        version = str(dependency.get("version", "desconocida"))
        vulns = dependency.get("vulns", [])
        if not isinstance(vulns, list):
            continue

        for vulnerability in vulns:
            if not isinstance(vulnerability, dict):
                continue
            vulnerability_id = str(vulnerability.get("id", "sin-id"))
            fix_versions = vulnerability.get("fix_versions") or []
            description = f"{name} {version}: {vulnerability_id}"
            if isinstance(fix_versions, list) and fix_versions:
                actionable.append(f"{description}; corregir con {', '.join(map(str, fix_versions))}")
            else:
                without_fix.append(description)

    for finding in without_fix:
        print(f"::warning title=Vulnerabilidad sin corrección publicada::{finding}")

    if actionable:
        print("Vulnerabilidades con actualización disponible:")
        for finding in actionable:
            print(f"- {finding}")
        return 1

    print("No hay vulnerabilidades accionables en las dependencias auditadas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
