from datetime import date
from decimal import Decimal
from typing import Optional, Union

from pydantic import BaseModel

Numero = Union[Decimal, int, float]


class TarjetaOut(BaseModel):
    titulo: str
    valor: Numero
    comparacion_valor_anterior: Optional[Numero] = None
    comparacion_porcentaje: Optional[float] = None
    tendencia: Optional[str] = None


class DashboardResumenOut(BaseModel):
    fecha: date
    tarjetas: list[TarjetaOut]
