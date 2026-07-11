from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class SerieIngresoItem(BaseModel):
    periodo: str
    ingresos: Decimal
    reembolsos: Decimal
    neto: Decimal


class ReporteIngresosOut(BaseModel):
    desde: date
    hasta: date
    agrupar_por: str
    total_ingresos: Decimal
    total_reembolsos: Decimal
    total_neto: Decimal
    num_pagos: int
    serie: list[SerieIngresoItem]


class CuentaPorCobrarItem(BaseModel):
    reservacion_id: int
    cliente_id: int
    servicio_id: int
    fecha_visita: date
    estado: str
    total: Decimal
    monto_pagado: Decimal
    saldo_pendiente: Decimal
    antiguedad_dias: int


class ReporteCuentasPorCobrarOut(BaseModel):
    fecha_corte: date
    num_reservaciones: int
    total_pendiente: Decimal
    items: list[CuentaPorCobrarItem]


class OcupacionServicioItem(BaseModel):
    servicio_id: int
    servicio_nombre: str
    capacidad_maxima: Optional[int]
    num_reservaciones: int
    total_personas: int
    promedio_personas_por_reservacion: float
    porcentaje_ocupacion_promedio: Optional[float]


class ReporteOcupacionOut(BaseModel):
    desde: date
    hasta: date
    items: list[OcupacionServicioItem]


class ServicioMasVendidoItem(BaseModel):
    servicio_id: int
    servicio_nombre: str
    num_reservaciones: int
    total_facturado: Decimal


class ReporteServiciosMasVendidosOut(BaseModel):
    desde: date
    hasta: date
    items: list[ServicioMasVendidoItem]


class ClienteFrecuenteItem(BaseModel):
    cliente_id: int
    cliente_nombre: str
    num_reservaciones: int
    total_gastado: Decimal


class ReporteClientesFrecuentesOut(BaseModel):
    desde: date
    hasta: date
    minimo_reservaciones: int
    items: list[ClienteFrecuenteItem]


class ReporteReservacionesPorEstadoOut(BaseModel):
    desde: date
    hasta: date
    total: int
    por_estado: dict[str, int]


class CancelacionPorServicioItem(BaseModel):
    servicio_id: int
    servicio_nombre: str
    num_cancelaciones: int


class ReporteCancelacionesOut(BaseModel):
    desde: date
    hasta: date
    total_reservaciones: int
    num_canceladas: int
    tasa_cancelacion: float
    desglose_por_servicio: list[CancelacionPorServicioItem]


class SerieTendenciaItem(BaseModel):
    periodo: str
    num_reservaciones: int


class ReporteTendenciaReservacionesOut(BaseModel):
    desde: date
    hasta: date
    agrupar_por: str
    total: int
    serie: list[SerieTendenciaItem]


class SerieClientesNuevosItem(BaseModel):
    periodo: str
    num_clientes: int


class ReporteClientesNuevosOut(BaseModel):
    desde: date
    hasta: date
    agrupar_por: str
    total: int
    serie: list[SerieClientesNuevosItem]


class ProximaReservacionItem(BaseModel):
    reservacion_id: int
    cliente_id: int
    cliente_nombre: str
    servicio_id: int
    servicio_nombre: str
    fecha_visita: date
    num_personas: int
    estado: str


class ReporteProximasReservacionesOut(BaseModel):
    desde: date
    hasta: date
    dias: int
    total: int
    items: list[ProximaReservacionItem]
