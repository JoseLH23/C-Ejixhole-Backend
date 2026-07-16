from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class MetricasOperativasOut(BaseModel):
    ingresos_hoy: Decimal
    ingresos_mes: Decimal
    reservaciones_activas: int
    proximas_7_dias: int
    saldo_pendiente_total: Decimal
    tasa_cancelacion_mes: float
    ocupacion_promedio_mes: float
    diferencia_caja_hoy: Decimal


class MhCoreOperationalSummaryOut(BaseModel):
    generated_at: datetime
    business_date: date
    source: Literal["ejixhole"] = "ejixhole"
    api_version: Literal["v1"] = "v1"
    access: Literal["read_only"] = "read_only"
    scope: Literal["ejixhole:read:operations"] = "ejixhole:read:operations"
    metrics: MetricasOperativasOut
