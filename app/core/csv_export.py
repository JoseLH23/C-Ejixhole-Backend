"""
Exportación CSV de Reportes. El frontend generaba estos CSV del lado
del cliente a partir del JSON de /reportes/*; ahora el backend los
genera directo con ?formato=csv en el mismo endpoint, sobre los MISMOS
datos ya calculados por ReporteService (nunca se recalculan cifras
distintas para el CSV).

Solo se aplana a filas la lista de detalle de cada reporte
("serie"/"items"/"por_estado") — los totales/resumen del reporte se
quedan en el JSON, que sigue siendo la fuente completa.
"""
import csv
import io
from decimal import Decimal
from typing import Any

from fastapi.responses import StreamingResponse

BOM_UTF8 = "﻿"  # Excel en Windows (ver CLAUDE.md) lo necesita para no romper acentos/ñ.

# Inyección de fórmulas (CSV/Formula Injection, CWE-1236): un valor que
# llega hasta el CSV con datos de entrada del cliente (ej.
# cliente_nombre viene de nombre_completo del portal público, sin
# login) y empieza con =, +, -, @, tab o retorno de carro se interpreta
# como fórmula al abrir el archivo en Excel/Sheets — puede ejecutar
# comandos o filtrar datos a un servidor externo. Se neutraliza
# anteponiendo un apóstrofe, el mismo mecanismo que usa Excel para
# forzar texto literal.
CARACTERES_FORMULA_PELIGROSOS = ("=", "+", "-", "@", "\t", "\r")


def _escapar_formula(valor: str) -> str:
    if valor.startswith(CARACTERES_FORMULA_PELIGROSOS):
        return "'" + valor
    return valor


def _valor_csv(valor: Any) -> Any:
    if isinstance(valor, Decimal):
        valor = str(valor)
    if isinstance(valor, str):
        return _escapar_formula(valor)
    return valor


def filas_desde_conteo(conteo: dict, columna_clave: str, columna_valor: str) -> list[dict]:
    """Para reportes cuyo detalle es un dict (ej. por_estado), no una lista de dicts."""
    return [{columna_clave: clave, columna_valor: valor} for clave, valor in conteo.items()]


def respuesta_csv(filas: list[dict], columnas: list[str], nombre_archivo: str) -> StreamingResponse:
    buffer = io.StringIO()
    buffer.write(BOM_UTF8)
    escritor = csv.DictWriter(buffer, fieldnames=columnas, extrasaction="ignore")
    escritor.writeheader()
    for fila in filas:
        escritor.writerow({columna: _valor_csv(fila.get(columna)) for columna in columnas})
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'},
    )
