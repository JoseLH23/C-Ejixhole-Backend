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
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

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
    db: Session = Depends(get_db),
):
    service = ReporteService(db)
    return service.reporte_ingresos(
        periodo=periodo,
        desde=desde,
        hasta=hasta,
        agrupar_por=agrupar_por,
        metodo_pago=metodo_pago,
        servicio_id=servicio_id,
    )


@router.get("/cuentas-por-cobrar", response_model=ReporteCuentasPorCobrarOut)
def reporte_cuentas_por_cobrar(
    antiguedad_minima_dias: Optional[int] = None,
    db: Session = Depends(get_db),
):
    service = ReporteService(db)
    return service.reporte_cuentas_por_cobrar(antiguedad_minima_dias=antiguedad_minima_dias)


@router.get("/ocupacion", response_model=ReporteOcupacionOut)
def reporte_ocupacion(
    periodo: Optional[str] = None,
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    servicio_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    service = ReporteService(db)
    return service.reporte_ocupacion(periodo=periodo, desde=desde, hasta=hasta, servicio_id=servicio_id)


@router.get("/servicios-mas-vendidos", response_model=ReporteServiciosMasVendidosOut)
def reporte_servicios_mas_vendidos(
    periodo: Optional[str] = None,
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    limit: int = 10,
    db: Session = Depends(get_db),
):
    service = ReporteService(db)
    return service.reporte_servicios_mas_vendidos(periodo=periodo, desde=desde, hasta=hasta, limit=limit)


@router.get("/clientes-frecuentes", response_model=ReporteClientesFrecuentesOut)
def reporte_clientes_frecuentes(
    periodo: Optional[str] = None,
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    limit: int = 10,
    minimo_reservaciones: int = 2,
    db: Session = Depends(get_db),
):
    service = ReporteService(db)
    return service.reporte_clientes_frecuentes(
        periodo=periodo,
        desde=desde,
        hasta=hasta,
        limit=limit,
        minimo_reservaciones=minimo_reservaciones,
    )


@router.get("/reservaciones-por-estado", response_model=ReporteReservacionesPorEstadoOut)
def reporte_reservaciones_por_estado(
    periodo: Optional[str] = None,
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    servicio_id: Optional[int] = None,
    origen: Optional[str] = None,
    db: Session = Depends(get_db),
):
    service = ReporteService(db)
    return service.reporte_reservaciones_por_estado(
        periodo=periodo, desde=desde, hasta=hasta, servicio_id=servicio_id, origen=origen
    )


@router.get("/cancelaciones", response_model=ReporteCancelacionesOut)
def reporte_cancelaciones(
    periodo: Optional[str] = None,
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    db: Session = Depends(get_db),
):
    service = ReporteService(db)
    return service.reporte_cancelaciones(periodo=periodo, desde=desde, hasta=hasta)


@router.get("/tendencia-reservaciones", response_model=ReporteTendenciaReservacionesOut)
def reporte_tendencia_reservaciones(
    periodo: Optional[str] = None,
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    agrupar_por: str = "dia",
    estado: Optional[str] = None,
    db: Session = Depends(get_db),
):
    service = ReporteService(db)
    return service.reporte_tendencia_reservaciones(
        periodo=periodo, desde=desde, hasta=hasta, agrupar_por=agrupar_por, estado=estado
    )


@router.get("/clientes-nuevos", response_model=ReporteClientesNuevosOut)
def reporte_clientes_nuevos(
    periodo: Optional[str] = None,
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    agrupar_por: str = "dia",
    db: Session = Depends(get_db),
):
    service = ReporteService(db)
    return service.reporte_clientes_nuevos(
        periodo=periodo, desde=desde, hasta=hasta, agrupar_por=agrupar_por
    )


@router.get("/proximas-reservaciones", response_model=ReporteProximasReservacionesOut)
def reporte_proximas_reservaciones(
    dias: int = 7,
    estado: Optional[str] = "confirmada",
    db: Session = Depends(get_db),
):
    service = ReporteService(db)
    return service.reporte_proximas_reservaciones(dias=dias, estado=estado)
