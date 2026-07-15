"""
Rutas de Reportes. TODAS requieren rol admin (ver
docs/modulos/reportes-diseno.md sección 2).

Implementado hasta ahora:
  Entrega 1 (financieros):
    - GET /reportes/ingresos
    - GET /reportes/cuentas-por-cobrar
  Entrega 2 (operacionales):
    - GET /reportes/ocupacion
    - GET /reportes/servicios-mas-vendidos
    - GET /reportes/clientes-frecuentes
    - GET /reportes/reservaciones-por-estado
    - GET /reportes/cancelaciones
    - GET /reportes/tendencia-reservaciones

Pendientes del diseño original (dashboard, top clientes por gasto
puro, rendimiento por usuario) se agregan en iteraciones siguientes.

Exportación CSV: todos los reportes de esta lista aceptan
?formato=csv (default "json") y responden un archivo descargable con
la lista de detalle del reporte ("serie"/"items"/"por_estado"). Antes
esto lo generaba el frontend del lado del cliente a partir del JSON;
ahora se genera aquí, sobre los mismos datos ya calculados por
ReporteService — ver app/core/csv_export.py.
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.csv_export import filas_desde_conteo, respuesta_csv
from app.database import get_db
from app.dependencies import require_roles
from app.schemas.reporte import (
    ReporteCancelacionesOut,
    ReporteClientesFrecuentesOut,
    ReporteClientesNuevosOut,
    ReporteCuentasPorCobrarOut,
    ReporteIngresosOut,
    ReporteOcupacionOut,
    ReporteProximasReservacionesOut,
    ReporteReservacionesPorEstadoOut,
    ReporteServiciosMasVendidosOut,
    ReporteTendenciaReservacionesOut,
)
from app.services.reporte_service import ReporteService

router = APIRouter(
    prefix="/reportes", tags=["Reportes"], dependencies=[Depends(require_roles("admin"))]
)


@router.get("/ingresos", response_model=ReporteIngresosOut)
def reporte_ingresos(
    periodo: Optional[str] = None,
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    agrupar_por: str = "dia",
    metodo_pago: Optional[str] = None,
    servicio_id: Optional[int] = None,
    formato: str = Query("json", pattern="^(json|csv)$"),
    db: Session = Depends(get_db),
):
    service = ReporteService(db)
    data = service.reporte_ingresos(
        periodo=periodo,
        desde=desde,
        hasta=hasta,
        agrupar_por=agrupar_por,
        metodo_pago=metodo_pago,
        servicio_id=servicio_id,
    )
    if formato == "csv":
        return respuesta_csv(
            data["serie"], ["periodo", "ingresos", "reembolsos", "neto"], "reporte_ingresos.csv"
        )
    return data


@router.get("/cuentas-por-cobrar", response_model=ReporteCuentasPorCobrarOut)
def reporte_cuentas_por_cobrar(
    antiguedad_minima_dias: Optional[int] = None,
    formato: str = Query("json", pattern="^(json|csv)$"),
    db: Session = Depends(get_db),
):
    service = ReporteService(db)
    data = service.reporte_cuentas_por_cobrar(antiguedad_minima_dias=antiguedad_minima_dias)
    if formato == "csv":
        columnas = [
            "reservacion_id", "cliente_id", "servicio_id", "fecha_visita", "estado",
            "total", "monto_pagado", "saldo_pendiente", "antiguedad_dias",
        ]
        return respuesta_csv(data["items"], columnas, "reporte_cuentas_por_cobrar.csv")
    return data


@router.get("/ocupacion", response_model=ReporteOcupacionOut)
def reporte_ocupacion(
    periodo: Optional[str] = None,
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    servicio_id: Optional[int] = None,
    formato: str = Query("json", pattern="^(json|csv)$"),
    db: Session = Depends(get_db),
):
    service = ReporteService(db)
    data = service.reporte_ocupacion(periodo=periodo, desde=desde, hasta=hasta, servicio_id=servicio_id)
    if formato == "csv":
        columnas = [
            "servicio_id", "servicio_nombre", "capacidad_maxima", "num_reservaciones",
            "total_personas", "promedio_personas_por_reservacion", "porcentaje_ocupacion_promedio",
        ]
        return respuesta_csv(data["items"], columnas, "reporte_ocupacion.csv")
    return data


@router.get("/servicios-mas-vendidos", response_model=ReporteServiciosMasVendidosOut)
def reporte_servicios_mas_vendidos(
    periodo: Optional[str] = None,
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    limit: int = 10,
    formato: str = Query("json", pattern="^(json|csv)$"),
    db: Session = Depends(get_db),
):
    service = ReporteService(db)
    data = service.reporte_servicios_mas_vendidos(periodo=periodo, desde=desde, hasta=hasta, limit=limit)
    if formato == "csv":
        columnas = ["servicio_id", "servicio_nombre", "num_reservaciones", "total_facturado"]
        return respuesta_csv(data["items"], columnas, "reporte_servicios_mas_vendidos.csv")
    return data


@router.get("/clientes-frecuentes", response_model=ReporteClientesFrecuentesOut)
def reporte_clientes_frecuentes(
    periodo: Optional[str] = None,
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    limit: int = 10,
    minimo_reservaciones: int = 2,
    formato: str = Query("json", pattern="^(json|csv)$"),
    db: Session = Depends(get_db),
):
    service = ReporteService(db)
    data = service.reporte_clientes_frecuentes(
        periodo=periodo,
        desde=desde,
        hasta=hasta,
        limit=limit,
        minimo_reservaciones=minimo_reservaciones,
    )
    if formato == "csv":
        columnas = ["cliente_id", "cliente_nombre", "num_reservaciones", "total_gastado"]
        return respuesta_csv(data["items"], columnas, "reporte_clientes_frecuentes.csv")
    return data


@router.get("/reservaciones-por-estado", response_model=ReporteReservacionesPorEstadoOut)
def reporte_reservaciones_por_estado(
    periodo: Optional[str] = None,
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    servicio_id: Optional[int] = None,
    origen: Optional[str] = None,
    formato: str = Query("json", pattern="^(json|csv)$"),
    db: Session = Depends(get_db),
):
    service = ReporteService(db)
    data = service.reporte_reservaciones_por_estado(
        periodo=periodo, desde=desde, hasta=hasta, servicio_id=servicio_id, origen=origen
    )
    if formato == "csv":
        filas = filas_desde_conteo(data["por_estado"], "estado", "cantidad")
        return respuesta_csv(filas, ["estado", "cantidad"], "reporte_reservaciones_por_estado.csv")
    return data


@router.get("/cancelaciones", response_model=ReporteCancelacionesOut)
def reporte_cancelaciones(
    periodo: Optional[str] = None,
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    formato: str = Query("json", pattern="^(json|csv)$"),
    db: Session = Depends(get_db),
):
    service = ReporteService(db)
    data = service.reporte_cancelaciones(periodo=periodo, desde=desde, hasta=hasta)
    if formato == "csv":
        columnas = ["servicio_id", "servicio_nombre", "num_cancelaciones"]
        return respuesta_csv(data["desglose_por_servicio"], columnas, "reporte_cancelaciones.csv")
    return data


@router.get("/tendencia-reservaciones", response_model=ReporteTendenciaReservacionesOut)
def reporte_tendencia_reservaciones(
    periodo: Optional[str] = None,
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    agrupar_por: str = "dia",
    estado: Optional[str] = None,
    formato: str = Query("json", pattern="^(json|csv)$"),
    db: Session = Depends(get_db),
):
    service = ReporteService(db)
    data = service.reporte_tendencia_reservaciones(
        periodo=periodo, desde=desde, hasta=hasta, agrupar_por=agrupar_por, estado=estado
    )
    if formato == "csv":
        return respuesta_csv(
            data["serie"], ["periodo", "num_reservaciones"], "reporte_tendencia_reservaciones.csv"
        )
    return data


@router.get("/clientes-nuevos", response_model=ReporteClientesNuevosOut)
def reporte_clientes_nuevos(
    periodo: Optional[str] = None,
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    agrupar_por: str = "dia",
    formato: str = Query("json", pattern="^(json|csv)$"),
    db: Session = Depends(get_db),
):
    service = ReporteService(db)
    data = service.reporte_clientes_nuevos(
        periodo=periodo, desde=desde, hasta=hasta, agrupar_por=agrupar_por
    )
    if formato == "csv":
        return respuesta_csv(data["serie"], ["periodo", "num_clientes"], "reporte_clientes_nuevos.csv")
    return data


@router.get("/proximas-reservaciones", response_model=ReporteProximasReservacionesOut)
def reporte_proximas_reservaciones(
    dias: int = 7,
    estado: Optional[str] = "confirmada",
    formato: str = Query("json", pattern="^(json|csv)$"),
    db: Session = Depends(get_db),
):
    service = ReporteService(db)
    data = service.reporte_proximas_reservaciones(dias=dias, estado=estado)
    if formato == "csv":
        columnas = [
            "reservacion_id", "cliente_id", "cliente_nombre", "servicio_id",
            "servicio_nombre", "fecha_visita", "num_personas", "estado",
        ]
        return respuesta_csv(data["items"], columnas, "reporte_proximas_reservaciones.csv")
    return data
